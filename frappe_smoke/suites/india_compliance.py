"""India Compliance smoke suite (stub — auto-skips when absent)."""

from __future__ import annotations

from ._stub import StubSuite


class IndiaComplianceSuite(StubSuite):
    name = "india_compliance"
    required_app = "india_compliance"
    probe_doctype = "GST Settings"
