"""Shared scaffolding for not-yet-implemented app suites.

Each stub suite is gated on its app and runs a single "app reachable" step that
lists a representative DocType. When the app isn't installed the suite cleanly
auto-skips; when it IS installed, the step gives a minimal liveness signal until
a full suite is written. Fill in real flows by replacing ``build_steps``.
"""

from __future__ import annotations

from ..client import FrappeClient
from ..gating import Versions
from .base import SmokeSuite, Step


def _reachable(doctype: str):
    def step(client: FrappeClient, ctx: dict) -> None:
        # A successful list call proves the doctype migrated and the app's data
        # layer responds — a deliberately shallow check for a stub.
        client.get_list(doctype, fields=["name"], limit=1)

    return step


class StubSuite(SmokeSuite):
    """Base for stub suites: set ``name``, ``required_app`` and ``probe_doctype``."""

    probe_doctype: str = ""

    def build_steps(self, versions: Versions) -> list[Step]:
        return [Step(f"{self.required_app} reachable ({self.probe_doctype})",
                     _reachable(self.probe_doctype))]
