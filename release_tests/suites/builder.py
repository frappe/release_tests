"""Frappe Builder release suite (stub — auto-skips when 'builder' is absent)."""

from __future__ import annotations

from ._stub import StubSuite


class BuilderSuite(StubSuite):
    name = "builder"
    required_app = "builder"
    probe_doctype = "Builder Page"
