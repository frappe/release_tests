"""HRMS org hierarchy: an Employee and a second Employee that reports to them."""

from __future__ import annotations

from .. import factories
from ..client import FrappeClient
from ..gating import Versions
from .base import ReleaseSuite, Step


def _hierarchy(client: FrappeClient, ctx: dict) -> None:
    ctx["company"] = factories.ensure_company(client)
    ctx["manager"] = factories.ensure_employee(client, ctx["company"])
    ctx["report"] = factories.ensure_employee2(client, ctx["company"], ctx["manager"])


def _verify_reports_to(client: FrappeClient, ctx: dict) -> None:
    doc = client.get_doc("Employee", ctx["report"])
    if doc.get("reports_to") != ctx["manager"]:
        raise AssertionError(f"reports_to is {doc.get('reports_to')!r}, expected {ctx['manager']!r}")


class HRMSOrgSuite(ReleaseSuite):
    name = "hrms_org"
    required_app = "hrms"
    description = "Org hierarchy: create a manager Employee and a report whose reports_to points to the manager."

    def build_steps(self, versions: Versions) -> list[Step]:
        return [
            Step("create manager + report employees", _hierarchy),
            Step("verify reports_to link", _verify_reports_to),
        ]
