"""version-16-polished: permission and security fixes, checked per role.

Every check runs as an ordinary persona (see :mod:`release_tests.personas`),
never as Administrator, and each one asserts both sides where it matters: the
right role is allowed, the wrong role is refused. Several of the release's fixes
are front-end only (the export button and report view are *hidden*); for those
the suite checks the boot data the UI decides from, plus the server-side refusal
that is the real protection.
"""

from __future__ import annotations

import json
from typing import ClassVar

from .. import personas
from ..checks import ensure, expect_allowed, expect_denied, expect_rejected
from ..client import FrappeAPIError, FrappeClient
from ..gating import Versions
from ._v16p import (
    RT_PROBE_COUNTRIES,
    RT_PROBE_DOCTYPE,
    boot_list,
    ensure_admin_probe_row,
    ensure_perm_probe,
    polished_precheck,
)
from .base import ReleaseSuite, SkipStep, Step

EXPORT = "frappe.desk.reportview.export_query"
PDF = "frappe.utils.print_format.download_pdf"
MULTI_PDF = "frappe.utils.print_format.download_multi_pdf"
PRINT_HTML = "frappe.www.printview.get_html_and_style"
RT_DISABLED_USER = "rt.disabled@example.com"
RT_KANBAN_BOARD = "RT Probe Board"
RT_ADDRESS_PAYLOAD = '<img src=x onerror="alert(1)">RT-XSS'


# ------------------------------------------------------------------ setup
def _setup(client: FrappeClient, ctx: dict) -> None:
    ctx["probe"] = ensure_perm_probe(client)
    ctx["admin_row"] = ensure_admin_probe_row(client)
    for key in ("reader", "exporter", "owner_exporter", "sales"):
        personas.login_as(client, key)
    owner = personas.login_as(client, "owner_exporter")
    ctx["owner_row"] = owner.insert(
        {
            "doctype": RT_PROBE_DOCTYPE,
            "title": "RT probe (owned by owner exporter)",
            "country": "India",
        }
    )["name"]


def _need_probe(ctx: dict) -> None:
    if "probe" not in ctx:
        raise SkipStep("permission probe not set up (see the setup step)")


def _export(who: FrappeClient, names: list[str]):
    return who.call_raw(
        EXPORT,
        doctype=RT_PROBE_DOCTYPE,
        file_format_type="CSV",
        title=RT_PROBE_DOCTYPE,
        fields=json.dumps([f"`tab{RT_PROBE_DOCTYPE}`.`name`", f"`tab{RT_PROBE_DOCTYPE}`.`title`"]),
        filters=json.dumps([[RT_PROBE_DOCTYPE, "name", "in", names]]),
    )


# ------------------------------------------------------------ export (#42577)
def _export_refused_for_reader(client: FrappeClient, ctx: dict) -> None:
    _need_probe(ctx)
    reader = personas.login_as(client, "reader")
    expect_denied(
        reader,
        "user without Export permission exports the probe DocType",
        lambda: _export(reader, [ctx["admin_row"]]),
        endpoint=EXPORT,
        guards="frappe#42577",
    )


def _export_allowed_for_exporter(client: FrappeClient, ctx: dict) -> None:
    _need_probe(ctx)
    exporter = personas.login_as(client, "exporter")
    resp = expect_allowed(
        exporter,
        "user with Export permission exports the probe DocType",
        lambda: _export(exporter, [ctx["admin_row"]]),
        endpoint=EXPORT,
        guards="frappe#42577",
    )
    ensure(
        ctx["admin_row"] in resp.text,
        "exported CSV contains the requested row",
        expected=f"row {ctx['admin_row']} in the CSV",
        actual=resp.text[:200],
        who=exporter,
        endpoint=EXPORT,
    )


def _owner_only_export(client: FrappeClient, ctx: dict) -> None:
    _need_probe(ctx)
    owner = personas.login_as(client, "owner_exporter")
    resp = expect_allowed(
        owner,
        "owner-only exporter exports a row they own",
        lambda: _export(owner, [ctx["owner_row"]]),
        endpoint=EXPORT,
        guards="frappe#42577",
    )
    ensure(
        ctx["owner_row"] in resp.text,
        "owner-only export contains the owner's row",
        expected=f"row {ctx['owner_row']} in the CSV",
        actual=resp.text[:200],
        who=owner,
        endpoint=EXPORT,
        guards="frappe#42577",
    )
    expect_denied(
        owner,
        "owner-only exporter exports a row someone else owns",
        lambda: _export(owner, [ctx["admin_row"]]),
        endpoint=EXPORT,
        guards="frappe#42577",
    )


def _boot_export_and_report_flags(client: FrappeClient, ctx: dict) -> None:
    """The UI hides Export and Report View from these boot lists (frappe#42577, #43044)."""
    _need_probe(ctx)
    expectations = [
        # persona, boot key, probe expected in list?
        ("reader", "can_export", False),
        ("reader", "can_get_report", False),
        ("exporter", "can_export", True),
        ("exporter", "can_export_owner_only", False),
        ("owner_exporter", "can_export", True),
        ("owner_exporter", "can_export_owner_only", True),
    ]
    for key, boot_key, want in expectations:
        who = personas.login_as(client, key)
        page = who.get_page("/desk")
        values = boot_list(page.text, boot_key)
        if values is None:
            raise SkipStep(
                f"no '{boot_key}' in the desk boot data for {who.persona.email} "
                f"(HTTP {page.status_code}); cannot check what the UI hides"
            )
        ensure(
            (RT_PROBE_DOCTYPE in values) == want,
            f"boot.{boot_key} {'includes' if want else 'excludes'} the probe DocType",
            expected=f"'{RT_PROBE_DOCTYPE}' {'in' if want else 'not in'} {boot_key}",
            actual=f"{boot_key} = {values[:15]}",
            who=who,
            endpoint="/desk (frappe.boot.user)",
            guards="frappe#42577" if "export" in boot_key else "frappe#43044",
            hint="the list view decides whether to show Export / Report View from this list",
        )


# ------------------------------------------------------------ link filters
def _link_filter_validation(client: FrappeClient, ctx: dict) -> None:
    """The form validates a Link through this call, passing the field's link filters."""
    sales = personas.login_as(client, "sales")
    method = "frappe.client.validate_link_and_fetch"
    filters = json.dumps({"name": ["in", RT_PROBE_COUNTRIES]})

    inside = expect_allowed(
        sales,
        "link validation accepts a value inside the link filter",
        lambda: sales.call(method, doctype="Country", docname="India", filters=filters),
        endpoint=method,
        guards="frappe#37608",
    )
    ensure(
        (inside or {}).get("name") == "India",
        "link validation accepts a value inside the link filter",
        expected="{'name': 'India'}",
        actual=inside,
        who=sales,
        endpoint=method,
        guards="frappe#37608",
    )
    outside = expect_allowed(
        sales,
        "link validation of a value outside the link filter",
        lambda: sales.call(method, doctype="Country", docname="Germany", filters=filters),
        endpoint=method,
        guards="frappe#37608",
    )
    ensure(
        not (outside or {}).get("name"),
        "link validation rejects a value outside the link filter",
        expected="empty result (value filtered out)",
        actual=outside,
        who=sales,
        endpoint=method,
        guards="frappe#37608",
    )


def _link_filter_on_save(client: FrappeClient, ctx: dict) -> None:
    """Informational: does saving bypass the link filter? Recorded, not failed.

    The release enforces link filters in the validation call above; the document
    save path doesn't re-check them. This step makes that visible in every report.
    """
    _need_probe(ctx)
    exporter = personas.login_as(client, "exporter")
    try:
        doc = exporter.insert(
            {"doctype": RT_PROBE_DOCTYPE, "title": "RT link filter probe", "country": "Germany"}
        )
    except FrappeAPIError:
        return  # refused on save: enforced end to end
    exporter.delete(RT_PROBE_DOCTYPE, doc["name"])
    raise SkipStep(
        "NOTE: a document saved over the API with a Link value outside the field's link "
        "filter (country=Germany) was accepted; link filters are enforced in the form's "
        "validation call only, not on save"
    )


# --------------------------------------------------------------- workflow
def _workflow_non_submittable(client: FrappeClient, ctx: dict) -> None:
    for state in ("RT Draft", "RT Done"):
        if not client.get_list("Workflow State", filters={"name": state}, fields=["name"], limit=1):
            client.insert({"doctype": "Workflow State", "workflow_state_name": state})
    try:
        _expect_workflow_rejected(client)
    finally:
        # If the server wrongly accepted it, don't leave it behind on the target.
        if client.get_list(
            "Workflow", filters={"name": "RT Non Submittable Probe"}, fields=["name"], limit=1
        ):
            client.delete("Workflow", "RT Non Submittable Probe")


def _expect_workflow_rejected(client: FrappeClient) -> None:
    expect_rejected(
        client,
        "Workflow on a non-submittable DocType with a Submitted state",
        lambda: client.insert(
            {
                "doctype": "Workflow",
                "workflow_name": "RT Non Submittable Probe",
                "document_type": "ToDo",
                "is_active": 0,
                "workflow_state_field": "workflow_state",
                "states": [
                    {"state": "RT Draft", "doc_status": "0", "allow_edit": "System Manager"},
                    {"state": "RT Done", "doc_status": "1", "allow_edit": "System Manager"},
                ],
                "transitions": [],
            }
        ),
        message="is not submittable",
        endpoint="POST /api/resource/Workflow",
        guards="frappe#37179",
    )


# -------------------------------------------------- permission manager / settings
def _permission_manager_refused(client: FrappeClient, ctx: dict) -> None:
    mgr = personas.login_as(client, "sales_mgr")
    base = "frappe.core.page.permission_manager.permission_manager"
    expect_denied(
        mgr,
        "non-System-Manager reads role permissions (DocType Settings > Permissions)",
        lambda: mgr.call(f"{base}.get_permissions", doctype="ToDo"),
        endpoint=f"{base}.get_permissions",
        guards="frappe#41005, frappe#41832",
    )
    expect_denied(
        mgr,
        "non-System-Manager adds a role permission row",
        lambda: mgr.call(f"{base}.add", parent="ToDo", role="Sales Manager", permlevel=0),
        endpoint=f"{base}.add",
        guards="frappe#41005, frappe#41832",
    )


def _print_settings_write_refused(client: FrappeClient, ctx: dict) -> None:
    sales = personas.login_as(client, "sales")
    expect_denied(
        sales,
        "Sales User changes Print Settings",
        lambda: sales.call(
            "frappe.client.set_value",
            doctype="Print Settings",
            name="Print Settings",
            fieldname="max_bulk_print_docs",
            value=1,
        ),
        endpoint="frappe.client.set_value (Print Settings)",
        guards="frappe@0b49110db2",
    )


# ----------------------------------------------------------------- kanban
def _kanban_card_moves(client: FrappeClient, ctx: dict) -> None:
    _need_probe(ctx)
    base = "frappe.desk.doctype.kanban_board.kanban_board"
    if not client.get_list(
        "Kanban Board", filters={"name": RT_KANBAN_BOARD}, fields=["name"], limit=1
    ):
        client.call(
            f"{base}.quick_kanban_board",
            doctype=RT_PROBE_DOCTYPE,
            board_name=RT_KANBAN_BOARD,
            field_name="status",
        )
    reader = personas.login_as(client, "reader")
    exporter = personas.login_as(client, "exporter")
    move = {
        "board_name": RT_KANBAN_BOARD,
        "docname": ctx["admin_row"],
        "from_colname": "Open",
        "to_colname": "Open",
        "old_index": 0,
        "new_index": 0,
    }
    expect_denied(
        reader,
        "read-only user moves a Kanban card",
        lambda: reader.call(f"{base}.update_order_for_single_card", **move),
        endpoint=f"{base}.update_order_for_single_card",
        guards="frappe@24a6500282",
    )
    expect_allowed(
        exporter,
        "user with write access moves a Kanban card",
        lambda: exporter.call(f"{base}.update_order_for_single_card", **move),
        endpoint=f"{base}.update_order_for_single_card",
        guards="frappe@24a6500282",
    )
    expect_allowed(
        exporter,
        "Kanban board accepts a native (non-string) order payload",
        lambda: exporter.session.post(
            f"{exporter.url}/api/method/{base}.update_order",
            json={"board_name": RT_KANBAN_BOARD, "order": {"Open": [ctx["admin_row"]]}},
            timeout=exporter.timeout,
        ).raise_for_status(),
        endpoint=f"{base}.update_order (JSON body)",
        guards="frappe@24a6500282",
    )


# ------------------------------------------------------------------ print
def _print_permissions(client: FrappeClient, ctx: dict) -> None:
    _need_probe(ctx)
    sales = personas.login_as(client, "sales")  # no access to the probe at all
    exporter = personas.login_as(client, "exporter")
    expect_denied(
        sales,
        "user without read or print access downloads a PDF",
        lambda: sales.call_raw(PDF, doctype=RT_PROBE_DOCTYPE, name=ctx["admin_row"]),
        endpoint=PDF,
    )
    expect_denied(
        sales,
        "bulk print of a document the user cannot read fails with a permission error",
        lambda: sales.call_raw(
            MULTI_PDF, doctype=RT_PROBE_DOCTYPE, name=json.dumps([ctx["admin_row"]])
        ),
        endpoint=MULTI_PDF,
        guards="frappe@fd76f9ab72",
        hint="before the fix the failure was only logged and an empty PDF returned",
    )
    html = expect_allowed(
        exporter,
        "user with print access renders the print view",
        lambda: exporter.call(PRINT_HTML, doc=RT_PROBE_DOCTYPE, name=ctx["admin_row"]),
        endpoint=PRINT_HTML,
    )
    ensure(
        "RT probe" in (html or {}).get("html", ""),
        "print view renders the document",
        expected="rendered HTML containing the document title",
        actual=str(html)[:200],
        who=exporter,
        endpoint=PRINT_HTML,
    )


def _bulk_print_limit(client: FrappeClient, ctx: dict) -> None:
    _need_probe(ctx)
    limit = int(client.get_doc("Print Settings", "Print Settings").get("max_bulk_print_docs") or 0)
    ensure(
        limit > 0,
        "Print Settings has a bulk print limit",
        expected="max_bulk_print_docs > 0 (100 by default)",
        actual=limit,
        endpoint="Print Settings",
    )
    exporter = personas.login_as(client, "exporter")
    names = [ctx["admin_row"]] * (limit + 1)
    expect_rejected(
        exporter,
        f"bulk print of {limit + 1} documents (limit {limit})",
        lambda: exporter.call_raw(MULTI_PDF, doctype=RT_PROBE_DOCTYPE, name=json.dumps(names)),
        message="Cannot generate PDF for more than",
        endpoint=MULTI_PDF,
    )


# -------------------------------------------------------- auth emails
def _queued_to(client: FrappeClient, email: str) -> int:
    rows = client.get_list(
        "Email Queue",
        filters=[["Email Queue Recipient", "recipient", "=", email]],
        fields=["name"],
        limit=500,
    )
    return len(rows)


def _reset_password(client: FrappeClient, email: str) -> None:
    anon = personas.guest(client)
    try:
        anon.call("frappe.core.doctype.user.user.reset_password", user=email)
    except FrappeAPIError as exc:
        if exc.status == 429:
            raise SkipStep("password reset is rate limited on this site right now") from exc
        raise


def _no_auth_email_for_disabled(client: FrappeClient, ctx: dict) -> None:
    if not client.get_list("User", filters={"name": RT_DISABLED_USER}, fields=["name"], limit=1):
        client.insert(
            {
                "doctype": "User",
                "email": RT_DISABLED_USER,
                "first_name": "RT Disabled",
                "send_welcome_email": 0,
                "enabled": 0,
            }
        )
    else:
        client.call(
            "frappe.client.set_value",
            doctype="User",
            name=RT_DISABLED_USER,
            fieldname="enabled",
            value=0,
        )

    # Control: an enabled user's reset must queue a mail, else the site doesn't
    # send these at all and the real check below would prove nothing.
    # The website persona: resetting a password ends that user's sessions, so the
    # control must be a user no other step is logged in as.
    enabled = personas.ensure_user(client, "website").email
    before = _queued_to(client, enabled)
    _reset_password(client, enabled)
    if _queued_to(client, enabled) <= before:
        raise SkipStep("this site queues no password-reset email even for an enabled user")

    before = _queued_to(client, RT_DISABLED_USER)
    _reset_password(client, RT_DISABLED_USER)
    after = _queued_to(client, RT_DISABLED_USER)
    ensure(
        after == before,
        "password reset requested for a disabled user sends no email",
        expected="no new Email Queue entry",
        actual=f"{after - before} new email(s) queued to {RT_DISABLED_USER}",
        endpoint="frappe.core.doctype.user.user.reset_password (as Guest)",
    )


# ------------------------------------------------------------ guest + portal
def _guest_desk_redirects_to_login(client: FrappeClient, ctx: dict) -> None:
    anon = personas.guest(client)
    for path in ("/desk", "/app/todo"):
        resp = anon.get_page(path)
        landed = resp.url
        ensure(
            "login" in landed or 'id="login' in resp.text or "page-card-head" in resp.text,
            f"logged-out visit to {path} lands on the login page",
            expected="login page",
            actual=f"HTTP {resp.status_code} at {landed}",
            who=anon,
            endpoint=f"GET {path}",
            guards="frappe#37412",
        )


def _portal_address_escaped(client: FrappeClient, ctx: dict) -> None:
    sales = personas.login_as(client, "sales")
    title = "RT XSS Address"
    existing = sales.get_list("Address", filters={"address_title": title}, fields=["name"], limit=1)
    if not existing:
        expect_allowed(
            sales,
            "Sales User creates an Address",
            lambda: sales.insert(
                {
                    "doctype": "Address",
                    "address_title": title,
                    "address_type": "Billing",
                    "address_line1": RT_ADDRESS_PAYLOAD,
                    "city": "Mumbai",
                    # State and PIN are mandatory for Indian addresses under India Compliance.
                    "state": "Maharashtra",
                    "pincode": "400001",
                    "country": "India",
                }
            ),
            endpoint="POST /api/resource/Address",
        )
    page = sales.get_page("/addresses")
    if page.status_code == 404:
        raise SkipStep("/addresses portal page not published on this site (HTTP 404)")
    ensure(
        page.status_code == 200,
        "portal address list page loads",
        expected="HTTP 200",
        actual=f"HTTP {page.status_code}",
        who=sales,
        endpoint="GET /addresses",
        guards="frappe#40180",
        hint="the portal address list itself errors",
    )
    ensure(
        '<img src=x onerror="alert(1)">' not in page.text,
        "portal address list escapes HTML stored in an address",
        expected="the payload shown as text (escaped)",
        actual="raw <img onerror> tag present in the page",
        who=sales,
        endpoint="GET /addresses",
        guards="frappe#40180",
        hint="stored XSS: address fields rendered unescaped in the portal",
    )


# --------------------------------------------- ordinary users, own documents
def _own_documents(client: FrappeClient, ctx: dict) -> None:
    """The hardening regressions that keep recurring: an ordinary user editing,
    saving and attaching to their own document. Repeated for several roles."""
    ran = []
    for key in ("sales", "purchase", "accounts", "hr"):
        try:
            who = personas.login_as(client, key)
        except SkipStep:
            continue  # role not installed on this site
        ran.append(key)
        todo = expect_allowed(
            who,
            "create own ToDo",
            lambda who=who: who.insert(
                {
                    "doctype": "ToDo",
                    "description": "RT-V16P own document",
                    "allocated_to": who.persona.email,
                }
            ),
            endpoint="POST /api/resource/ToDo",
        )["name"]
        expect_allowed(
            who,
            "set_value on own ToDo",
            lambda who=who, todo=todo: who.call(
                "frappe.client.set_value",
                doctype="ToDo",
                name=todo,
                fieldname="description",
                value="RT-V16P edited",
            ),
            endpoint="frappe.client.set_value",
            guards="frappe@e197a37a",
        )
        doc = who.get_doc("ToDo", todo)
        doc["priority"] = "High"
        expect_allowed(
            who,
            "client.save on own ToDo",
            lambda who=who, doc=doc: who.call(
                "frappe.client.save", doc=json.dumps(doc, default=str)
            ),
            endpoint="frappe.client.save",
            guards="frappe@e197a37a",
        )
        expect_allowed(
            who,
            "attach a file to own ToDo",
            lambda who=who, todo=todo: who.upload(
                {"doctype": "ToDo", "docname": todo, "is_private": 1},
                "rt-own.txt",
                b"release test attachment",
            ),
            endpoint="upload_file",
            guards="frappe@8e8ef9d0",
        )
    if not ran:
        raise SkipStep("none of the Sales/Purchase/Accounts/HR roles exist on this site")


class V16PSecuritySuite(ReleaseSuite):
    name = "v16p_security"
    required_app = "frappe"
    description = (
        "version-16-polished permission fixes, per role: export, report view, link filters, "
        "workflow, permission manager, kanban, print, auth emails, guest redirect, portal "
        "escaping, and ordinary users on their own documents."
    )
    guards: ClassVar[list[str]] = [
        "frappe#42577",
        "frappe#43044",
        "frappe#37608",
        "frappe#37179",
        "frappe#41005",
        "frappe#41832",
        "frappe#37412",
        "frappe#40180",
        "frappe@fd76f9ab72",
        "frappe@0b49110db2",
        "frappe@24a6500282",
    ]

    # Each check stands alone; one failure must not hide the others.
    independent_steps = True

    def precheck(self, client: FrappeClient) -> str | None:
        return polished_precheck(client)

    def build_steps(self, versions: Versions) -> list[Step]:
        return [
            Step("setup: probe DocType + role users", _setup, blocks_on_fail=True),
            Step("export refused without Export permission [reader]", _export_refused_for_reader),
            Step("export allowed with Export permission [exporter]", _export_allowed_for_exporter),
            Step("owner-only export: own rows only [owner_exporter]", _owner_only_export),
            Step(
                "UI boot hides Export / Report View [reader, exporter, owner_exporter]",
                _boot_export_and_report_flags,
            ),
            Step("link filter enforced in link validation [sales]", _link_filter_validation),
            Step("link filter on document save (informational) [exporter]", _link_filter_on_save),
            Step(
                "workflow refuses Submitted state on non-submittable DocType",
                _workflow_non_submittable,
            ),
            Step("permission manager refused [sales_mgr]", _permission_manager_refused),
            Step("Print Settings write refused [sales]", _print_settings_write_refused),
            Step("kanban card move needs write [reader vs exporter]", _kanban_card_moves),
            Step("print / bulk print permissions [sales vs exporter]", _print_permissions),
            Step("bulk print limit enforced [exporter]", _bulk_print_limit),
            Step("no auth email to a disabled user [guest]", _no_auth_email_for_disabled),
            Step("logged-out desk visit goes to login [guest]", _guest_desk_redirects_to_login),
            Step("portal address list escapes HTML [sales]", _portal_address_escaped),
            Step(
                "own documents: edit, save, attach [sales, purchase, accounts, hr]", _own_documents
            ),
        ]
