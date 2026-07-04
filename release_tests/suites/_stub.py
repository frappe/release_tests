"""Shared scaffolding for not-yet-implemented app suites.

Each stub suite is gated on its app and runs a single "app reachable" step that
lists a representative DocType. When the app isn't installed the suite cleanly
auto-skips; when it IS installed, the step gives a minimal liveness signal until
a full suite is written. Fill in real flows by replacing ``build_steps``.
"""

from __future__ import annotations

from ..client import FrappeClient
from ..gating import Versions
from .base import ReleaseSuite, Step


def _reachable(doctype: str):
    def step(client: FrappeClient, ctx: dict) -> None:
        # Confirm the app migrated its schema by checking the probe DocType is
        # registered. We query the DocType master (always a real table) rather
        # than listing the doctype itself, because Single doctypes (e.g. "GST
        # Settings") have no list table and would 500 on /api/resource/<name>.
        found = client.get_list("DocType", filters={"name": doctype}, fields=["name"], limit=1)
        if not found:
            raise AssertionError(f"DocType {doctype!r} not found — app not fully migrated?")

    return step


class StubSuite(ReleaseSuite):
    """Base for stub suites: set ``name``, ``required_app`` and ``probe_doctype``."""

    probe_doctype: str = ""

    @property
    def description(self) -> str:  # type: ignore[override]
        return f"Stub: reachability probe ({self.probe_doctype}). Expand into real flows later."

    def build_steps(self, versions: Versions) -> list[Step]:
        return [Step(f"{self.required_app} reachable ({self.probe_doctype})",
                     _reachable(self.probe_doctype))]
