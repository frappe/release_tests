"""KSA Compliance release suite (stub — auto-skips when absent)."""

from __future__ import annotations

from ._stub import StubSuite


class KSAComplianceSuite(StubSuite):
    name = "ksa_compliance"
    required_app = "ksa_compliance"
    probe_doctype = "ZATCA Business Settings"
