"""Frappe Insights: build a Workbook that queries Sales Invoice, then charts + a dashboard.

Insights v3 keeps queries/charts/dashboards inside a Workbook. This suite creates
a Workbook, a builder query whose source is the ``tabSales Invoice`` table, two
charts over that query, and a dashboard laying them out — the core authoring
flow. All idempotent (keyed on title), so re-runs stay clean.

Needs ERPNext too (the query targets Sales Invoice), so it only applies when both
apps are installed.
"""

from __future__ import annotations

from .. import factories
from ..client import FrappeClient
from ..gating import Versions
from .base import ReleaseSuite, Step

_SALES_INVOICE_TABLE = "tabSales Invoice"


def _workbook(client: FrappeClient, ctx: dict) -> None:
    ctx["workbook"] = factories.ensure_insights_workbook(client)


def _query(client: FrappeClient, ctx: dict) -> None:
    ctx["query"] = factories.ensure_insights_query(client, ctx["workbook"], _SALES_INVOICE_TABLE)


def _charts(client: FrappeClient, ctx: dict) -> None:
    ctx["charts"] = [
        factories.ensure_insights_chart(client, ctx["workbook"], ctx["query"], "Release SI Bar", "Bar"),
        factories.ensure_insights_chart(client, ctx["workbook"], ctx["query"], "Release SI Total", "Number"),
    ]


def _dashboard(client: FrappeClient, ctx: dict) -> None:
    ctx["dashboard"] = factories.ensure_insights_dashboard(client, ctx["workbook"], ctx["charts"])


def _verify(client: FrappeClient, ctx: dict) -> None:
    dash = client.get_doc("Insights Dashboard v3", ctx["dashboard"])
    if not dash.get("name"):
        raise AssertionError("Insights dashboard was not created")
    if not ctx.get("query"):
        raise AssertionError("Insights query on Sales Invoice was not created")


class InsightsSuite(ReleaseSuite):
    name = "insights"
    required_app = "insights"
    description = "Insights: Workbook -> query on Sales Invoice -> charts -> dashboard."

    def applies(self, versions: Versions) -> bool:
        # The query sources the Sales Invoice table, so ERPNext must be present too.
        return "insights" in versions and "erpnext" in versions

    def build_steps(self, versions: Versions) -> list[Step]:
        return [
            Step("create Insights Workbook", _workbook),
            Step("create query on Sales Invoice", _query),
            Step("create charts", _charts),
            Step("create dashboard", _dashboard),
            Step("verify dashboard + query", _verify),
        ]
