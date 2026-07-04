"""Frappe HR release suite: create an Employee and confirm HR doctypes are live."""

from __future__ import annotations

from .. import factories
from ..client import FrappeClient
from ..gating import Versions
from .base import ReleaseSuite, Step


def _employee(client: FrappeClient, ctx: dict) -> None:
    ctx["company"] = factories.ensure_company(client)
    ctx["employee"] = factories.ensure_employee(client, ctx["company"])


def _read_employee(client: FrappeClient, ctx: dict) -> None:
    doc = client.get_doc("Employee", ctx["employee"])
    if doc.get("status") != "Active":
        raise AssertionError(f"employee not Active: {doc.get('status')}")


def _leave_types_present(client: FrappeClient, ctx: dict) -> None:
    # HRMS ships standard Leave Types via fixtures; their presence confirms the
    # app's data layer migrated correctly.
    leave_types = client.get_list("Leave Type", fields=["name"], limit=1)
    if not leave_types:
        raise AssertionError("no Leave Type records found — HRMS fixtures missing?")


class HRMSSuite(ReleaseSuite):
    name = "hrms"
    required_app = "hrms"
    description = "HR basics: create an Employee, read it back Active, and confirm Leave Type fixtures migrated."

    def build_steps(self, versions: Versions) -> list[Step]:
        return [
            Step("create Employee", _employee),
            Step("read Employee", _read_employee),
            Step("Leave Type fixtures present", _leave_types_present),
        ]
