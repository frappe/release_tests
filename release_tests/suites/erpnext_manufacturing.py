"""ERPNext manufacturing: BOM -> Work Order -> material transfer -> manufacture.

A bare-bones cycle (no operations): stock raw materials, define a BOM, raise a Work
Order, transfer materials to WIP, then run the Manufacture entry and check output.
"""

from __future__ import annotations

from datetime import datetime

from .. import factories
from ..client import FrappeClient
from ..gating import Versions
from .base import ReleaseSuite, Step

_WO_QTY = 5
_MAKE_SE = "erpnext.manufacturing.doctype.work_order.work_order.make_stock_entry"


def _masters(client: FrappeClient, ctx: dict) -> None:
    ctx["company"] = factories.ensure_company(client)
    warehouses = factories.ensure_manufacturing_warehouses(client, ctx["company"])
    ctx["source"], ctx["wip"], ctx["fg_wh"] = (
        warehouses["source"],
        warehouses["wip"],
        warehouses["fg"],
    )
    ctx["fg"] = factories.ensure_fg_item(client, ctx["company"], ctx["fg_wh"])
    ctx["raw"] = factories.ensure_raw_item(client, ctx["company"], ctx["source"])
    factories.ensure_stock_on_hand(client, ctx["company"], ctx["raw"], ctx["source"], qty=50, rate=10)


def _bom(client: FrappeClient, ctx: dict) -> None:
    ctx["bom"] = factories.ensure_bom(client, ctx["company"], ctx["fg"], [(ctx["raw"], 2, 10)])


def _work_order(client: FrappeClient, ctx: dict) -> None:
    doc = {
        "doctype": "Work Order",
        "production_item": ctx["fg"],
        "bom_no": ctx["bom"],
        "qty": _WO_QTY,
        "company": ctx["company"],
        "wip_warehouse": ctx["wip"],
        "fg_warehouse": ctx["fg_wh"],
        "source_warehouse": ctx["source"],
        "planned_start_date": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
    }
    ctx["wo"] = client.submit({**client.insert(doc)})["name"]


def _stock_entry(client: FrappeClient, ctx: dict, purpose: str) -> None:
    entry = client.call(_MAKE_SE, work_order_id=ctx["wo"], purpose=purpose)
    entry["doctype"] = "Stock Entry"
    client.submit({**client.insert(entry)})


def _transfer(client: FrappeClient, ctx: dict) -> None:
    _stock_entry(client, ctx, "Material Transfer for Manufacture")


def _manufacture(client: FrappeClient, ctx: dict) -> None:
    _stock_entry(client, ctx, "Manufacture")


def _verify_produced(client: FrappeClient, ctx: dict) -> None:
    produced = float(client.get_doc("Work Order", ctx["wo"]).get("produced_qty") or 0)
    if produced < _WO_QTY - 0.01:
        raise AssertionError(f"produced_qty {produced} != expected {_WO_QTY}")


class ERPNextManufacturingSuite(ReleaseSuite):
    name = "erpnext_manufacturing"
    required_app = "erpnext"
    description = "Manufacturing: BOM (no operations) -> Work Order -> material transfer -> manufacture; verify produced qty."

    def build_steps(self, versions: Versions) -> list[Step]:
        return [
            Step("ensure masters + raw stock", _masters),
            Step("ensure BOM", _bom),
            Step("submit Work Order", _work_order),
            Step("Material Transfer for Manufacture", _transfer),
            Step("Manufacture entry", _manufacture),
            Step("verify produced qty", _verify_produced),
        ]
