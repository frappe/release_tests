"""Frappe Helpdesk smoke suite (stub — auto-skips when 'helpdesk' is absent)."""

from __future__ import annotations

from ._stub import StubSuite


class HelpdeskSuite(StubSuite):
    name = "helpdesk"
    required_app = "helpdesk"
    probe_doctype = "HD Ticket"
