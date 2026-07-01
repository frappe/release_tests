"""Rerun-safety helpers.

Transaction suites create submitted documents that aren't naturally idempotent
(e.g. a Leave Allocation for the same employee/period collides on a second run).
``purge`` clears prior smoke-created docs so a suite can start clean every time.
"""

from __future__ import annotations

from .client import FrappeAPIError, FrappeClient


def purge(client: FrappeClient, doctype: str, filters: dict) -> None:
    """Cancel (if submitted) and delete every ``doctype`` matching ``filters``.

    Best-effort: individual failures (already gone, blocked by a link) are
    ignored so cleanup never fails the run itself.
    """
    rows = client.get_list(doctype, filters=filters, fields=["name", "docstatus"], limit=100)
    for row in rows:
        name = row["name"]
        try:
            if row.get("docstatus") == 1:
                client.cancel(doctype, name)
            client.delete(doctype, name)
        except FrappeAPIError:
            continue
