"""version-16-polished Frappe features, over the API.

What the server side of the release's big features does: the new navigation
records, saved list layouts (per user), Insert-or-Update data import, chunked
uploads, DocType-scoped email templates, and the Typst print renderer. What only
the browser can show (routing, the view switcher, dialogs) is in the Cypress specs.
"""

from __future__ import annotations

import csv
import io
import json
import time
from typing import ClassVar

from .. import personas
from ..checks import ensure, expect_allowed, expect_denied
from ..client import FrappeAPIError, FrappeClient
from ..gating import Versions
from ._v16p import import_errors, polished_precheck
from .base import ReleaseSuite, SkipStep, Step

# Print Heading: a core DocType that allows import and is named by its own field.
IMPORT_DOCTYPE = "Print Heading"
RT_HEADING_EXISTING = "RT Import Existing"
RT_HEADING_NEW = "RT Import New"
IMPORT_TIMEOUT_S = 90


def _navigation_records(client: FrappeClient, ctx: dict) -> None:
    sidebars = client.get_list("Sidebar", fields=["name", "module"], limit=500)
    ensure(
        len(sidebars) > 0,
        "per-module Sidebars exist",
        expected="at least one Sidebar record",
        actual="0 Sidebar records",
        endpoint="Sidebar",
        hint="new navigation: every module shows its sidebar from these records",
    )
    ctx["sidebar_count"] = len(sidebars)
    try:
        who = personas.login_as(client, "sales")
    except SkipStep:
        return
    page = who.get_page("/desk")
    ensure(
        page.status_code == 200 and "frappe.boot" in page.text,
        "desk loads for an ordinary user",
        expected="HTTP 200 with the desk boot",
        actual=f"HTTP {page.status_code} at {page.url}",
        who=who,
        endpoint="GET /desk",
    )


def _list_layout_per_user(client: FrappeClient, ctx: dict) -> None:
    """Saved list layouts: saved with its route signature, private to its owner."""
    try:
        owner = personas.login_as(client, "sales")
        other = personas.login_as(client, "purchase")
    except SkipStep as exc:
        raise SkipStep(f"needs Sales User and Purchase User roles: {exc}") from exc
    name_ = "RT saved layout"
    existing = owner.get_list(
        "List Filter",
        filters={"filter_name": name_, "for_user": owner.persona.email},
        fields=["name"],
        limit=1,
    )
    if existing:
        layout = existing[0]["name"]
    else:
        layout = expect_allowed(
            owner,
            "save a list layout (filters, columns, sort) on ToDo",
            lambda: owner.insert(
                {
                    "doctype": "List Filter",
                    "filter_name": name_,
                    "reference_doctype": "ToDo",
                    "for_user": owner.persona.email,
                    "filters": json.dumps([["ToDo", "status", "=", "Open"]]),
                    "columns": json.dumps(["description", "status", "priority"]),
                    "sort_field": "modified",
                    "sort_order": "desc",
                }
            ),
            endpoint="POST /api/resource/List Filter",
        )["name"]
    saved = owner.get_doc("List Filter", layout)
    ensure(
        bool(saved.get("route_signature")),
        "saved list layout gets its route signature",
        expected="route_signature set (ties the layout to the list it was saved on)",
        actual=saved.get("route_signature"),
        who=owner,
        endpoint="List Filter",
    )
    seen = other.get_list("List Filter", filters={"name": layout}, fields=["name"], limit=1)
    ensure(
        not seen,
        "another user cannot see someone's private list layout",
        expected="not listed",
        actual=f"listed: {seen}",
        who=other,
        endpoint="GET /api/resource/List Filter",
        hint="personal layouts leaking to other users",
    )
    expect_denied(
        other,
        "another user edits someone's private list layout",
        lambda: other.call(
            "frappe.client.set_value",
            doctype="List Filter",
            name=layout,
            fieldname="sort_order",
            value="asc",
        ),
        endpoint="frappe.client.set_value (List Filter)",
    )


def _insert_or_update_import(client: FrappeClient, ctx: dict) -> None:
    """Data import in the new Insert-or-Update mode: one row updates, one inserts."""
    stamp = str(int(time.time()))
    if client.get_list(
        IMPORT_DOCTYPE, filters={"name": RT_HEADING_EXISTING}, fields=["name"], limit=1
    ):
        client.call(
            "frappe.client.set_value",
            doctype=IMPORT_DOCTYPE,
            name=RT_HEADING_EXISTING,
            fieldname="description",
            value="old",
        )
    else:
        client.insert(
            {"doctype": IMPORT_DOCTYPE, "print_heading": RT_HEADING_EXISTING, "description": "old"}
        )
    if client.get_list(IMPORT_DOCTYPE, filters={"name": RT_HEADING_NEW}, fields=["name"], limit=1):
        client.delete(IMPORT_DOCTYPE, RT_HEADING_NEW)

    buf = io.StringIO()
    writer = csv.writer(buf)
    writer.writerow(["ID", "Print Heading", "Description"])
    writer.writerow([RT_HEADING_EXISTING, RT_HEADING_EXISTING, f"updated {stamp}"])
    writer.writerow(["", RT_HEADING_NEW, f"inserted {stamp}"])
    upload = client.upload(
        {"is_private": 1}, f"rt-heading-import-{stamp}.csv", buf.getvalue().encode()
    )
    file_url = upload.json()["message"]["file_url"]

    data_import = client.insert(
        {
            "doctype": "Data Import",
            "reference_doctype": IMPORT_DOCTYPE,
            "import_type": "Insert or Update Records",
            "import_file": file_url,
        }
    )["name"]
    client.call(
        "frappe.core.doctype.data_import.data_import.form_start_import", data_import=data_import
    )

    status = "Pending"
    deadline = time.monotonic() + IMPORT_TIMEOUT_S
    while time.monotonic() < deadline:
        status = client.get_doc("Data Import", data_import).get("status")
        if status not in ("Pending", "In Progress"):
            break
        time.sleep(3)
    if status in ("Pending", "In Progress"):
        raise SkipStep(
            f"Data Import {data_import} still {status} after {IMPORT_TIMEOUT_S}s — "
            "no background worker is processing imports on this site"
        )
    ensure(
        status == "Success",
        "Insert-or-Update import finishes successfully",
        expected="Success",
        actual=f"{status} — {import_errors(client, data_import)}",
        endpoint="Data Import",
    )
    updated = client.get_doc(IMPORT_DOCTYPE, RT_HEADING_EXISTING).get("description")
    ensure(
        updated == f"updated {stamp}",
        "existing row updated by Insert-or-Update",
        expected=f"description 'updated {stamp}'",
        actual=updated,
        endpoint=f"Data Import {data_import}",
    )
    inserted = client.get_list(
        IMPORT_DOCTYPE, filters={"name": RT_HEADING_NEW}, fields=["name"], limit=1
    )
    ensure(
        bool(inserted),
        "new row inserted by Insert-or-Update",
        expected=f"{IMPORT_DOCTYPE} '{RT_HEADING_NEW}' created",
        actual="not created",
        endpoint=f"Data Import {data_import}",
    )


def _chunked_upload(client: FrappeClient, ctx: dict) -> None:
    """Large files go up in chunks; the server stitches them back together."""
    who = personas.login_as(client, "sales")
    todo = who.insert(
        {
            "doctype": "ToDo",
            "description": "RT-V16P chunked upload",
            "allocated_to": who.persona.email,
        }
    )["name"]
    content = bytes(range(256)) * 400  # 102,400 bytes
    chunk = 40_000
    parts = [content[i : i + chunk] for i in range(0, len(content), chunk)]
    stamp = int(time.time())
    last = None
    for index, part in enumerate(parts):
        last = expect_allowed(
            who,
            f"upload chunk {index + 1} of {len(parts)}",
            lambda index=index, part=part: who.upload(
                {
                    "doctype": "ToDo",
                    "docname": todo,
                    "is_private": 1,
                    "chunk_index": index,
                    "total_chunk_count": len(parts),
                    "chunk_byte_offset": index * chunk,
                    "total_file_size": len(content),
                },
                f"rt-chunked-{stamp}.bin",
                part,
            ),
            endpoint="upload_file (chunked)",
        )
    message = (last.json() or {}).get("message") or {}
    ensure(
        int(message.get("file_size") or 0) == len(content),
        "chunked upload stored the whole file",
        expected=f"{len(content)} bytes",
        actual=f"{message.get('file_size')} bytes ({message.get('file_url')})",
        who=who,
        endpoint="upload_file (chunked)",
        hint="chunks lost or written at the wrong offset",
    )


def _email_template_scoped(client: FrappeClient, ctx: dict) -> None:
    name = "RT ToDo Template"
    if not client.get_list("Email Template", filters={"name": name}, fields=["name"], limit=1):
        client.insert(
            {
                "doctype": "Email Template",
                "name": name,
                "__newname": name,
                "subject": "RT {{ doc.name }}",
                "response": "Release test template",
                "reference_doctype": "ToDo",
            }
        )
    scoped = client.get_list(
        "Email Template",
        filters={"reference_doctype": "ToDo", "name": name},
        fields=["name"],
        limit=1,
    )
    ensure(
        bool(scoped),
        "Email Template can be scoped to a DocType",
        expected=f"'{name}' listed for reference_doctype = ToDo",
        actual="not found",
        endpoint="Email Template",
    )


def _meta_flags(client: FrappeClient, ctx: dict) -> None:
    """New schema: DocType.deprecated and Report.documentation_url exist and are queryable."""
    for doctype, field in (("DocType", "deprecated"), ("Report", "documentation_url")):
        try:
            client.get_list(doctype, fields=["name", field], limit=1)
        except FrappeAPIError as exc:
            ensure(
                False,
                f"{doctype}.{field} exists",
                expected="field present",
                actual=f"HTTP {exc.status}: {str(exc.server_messages)[:150]}",
                endpoint=doctype,
            )


def _typst_pdf(client: FrappeClient, ctx: dict) -> None:
    todo = client.insert({"doctype": "ToDo", "description": "RT-V16P Typst print"})["name"]
    try:
        resp = client.call_raw(
            "frappe.utils.print_format.download_pdf",
            doctype="ToDo",
            name=todo,
            pdf_generator="Typst",
        )
    except FrappeAPIError as exc:
        if "typst" in str(exc).lower() and exc.status and exc.status >= 500:
            raise SkipStep(
                f"Typst renderer not available on this server: {str(exc)[:150]}"
            ) from exc
        raise
    ensure(
        resp.content[:4] == b"%PDF",
        "Typst renders a PDF",
        expected="a PDF (starts with %PDF)",
        actual=f"{resp.headers.get('Content-Type')} — {resp.content[:40]!r}",
        endpoint="download_pdf (pdf_generator=Typst)",
    )


class V16PFrappeFeaturesSuite(ReleaseSuite):
    name = "v16p_frappe_features"
    required_app = "frappe"
    description = (
        "version-16-polished Frappe features over the API: navigation records, per-user list "
        "layouts, Insert-or-Update import, chunked upload, scoped email templates, new meta "
        "fields, Typst PDF."
    )
    guards: ClassVar[list[str]] = ["frappe#39887", "frappe#40979", "frappe#40533"]

    # Each check stands alone; one failure must not hide the others.
    independent_steps = True

    def precheck(self, client: FrappeClient) -> str | None:
        return polished_precheck(client)

    def build_steps(self, versions: Versions) -> list[Step]:
        return [
            Step("new navigation: Sidebars exist, desk loads [sales]", _navigation_records),
            Step("saved list layout is per user [sales vs purchase]", _list_layout_per_user),
            Step("data import: Insert or Update", _insert_or_update_import),
            Step("chunked upload of a large file [sales]", _chunked_upload),
            Step("email template scoped to a DocType", _email_template_scoped),
            Step("DocType.deprecated and Report.documentation_url", _meta_flags),
            Step("Typst renders a PDF", _typst_pdf),
        ]
