"""Frappe Builder: author a page (hero + cards) and publish it.

Flow: create a Builder Page whose ``blocks`` hold a hero section and a row of
cards -> publish it -> confirm the published route renders. Idempotent (keyed on
route).

NOTE: written against the Builder Page schema but not yet validated end-to-end in
this environment (the ``builder`` app isn't present here), and the ``blocks``
component shape is Builder-version-specific. It auto-skips where Builder isn't
installed and will be exercised on the first target that has it.
"""

from __future__ import annotations

from .. import factories
from ..client import FrappeClient
from ..gating import Versions
from .base import ReleaseSuite, SkipStep, Step


def _page(client: FrappeClient, ctx: dict) -> None:
    page = factories.ensure_builder_page(client)
    ctx["page"] = page["name"]
    ctx["route"] = page.get("route")
    ctx["published"] = page.get("published")


def _published_page_loads(client: FrappeClient, ctx: dict) -> None:
    if not ctx.get("published"):
        raise AssertionError(f"Builder page {ctx['page']} did not publish")
    route = ctx.get("route")
    if not route:
        raise SkipStep("Builder page has no route to fetch")
    resp = client.session.get(f"{client.url}/{route.lstrip('/')}", timeout=client.timeout)
    if not resp.ok:
        raise AssertionError(f"published page /{route} returned {resp.status_code}")


class BuilderSuite(ReleaseSuite):
    name = "builder"
    required_app = "builder"
    description = "Builder: author a page (hero + cards) and publish it."

    def build_steps(self, versions: Versions) -> list[Step]:
        return [
            Step("create + publish Builder Page", _page),
            Step("published page loads", _published_page_loads),
        ]
