"""Webshop smoke suite (stub — auto-skips when 'webshop' is absent)."""

from __future__ import annotations

from ._stub import StubSuite


class WebshopSuite(StubSuite):
    name = "webshop"
    required_app = "webshop"
    probe_doctype = "Website Item"
