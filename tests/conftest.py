"""Shared test fixtures: a fake FrappeClient so tests need no live site."""

from __future__ import annotations

import pytest


class FakeClient:
    """In-memory stand-in for FrappeClient used by runner/suite tests.

    Records calls and serves canned ``get_versions``; doc operations write to an
    in-memory store so CRUD round-trips behave plausibly.
    """

    def __init__(self, versions: dict | None = None):
        self._versions = versions or {}
        self._store: dict[str, dict] = {}
        self._counter = 0
        self.calls: list[tuple] = []
        self.logged_in_user = "Administrator"

    def get_versions(self):
        self.calls.append(("get_versions",))
        return self._versions

    def call(self, method, **kwargs):
        self.calls.append(("call", method, kwargs))
        if method == "frappe.auth.get_logged_user":
            return self.logged_in_user
        if method == "frappe.client.delete":
            self._store.pop(f"{kwargs['doctype']}:{kwargs['name']}", None)
            return None
        return {}

    def insert(self, doc):
        self.calls.append(("insert", doc.get("doctype")))
        self._counter += 1
        name = doc.get("name") or f"{doc['doctype']}-{self._counter:04d}"
        stored = {**doc, "name": name, "docstatus": doc.get("docstatus", 0)}
        self._store[f"{doc['doctype']}:{name}"] = stored
        return stored

    def submit(self, doc):
        self.calls.append(("submit", doc.get("doctype")))
        doc = {**doc, "docstatus": 1}
        self._store[f"{doc['doctype']}:{doc['name']}"] = doc
        return doc

    def get_doc(self, doctype, name):
        self.calls.append(("get_doc", doctype, name))
        return self._store.get(f"{doctype}:{name}", {})

    def get_list(self, doctype, *, filters=None, fields=None, limit=20):
        self.calls.append(("get_list", doctype))
        return [v for k, v in self._store.items() if k.startswith(f"{doctype}:")][:limit]


@pytest.fixture
def fake_client():
    return FakeClient
