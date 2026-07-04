"""Frappe Learning release suite (stub — auto-skips when 'lms' is absent)."""

from __future__ import annotations

from ._stub import StubSuite


class LearningSuite(StubSuite):
    name = "learning"
    required_app = "lms"
    probe_doctype = "LMS Course"
