"""Frappe Insights smoke suite (stub — auto-skips when 'insights' is absent)."""

from __future__ import annotations

from ._stub import StubSuite


class InsightsSuite(StubSuite):
    name = "insights"
    required_app = "insights"
    probe_doctype = "Insights Data Source"
