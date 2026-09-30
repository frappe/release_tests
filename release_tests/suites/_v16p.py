"""Shared setup for the ``v16p_*`` suites (Frappe/ERPNext/HRMS version-16-polished).

Two things every polished suite needs:

* :func:`polished_precheck` — ``version-16`` and ``version-16-polished`` both report
  16.x, so version gating can't tell them apart. The polished release ships a new
  per-module ``Sidebar`` DocType that plain v16 doesn't have; its presence is the
  marker. On a plain v16 site the suites skip with that reason instead of failing.
* :func:`ensure_perm_probe` — a test-only custom DocType whose permission rows
  grant read / report / export / print to the probe roles in
  :mod:`release_tests.personas`. Permission checks run against it so no real
  DocType's permissions are ever changed on the target. Creating it writes schema,
  so it needs the target's ``allow_customisations`` opt-in.
"""

from __future__ import annotations

import json

from ..client import FrappeClient
from ..personas import RT_EXPORTER_ROLE, RT_OWNER_EXPORTER_ROLE, RT_READER_ROLE, ensure_custom_roles
from .base import SkipStep

POLISHED_MARKER_DOCTYPE = "Sidebar"

RT_PROBE_DOCTYPE = "RT Perm Probe"
RT_PROBE_ADMIN_TITLE = "RT probe (created by Administrator)"
# Allowed values for the probe's Country link — anything else is outside its link filter.
RT_PROBE_COUNTRIES = ["India", "France"]

_ALL = {"read": 1, "write": 1, "create": 1, "delete": 1, "report": 1, "export": 1, "print": 1}
_PROBE_PERMISSIONS = [
    {"role": "System Manager", **_ALL},
    # Read only: no report view, no export, no print right (print still follows read).
    {"role": RT_READER_ROLE, "read": 1},
    {
        "role": RT_EXPORTER_ROLE,
        "read": 1,
        "write": 1,
        "create": 1,
        "report": 1,
        "export": 1,
        "print": 1,
    },
    # Export only on rows the user owns: the case frappe#42577 split out as
    # ``can_export_owner_only``.
    {"role": RT_OWNER_EXPORTER_ROLE, "read": 1, "write": 1, "create": 1, "report": 1},
    {"role": RT_OWNER_EXPORTER_ROLE, "if_owner": 1, "read": 1, "export": 1},
]

_PROBE_DOCTYPE = {
    "doctype": "DocType",
    "name": RT_PROBE_DOCTYPE,
    "module": "Custom",
    "custom": 1,
    "autoname": "hash",
    "fields": [
        {"fieldname": "title", "fieldtype": "Data", "label": "Title", "reqd": 1, "in_list_view": 1},
        {
            "fieldname": "status",
            "fieldtype": "Select",
            "label": "Status",
            "options": "Open\nClosed",
            "default": "Open",
            "in_list_view": 1,
        },
        {
            "fieldname": "country",
            "fieldtype": "Link",
            "label": "Country",
            "options": "Country",
            "link_filters": json.dumps([["Country", "name", "in", RT_PROBE_COUNTRIES]]),
        },
    ],
    "permissions": _PROBE_PERMISSIONS,
}


def polished_precheck(client: FrappeClient) -> str | None:
    """Skip reason when the target isn't running version-16-polished, else None."""
    found = client.get_list(
        "DocType", filters={"name": POLISHED_MARKER_DOCTYPE}, fields=["name"], limit=1
    )
    if found:
        return None
    return (
        f"not a version-16-polished site (no '{POLISHED_MARKER_DOCTYPE}' DocType, "
        "which ships only in polished)"
    )


def _perm_key(row: dict) -> tuple:
    return (row.get("role"), int(row.get("if_owner") or 0)) + tuple(
        int(row.get(k) or 0) for k in sorted(_ALL)
    )


def ensure_perm_probe(client: FrappeClient) -> str:
    """Get-or-create the probe DocType, and restore its permission rows if drifted.

    Raises SkipStep when the target hasn't opted in to customisations.
    """
    if not client.allow_customisations:
        raise SkipStep(
            "needs allow_customisations = true on this target: the permission probe "
            f"is a custom DocType ('{RT_PROBE_DOCTYPE}')"
        )
    ensure_custom_roles(client)
    existing = client.get_list(
        "DocType", filters={"name": RT_PROBE_DOCTYPE}, fields=["name"], limit=1
    )
    if not existing:
        client.insert(dict(_PROBE_DOCTYPE))
        return RT_PROBE_DOCTYPE

    doc = client.get_doc("DocType", RT_PROBE_DOCTYPE)
    have = sorted(_perm_key(r) for r in doc.get("permissions") or [])
    want = sorted(_perm_key(r) for r in _PROBE_PERMISSIONS)
    if have != want:
        doc["permissions"] = [dict(r) for r in _PROBE_PERMISSIONS]
        client.call("frappe.client.save", doc=json.dumps(doc, default=str))
    return RT_PROBE_DOCTYPE


def ensure_admin_probe_row(client: FrappeClient) -> str:
    """A probe row owned by the target's admin user — i.e. not by any persona."""
    rows = client.get_list(
        RT_PROBE_DOCTYPE, filters={"title": RT_PROBE_ADMIN_TITLE}, fields=["name"], limit=1
    )
    if rows:
        return rows[0]["name"]
    return client.insert(
        {
            "doctype": RT_PROBE_DOCTYPE,
            "title": RT_PROBE_ADMIN_TITLE,
            "status": "Open",
            "country": "India",
        }
    )["name"]


def boot_list(page_html: str, key: str) -> list[str] | None:
    """Pull one list (e.g. ``can_export``) out of the ``frappe.boot`` JSON embedded in
    a desk page. None when the page has no boot (not logged in, or markup changed)."""
    import re

    match = re.search(rf'"{re.escape(key)}"\s*:\s*(\[[^\]]*\])', page_html)
    if not match:
        return None
    try:
        return json.loads(match.group(1))
    except ValueError:
        return None


def import_errors(client: FrappeClient, data_import: str) -> str:
    """The failed rows of a Data Import, as '<row>: <reason>' — so a partial import
    says which row broke and why, not just "Partial Success"."""
    try:
        logs = client.call(
            "frappe.core.doctype.data_import.data_import.get_import_logs",
            data_import=data_import,
            status="failed",
        )
    except Exception as exc:  # noqa: BLE001 - reporting aid only; never mask the real result
        return f"see Data Import {data_import} (row log unavailable: {str(exc)[:80]})"
    rows = []
    for log in logs or []:
        reason = _log_reason(log)
        rows.append(f"rows {log.get('row_indexes')}: {reason}")
    detail = "; ".join(rows[:5]) or "no failed-row log"
    return f"Data Import {data_import}: {detail}"


def _log_reason(log: dict) -> str:
    """A Data Import Log row's reason: its messages, else the exception's last line."""
    messages = log.get("messages") or ""
    try:
        parsed = json.loads(messages) if messages else []
    except (TypeError, ValueError):
        parsed = [messages]
    texts = []
    for item in parsed if isinstance(parsed, list) else [parsed]:
        if isinstance(item, str) and item.startswith("{"):
            try:
                item = json.loads(item).get("message", item)
            except ValueError:
                pass
        if item and str(item).strip() not in ("[]", "{}", '""'):
            texts.append(str(item))
    if texts:
        return " ".join(texts)[:200]
    lines = [ln.strip() for ln in (log.get("exception") or "").splitlines() if ln.strip()]
    return (lines[-1] if lines else "no reason recorded")[:200]
