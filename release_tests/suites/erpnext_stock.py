"""ERPNext stock: a Material Receipt increases the item's Bin quantity."""

from __future__ import annotations

from .. import factories
from ..client import FrappeClient
from ..gating import Versions
from .base import ReleaseSuite, Step

_RECEIPT_QTY = 5


def _masters(client: FrappeClient, ctx: dict) -> None:
    ctx["company"] = factories.ensure_company(client)
    ctx["warehouse"] = factories.ensure_warehouse(client, ctx["company"])
    ctx["item"] = factories.ensure_stock_item(client, ctx["company"], ctx["warehouse"])


def _bin_qty(client: FrappeClient, ctx: dict) -> float:
    bins = client.get_list(
        "Bin",
        filters={"item_code": ctx["item"], "warehouse": ctx["warehouse"]},
        fields=["actual_qty"],
        limit=1,
    )
    return float(bins[0]["actual_qty"]) if bins else 0.0


def _read_before(client: FrappeClient, ctx: dict) -> None:
    ctx["qty_before"] = _bin_qty(client, ctx)


def _material_receipt(client: FrappeClient, ctx: dict) -> None:
    doc = {
        "doctype": "Stock Entry",
        "stock_entry_type": "Material Receipt",
        "company": ctx["company"],
        "items": [
            {
                "item_code": ctx["item"],
                "qty": _RECEIPT_QTY,
                "basic_rate": 100,
                "t_warehouse": ctx["warehouse"],
            }
        ],
    }
    ctx["stock_entry"] = client.submit({**client.insert(doc)})["name"]


def _verify_increase(client: FrappeClient, ctx: dict) -> None:
    after = _bin_qty(client, ctx)
    expected = ctx["qty_before"] + _RECEIPT_QTY
    if abs(after - expected) > 0.01:
        raise AssertionError(f"Bin qty {after} != expected {expected}")


class ERPNextStockSuite(ReleaseSuite):
    name = "erpnext_stock"
    required_app = "erpnext"
    description = "Stock: a Material Receipt Stock Entry increases the item's Bin quantity by the received amount."

    def build_steps(self, versions: Versions) -> list[Step]:
        return [
            Step("ensure masters", _masters),
            Step("read Bin qty before", _read_before),
            Step("submit Material Receipt", _material_receipt),
            Step("verify Bin increased", _verify_increase),
        ]
