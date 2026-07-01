"""ERPNext serialised item: receive with serials, then deliver specific serials (v16).

Uses the v16 ``use_serial_batch_fields`` path: pass ``serial_no`` as newline text and
ERPNext auto-builds the Serial and Batch Bundle. Serials are made unique per run so
re-runs never collide.
"""

from __future__ import annotations

import time

from .. import factories
from ..client import FrappeClient
from ..gating import Versions
from .base import SmokeSuite, Step


def _masters(client: FrappeClient, ctx: dict) -> None:
    factories.ensure_serial_batch_enabled(client)
    ctx["company"] = factories.ensure_company(client)
    ctx["customer"] = factories.ensure_customer(client)
    ctx["supplier"] = factories.ensure_supplier(client)
    ctx["warehouse"] = factories.ensure_warehouse(client, ctx["company"])
    ctx["item"] = factories.ensure_serialised_item(client, ctx["company"], ctx["warehouse"])


def _receive(client: FrappeClient, ctx: dict) -> None:
    stamp = int(time.time())
    ctx["serials"] = [f"SMK-SER-{stamp}-{i}" for i in range(1, 4)]
    doc = {
        "doctype": "Purchase Receipt",
        "supplier": ctx["supplier"],
        "company": ctx["company"],
        "items": [
            {
                "item_code": ctx["item"],
                "qty": len(ctx["serials"]),
                "rate": 100,
                "warehouse": ctx["warehouse"],
                "use_serial_batch_fields": 1,
                "serial_no": "\n".join(ctx["serials"]),
            }
        ],
    }
    ctx["pr"] = client.submit({**client.insert(doc)})["name"]


def _deliver(client: FrappeClient, ctx: dict) -> None:
    ctx["shipped"] = ctx["serials"][:2]
    doc = {
        "doctype": "Delivery Note",
        "customer": ctx["customer"],
        "company": ctx["company"],
        "items": [
            {
                "item_code": ctx["item"],
                "qty": len(ctx["shipped"]),
                "rate": 150,
                "warehouse": ctx["warehouse"],
                "use_serial_batch_fields": 1,
                "serial_no": "\n".join(ctx["shipped"]),
            }
        ],
    }
    ctx["dn"] = client.submit({**client.insert(doc)})["name"]


def _verify_delivered(client: FrappeClient, ctx: dict) -> None:
    for serial in ctx["shipped"]:
        status = client.get_doc("Serial No", serial).get("status")
        if status != "Delivered":
            raise AssertionError(f"serial {serial} status is {status!r}, expected 'Delivered'")


class ERPNextSerialisedSuite(SmokeSuite):
    name = "erpnext_serialised"
    required_app = "erpnext"
    description = "Serialised item: Purchase Receipt with serials, then Delivery Note shipping specific serials."

    def build_steps(self, versions: Versions) -> list[Step]:
        return [
            Step("ensure masters (serialised item)", _masters),
            Step("receive serials (Purchase Receipt)", _receive),
            Step("deliver specific serials (Delivery Note)", _deliver),
            Step("verify serials Delivered", _verify_delivered),
        ]
