"""Webshop: publish a Website Item and surface it in the site's top bar.

Flow: ensure a stock Item -> publish a Website Item from it -> add a Top Bar Item
to Website Settings -> confirm the item's web page actually renders. All
idempotent (Website Item keyed on item_code, Top Bar Item on its label).

NOTE: written against the Webshop Website Item / Website Settings schema but not
yet validated end-to-end in this environment (the ``webshop`` app isn't present
here). It auto-skips where Webshop isn't installed and will be exercised on the
first target that has it.
"""

from __future__ import annotations

from .. import factories
from ..client import FrappeClient
from ..gating import Versions
from .base import ReleaseSuite, SkipStep, Step


def _item(client: FrappeClient, ctx: dict) -> None:
    ctx["item"] = factories.ensure_webshop_item(client)


def _publish(client: FrappeClient, ctx: dict) -> None:
    website_item = factories.ensure_website_item(client, ctx["item"])
    ctx["website_item"] = website_item["name"]
    ctx["route"] = website_item.get("route")


def _top_bar(client: FrappeClient, ctx: dict) -> None:
    factories.ensure_top_bar_item(client, factories.RT_TOP_BAR_LABEL, url="/all-products")


def _visible_on_website(client: FrappeClient, ctx: dict) -> None:
    route = ctx.get("route")
    if not route:
        raise SkipStep("Website Item has no route to fetch")
    resp = client.session.get(f"{client.url}/{route.lstrip('/')}", timeout=client.timeout)
    if not resp.ok:
        raise AssertionError(f"published item page /{route} returned {resp.status_code}")


class WebshopSuite(ReleaseSuite):
    name = "webshop"
    required_app = "webshop"
    description = "Webshop: publish a Website Item, add it to the top bar, and load its page."

    def build_steps(self, versions: Versions) -> list[Step]:
        return [
            Step("ensure Item", _item),
            Step("publish Website Item", _publish),
            Step("update Website Settings top bar", _top_bar),
            Step("item visible on website", _visible_on_website),
        ]
