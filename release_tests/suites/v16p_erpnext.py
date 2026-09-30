"""version-16-polished ERPNext: new print formats, opening stock, party import, settings map.

Every document is printed as the role that works with it (sales for Quotation /
Sales Order / Delivery Note, accounts for invoices, purchase for PO / RFQ), and
the features run as the role the release targets them at.
"""

from __future__ import annotations

import csv
import io
import json
import time
from datetime import date, timedelta
from typing import ClassVar

from .. import factories, personas
from ..checks import _CSRF_HINT, _csrf_refused, ensure, expect_allowed, expect_denied
from ..client import FrappeAPIError, FrappeClient
from ..gating import Versions
from ._v16p import import_errors, polished_precheck
from .base import ReleaseSuite, SkipStep, Step

PRINT_HTML = "frappe.www.printview.get_html_and_style"
PDF = "frappe.utils.print_format.download_pdf"
OPENING = "erpnext.stock.doctype.item.item.make_opening_stock_entry"
SETTINGS_MAP = "frappe.desk.doctype_settings.settings_map"

# The 32 new builder formats: four styles for each of eight DocTypes.
PRINT_STYLES = ("Bordered", "Classic", "Modern", "Modern with Images")
# DocType -> persona who prints it.
PRINTED_BY = {
    "Quotation": "sales",
    "Sales Order": "sales",
    "Delivery Note": "sales",
    "Sales Invoice": "accounts",
    "POS Invoice": "accounts",
    "Purchase Order": "purchase",
    "Purchase Invoice": "accounts",
    "Request for Quotation": "purchase",
}
IMPORT_TIMEOUT_S = 120


def _setup(client: FrappeClient, ctx: dict) -> None:
    ctx["company"] = company = factories.ensure_company(client)
    ctx["customer"] = customer = factories.ensure_customer(client)
    ctx["supplier"] = supplier = factories.ensure_supplier(client)
    ctx["warehouse"] = warehouse = factories.ensure_warehouse(client, company)
    ctx["item"] = item = factories.ensure_stock_item(client, company, warehouse)
    later = str(date.today() + timedelta(days=7))
    line = {"item_code": item, "qty": 1, "rate": 100, "warehouse": warehouse}
    drafts = {
        "Quotation": {"quotation_to": "Customer", "party_name": customer, "items": [line]},
        "Sales Order": {
            "customer": customer,
            "delivery_date": later,
            "items": [{**line, "delivery_date": later}],
        },
        "Delivery Note": {"customer": customer, "items": [line]},
        "Sales Invoice": {"customer": customer, "items": [line]},
        "Purchase Order": {
            "supplier": supplier,
            "schedule_date": later,
            "items": [{**line, "schedule_date": later}],
        },
        "Purchase Invoice": {"supplier": supplier, "items": [line]},
        "Request for Quotation": {
            "suppliers": [{"supplier": supplier}],
            "message_for_supplier": "Release test RFQ",
            "items": [{**line, "schedule_date": later, "uom": "Nos", "conversion_factor": 1}],
        },
    }
    ctx["drafts"] = {}
    for doctype, body in drafts.items():
        # Reuse an earlier run's draft so re-runs don't pile up documents.
        party = {k: body[k] for k in ("customer", "supplier", "party_name") if k in body}
        reuse = client.get_list(
            doctype, filters={"docstatus": 0, "company": company, **party}, fields=["name"], limit=1
        )
        ctx["drafts"][doctype] = (
            reuse[0]["name"]
            if reuse
            else client.insert({"doctype": doctype, "company": company, **body})["name"]
        )
    # POS Invoice needs a POS Profile to save; print an unsaved one instead.
    ctx["pos_doc"] = {
        "doctype": "POS Invoice",
        "company": company,
        "customer": customer,
        "items": [line],
    }


def _formats_shipped(client: FrappeClient, ctx: dict) -> None:
    wanted = [f"{dt} {style}" for dt in PRINTED_BY for style in PRINT_STYLES]
    rows = client.get_list(
        "Print Format", filters={"name": ["in", wanted]}, fields=["name", "disabled"], limit=100
    )
    present = {r["name"] for r in rows}
    missing = [n for n in wanted if n not in present]
    disabled = sorted(r["name"] for r in rows if r.get("disabled"))
    ensure(
        not missing and not disabled,
        "all 32 new print formats are installed and enabled",
        expected="32 formats (Bordered/Classic/Modern/Modern with Images × 8 DocTypes), none disabled",
        actual=f"missing {missing or 'none'}; disabled {disabled or 'none'}",
        endpoint="Print Format",
    )


def _default_formats_valid(client: FrappeClient, ctx: dict) -> None:
    """New sites default to Modern with Images; upgraded sites keep their own default.

    Either way the default must point at a format that exists and is enabled.
    """
    setters = client.get_list(
        "Property Setter",
        filters={"property": "default_print_format", "doc_type": ["in", list(PRINTED_BY)]},
        fields=["doc_type", "value"],
        limit=50,
    )
    problems, defaults = [], {}
    for row in setters:
        defaults[row["doc_type"]] = row["value"]
        fmt = client.get_list(
            "Print Format", filters={"name": row["value"]}, fields=["name", "disabled"], limit=1
        )
        if not fmt or fmt[0].get("disabled"):
            problems.append(
                f"{row['doc_type']} → {row['value']} ({'missing' if not fmt else 'disabled'})"
            )
    ctx["default_formats"] = defaults
    ensure(
        not problems,
        "default print formats point at enabled formats",
        expected="every default print format exists and is enabled",
        actual="; ".join(problems),
        endpoint="Property Setter (default_print_format)",
    )


def _render_all_formats(client: FrappeClient, ctx: dict) -> None:
    # A print format that doesn't exist silently falls back to the standard one, so
    # "it rendered" proves nothing unless the format is known to be installed.
    wanted = [f"{dt} {style}" for dt in PRINTED_BY for style in PRINT_STYLES]
    installed = {
        r["name"]
        for r in client.get_list(
            "Print Format", filters={"name": ["in", wanted]}, fields=["name"], limit=100
        )
    }
    failures = [f"{name}: not installed" for name in wanted if name not in installed]
    csrf_failures = 0  # the test's own session problem, not a rendering failure
    for doctype, key in PRINTED_BY.items():
        try:
            who = personas.login_as(client, key)
        except SkipStep:
            continue
        for style in PRINT_STYLES:
            fmt = f"{doctype} {style}"
            if fmt not in installed:
                continue
            if doctype == "POS Invoice":
                args = {"doc": json.dumps(ctx["pos_doc"])}
            else:
                args = {"doc": doctype, "name": ctx["drafts"][doctype]}
            try:
                result = who.call(PRINT_HTML, print_format=fmt, **args)
                if not (result or {}).get("html"):
                    failures.append(f"{fmt} as {who.persona.email}: empty HTML")
            except FrappeAPIError as exc:
                if _csrf_refused(exc):
                    csrf_failures += 1
                failures.append(
                    f"{fmt} as {who.persona.email}: HTTP {exc.status} {str(exc.server_messages)[:120]}"
                )
    ensure(
        not failures,
        "every new print format renders for the role that prints it",
        expected="rendered HTML for all 32 formats",
        actual=f"{len(failures)} failed — " + " | ".join(failures[:8]),
        endpoint=PRINT_HTML,
        hint=_CSRF_HINT
        if failures and csrf_failures == len(failures)
        else "sales prints Quotation/SO/DN, accounts prints SI/PI/POS, purchase prints PO/RFQ",
    )


def _invoice_pdf(client: FrappeClient, ctx: dict) -> None:
    accounts = personas.login_as(client, "accounts")
    fmt = "Sales Invoice Modern with Images"
    try:
        resp = accounts.call_raw(
            PDF, doctype="Sales Invoice", name=ctx["drafts"]["Sales Invoice"], format=fmt
        )
    except FrappeAPIError as exc:
        if (
            exc.status
            and exc.status >= 500
            and any(s in str(exc).lower() for s in ("wkhtmltopdf", "weasyprint", "chrome", "typst"))
        ):
            raise SkipStep(f"PDF generator not available on this server: {str(exc)[:150]}") from exc
        raise
    ensure(
        resp.content[:4] == b"%PDF",
        f"'{fmt}' downloads as a PDF",
        expected="a PDF (starts with %PDF)",
        actual=f"{resp.headers.get('Content-Type')} — {resp.content[:40]!r}",
        who=accounts,
        endpoint=PDF,
    )


def _hsn(client: FrappeClient) -> dict:
    """India Compliance makes an HSN code mandatory on Items; empty elsewhere."""
    code = factories._hsn_code(client)
    return {"gst_hsn_code": code} if code else {}


def _opening_stock_dialog(client: FrappeClient, ctx: dict) -> None:
    """The Item form's new opening stock dialog: Item write needed; creates a Stock Reconciliation."""
    code = f"RT-OPEN-{int(time.time())}"
    client.insert(
        {
            **_hsn(client),
            "doctype": "Item",
            "item_code": code,
            "item_name": "Release Opening Stock Item",
            "is_stock_item": 1,
            "stock_uom": "Nos",
            "item_group": "All Item Groups",
            "item_defaults": [{"company": ctx["company"], "default_warehouse": ctx["warehouse"]}],
        }
    )
    args = {
        "item_code": code,
        "company": ctx["company"],
        "qty": 5,
        "valuation_rate": 10,
        "warehouse": ctx["warehouse"],
    }
    try:
        stock = personas.login_as(client, "stock")
        expect_denied(
            stock,
            "Stock User (no Item write) sets opening stock",
            lambda: stock.call(OPENING, **args),
            endpoint=OPENING,
        )
    except SkipStep:
        pass
    item_mgr = personas.login_as(client, "item_mgr")
    reco = expect_allowed(
        item_mgr,
        "Item Manager sets opening stock from the Item form",
        lambda: item_mgr.call(OPENING, **args),
        endpoint=OPENING,
        hint="release note: opening stock dialog on the Item form",
    )
    doc = client.get_doc("Stock Reconciliation", reco) if reco else {}
    ensure(
        doc.get("docstatus") == 1 and doc.get("purpose") == "Opening Stock",
        "opening stock creates a submitted Opening Stock reconciliation",
        expected="submitted Stock Reconciliation, purpose Opening Stock",
        actual=f"{reco}: docstatus {doc.get('docstatus')}, purpose {doc.get('purpose')}",
        who=item_mgr,
        endpoint=OPENING,
    )


def _opening_stock_serial_batch(client: FrappeClient, ctx: dict) -> None:
    """Bug fix: opening stock entered on a new serial / batch item creates its stock."""
    item_mgr = personas.login_as(client, "item_mgr")
    stamp = int(time.time())
    kinds = {
        "serial": {"has_serial_no": 1, "serial_no_series": f"RTSN{stamp}-.####"},
        "batch": {
            "has_batch_no": 1,
            "create_new_batch": 1,
            "batch_number_series": f"RTB{stamp}-.####",
        },
    }
    for kind, extra in kinds.items():
        code = f"RT-OPEN-{kind.upper()}-{stamp}"
        expect_allowed(
            item_mgr,
            f"create a {kind} item with opening stock 3",
            lambda code=code, extra=extra, kind=kind: item_mgr.insert(
                {
                    **_hsn(client),
                    "doctype": "Item",
                    "item_code": code,
                    "item_name": f"Release opening {kind}",
                    "is_stock_item": 1,
                    "stock_uom": "Nos",
                    "item_group": "All Item Groups",
                    "opening_stock": 3,
                    "valuation_rate": 10,
                    "item_defaults": [
                        {"company": ctx["company"], "default_warehouse": ctx["warehouse"]}
                    ],
                    **extra,
                }
            ),
            endpoint="POST /api/resource/Item",
        )
        bins = client.get_list(
            "Bin",
            filters={"item_code": code, "warehouse": ctx["warehouse"]},
            fields=["actual_qty"],
            limit=1,
        )
        qty = float(bins[0]["actual_qty"]) if bins else 0.0
        ensure(
            qty == 3,
            f"opening stock booked for a new {kind} item",
            expected=f"3 in {ctx['warehouse']}",
            actual=f"{qty} ({code})",
            who=item_mgr,
            endpoint="Item insert → Stock Reconciliation",
            hint="changelog bug fix: opening stock for serial and batch items",
        )


def _party_import(client: FrappeClient, ctx: dict) -> None:
    """One file creates a Customer with its Contacts and Addresses.

    Runs as the target's admin login: Data Import is System Manager-only.
    """
    mgr = client
    stamp = int(time.time())
    customer = f"RT Import Customer {stamp}"
    group = client.get_list("Customer Group", filters={"is_group": 0}, fields=["name"], limit=1)
    territory = client.get_list("Territory", filters={"is_group": 0}, fields=["name"], limit=1)
    if not group or not territory:
        raise SkipStep("site has no leaf Customer Group / Territory")
    buf = io.StringIO()
    writer = csv.writer(buf)
    writer.writerow(
        [
            "customer_name",
            "customer_type",
            "customer_group",
            "territory",
            "contacts.first_name",
            "contacts.email_id",
            "contacts.is_primary_contact",
            "addresses.address_line1",
            "addresses.city",
            "addresses.country",
            "addresses.is_primary_address",
        ]
    )
    writer.writerow(
        [
            customer,
            "Company",
            group[0]["name"],
            territory[0]["name"],
            "Ann",
            f"ann.{stamp}@example.com",
            "1",
            "1 Main St",
            "Mumbai",
            "India",
            "1",
        ]
    )
    writer.writerow(["", "", "", "", "Bob", f"bob.{stamp}@example.com", "", "", "", "", ""])

    upload = expect_allowed(
        mgr,
        "upload the party import file",
        lambda: mgr.upload({"is_private": 1}, f"rt-party-{stamp}.csv", buf.getvalue().encode()),
        endpoint="upload_file",
    )
    data_import = expect_allowed(
        mgr,
        "create a Customer data import",
        lambda: mgr.insert(
            {
                "doctype": "Data Import",
                "reference_doctype": "Customer",
                "import_type": "Insert New Records",
                "import_file": upload.json()["message"]["file_url"],
            }
        ),
        endpoint="POST /api/resource/Data Import",
    )["name"]
    expect_allowed(
        mgr,
        "start the Customer data import",
        lambda: mgr.call(
            "frappe.core.doctype.data_import.data_import.form_start_import", data_import=data_import
        ),
        endpoint="form_start_import",
    )
    status, deadline = "Pending", time.monotonic() + IMPORT_TIMEOUT_S
    while time.monotonic() < deadline:
        status = client.get_doc("Data Import", data_import).get("status")
        if status not in ("Pending", "In Progress"):
            break
        time.sleep(3)
    if status in ("Pending", "In Progress"):
        raise SkipStep(
            f"Data Import {data_import} still {status} after {IMPORT_TIMEOUT_S}s — no background worker"
        )
    ensure(
        status == "Success",
        "party import finishes successfully",
        expected="Success",
        actual=f"{status} — {import_errors(client, data_import)}",
        who=mgr,
        endpoint="Data Import (Customer)",
    )
    name = client.get_list(
        "Customer", filters={"customer_name": customer}, fields=["name"], limit=1
    )

    def linked(doctype: str) -> list[dict]:
        return client.get_list(
            doctype,
            filters=[
                ["Dynamic Link", "link_doctype", "=", "Customer"],
                ["Dynamic Link", "link_name", "=", name[0]["name"] if name else "-"],
            ],
            fields=["name"],
            limit=10,
        )

    contacts, addresses = (linked("Contact"), linked("Address")) if name else ([], [])
    ensure(
        bool(name) and len(contacts) == 2 and len(addresses) == 1,
        "one import file creates the customer with its contacts and address",
        expected="1 Customer, 2 Contacts, 1 Address linked to it",
        actual=f"customer {'found' if name else 'missing'}, {len(contacts)} contacts, {len(addresses)} addresses",
        who=mgr,
        endpoint=f"Data Import {data_import}",
        hint="release note: party import (erpnext#57932)",
    )


def _settings_map(client: FrappeClient, ctx: dict) -> None:
    accounts = personas.login_as(client, "accounts")
    groups = expect_allowed(
        accounts,
        "Sales Invoice settings dialog loads its related settings",
        lambda: accounts.call(f"{SETTINGS_MAP}.get_settings_map", doctype="Sales Invoice"),
        endpoint=f"{SETTINGS_MAP}.get_settings_map",
        guards="erpnext#57025",
    )
    ensure(
        bool(groups),
        "Sales Invoice has a settings map",
        expected="at least one settings group (e.g. Accounts Settings)",
        actual=groups,
        who=accounts,
        endpoint=f"{SETTINGS_MAP}.get_settings_map",
        guards="erpnext#57025",
    )
    reader = personas.login_as(client, "reader")  # no access to Sales Invoice
    expect_denied(
        reader,
        "user without Sales Invoice access reads its settings map",
        lambda: reader.call(f"{SETTINGS_MAP}.get_settings_map", doctype="Sales Invoice"),
        endpoint=f"{SETTINGS_MAP}.get_settings_map",
    )


class V16PERPNextSuite(ReleaseSuite):
    name = "v16p_erpnext"
    required_app = "erpnext"
    description = (
        "version-16-polished ERPNext: 32 new print formats render per role, default formats "
        "valid, opening stock (dialog + serial/batch), party import, settings map."
    )
    guards: ClassVar[list[str]] = ["erpnext#57932", "erpnext#57025"]

    # Each check stands alone; one failure must not hide the others.
    independent_steps = True

    def precheck(self, client: FrappeClient) -> str | None:
        return polished_precheck(client)

    def build_steps(self, versions: Versions) -> list[Step]:
        return [
            Step("setup: masters + one draft per printed DocType", _setup, blocks_on_fail=True),
            Step("32 new print formats installed and enabled", _formats_shipped),
            Step("default print formats point at enabled formats", _default_formats_valid),
            Step("each new format renders [sales, accounts, purchase]", _render_all_formats),
            Step("Sales Invoice Modern with Images as PDF [accounts]", _invoice_pdf),
            Step("opening stock dialog [stock refused, item_mgr allowed]", _opening_stock_dialog),
            Step(
                "opening stock on new serial / batch items [item_mgr]", _opening_stock_serial_batch
            ),
            Step("party import: customer + contacts + address [site admin]", _party_import),
            Step("settings map for Sales Invoice [accounts vs reader]", _settings_map),
        ]
