"""Frappe CRM smoke suite (stub — auto-skips when 'crm' is not installed)."""

from __future__ import annotations

from ._stub import StubSuite


class CRMSuite(StubSuite):
    name = "crm"
    required_app = "crm"
    probe_doctype = "CRM Lead"
