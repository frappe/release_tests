"""ERPNext batched item: receive into a batch, then deliver from it (v16).

Uses the v16 ``use_serial_batch_fields`` path with a unique batch per run.
"""

from __future__ import annotations

from .. import factories
from ..client import FrappeClient
from ..gating import Versions
from .base import SmokeSuite, Step

_RECEIVE_QTY = 100
_DELIVER_QTY = 25


def _masters(client: FrappeClient, ctx: dict) -> None:
    factories.ensure_serial_batch_enabled(client)
    ctx["company"] = factories.ensure_company(client)
    ctx["customer"] = factories.ensure_customer(client)
    ctx["supplier"] = factories.ensure_supplier(client)
    ctx["warehouse"] = factories.ensure_warehouse(client, ctx["company"])
    ctx["item"] = factories.ensure_batched_item(client, ctx["company"], ctx["warehouse"])


def _receive(client: FrappeClient, ctx: dict) -> None:
    # Leave batch_no blank: create_new_batch + batch_number_series auto-generate a
    # unique batch, which ERPNext writes back onto the submitted item row.
    doc = {
        "doctype": "Purchase Receipt",
        "supplier": ctx["supplier"],
        "company": ctx["company"],
        "items": [
            {
                "item_code": ctx["item"],
                "qty": _RECEIVE_QTY,
                "rate": 50,
                "warehouse": ctx["warehouse"],
                "use_serial_batch_fields": 1,
            }
        ],
    }
    ctx["pr"] = client.submit({**client.insert(doc)})["name"]
    # The auto-created batch is referenced via the bundle, not written back to the
    # row's batch_no, so grab the most-recent batch for this item.
    batches = client.get_list(
        "Batch", filters={"item": ctx["item"]}, fields=["name"], order_by="creation desc", limit=1
    )
    if not batches:
        raise AssertionError("no batch auto-generated on receipt")
    ctx["batch"] = batches[0]["name"]


def _deliver(client: FrappeClient, ctx: dict) -> None:
    doc = {
        "doctype": "Delivery Note",
        "customer": ctx["customer"],
        "company": ctx["company"],
        "items": [
            {
                "item_code": ctx["item"],
                "qty": _DELIVER_QTY,
                "rate": 75,
                "warehouse": ctx["warehouse"],
                "use_serial_batch_fields": 1,
                "batch_no": ctx["batch"],
            }
        ],
    }
    ctx["dn"] = client.submit({**client.insert(doc)})["name"]


def _verify_batch_qty(client: FrappeClient, ctx: dict) -> None:
    remaining = client.call(
        "erpnext.stock.doctype.batch.batch.get_batch_qty",
        batch_no=ctx["batch"],
        warehouse=ctx["warehouse"],
    )
    expected = _RECEIVE_QTY - _DELIVER_QTY
    if abs(float(remaining or 0) - expected) > 0.01:
        raise AssertionError(f"batch qty {remaining} != expected {expected}")


class ERPNextBatchedSuite(SmokeSuite):
    name = "erpnext_batched"
    required_app = "erpnext"
    description = "Batched item: receive 100 into a batch, deliver 25, verify 75 remain in the batch."

    def build_steps(self, versions: Versions) -> list[Step]:
        return [
            Step("ensure masters (batched item)", _masters),
            Step("receive batch (Purchase Receipt)", _receive),
            Step("deliver from batch (Delivery Note)", _deliver),
            Step("verify remaining batch qty", _verify_batch_qty),
        ]
