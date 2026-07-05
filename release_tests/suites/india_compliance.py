"""India Compliance: GST masters -> GST Sales Invoice -> best-effort e-invoice.

Setup (company/customer GSTIN, item tax templates at 5/12/18%) is idempotent and
runs once; the invoice + e-invoice attempt repeat each run. e-invoice IRN needs
the India Compliance API configured on the site — if it isn't, that step skips.
"""

from __future__ import annotations

from .. import factories
from ..client import FrappeClient
from ..gating import Versions
from .base import ReleaseSuite, SkipStep, Step

_PLACE_OF_SUPPLY = "27-Maharashtra"  # matches RT_CUSTOMER_GSTIN state (inter-state -> IGST)


def _masters(client: FrappeClient, ctx: dict) -> None:
    ctx["company"] = factories.ensure_gst_company(client)
    ctx["company_address"] = factories.ensure_company_gst_address(client, ctx["company"])
    ctx["customer"] = factories.ensure_gst_customer(client)
    ctx["igst_account"] = factories.output_igst_account(client, ctx["company"])
    ctx["items"] = [
        factories.ensure_gst_item(client, ctx["company"], code, name, rate)
        for code, name, rate in factories.RT_GST_ITEMS
    ]


def _gst_invoice(client: FrappeClient, ctx: dict) -> None:
    doc = {
        "doctype": "Sales Invoice",
        "customer": ctx["customer"],
        "company": ctx["company"],
        "company_address": ctx["company_address"],
        "company_gstin": factories.RT_COMPANY_GSTIN,
        "place_of_supply": _PLACE_OF_SUPPLY,
        "items": [{"item_code": it, "qty": 1, "rate": 1000} for it in ctx["items"]],
    }
    if ctx.get("igst_account"):
        # One IGST row; each item's Item Tax Template applies its own rate per line.
        doc["taxes"] = [
            {"charge_type": "On Net Total", "account_head": ctx["igst_account"], "description": "IGST", "rate": 18}
        ]
    ctx["invoice"] = client.submit({**client.insert(doc)})["name"]


def _verify_gst(client: FrappeClient, ctx: dict) -> None:
    inv = client.get_doc("Sales Invoice", ctx["invoice"])
    tax = float(inv.get("total_taxes_and_charges") or 0)
    if tax <= 0:
        raise AssertionError(f"no GST computed on {ctx['invoice']} (total_taxes_and_charges={tax})")


def _e_invoice(client: FrappeClient, ctx: dict) -> None:
    try:
        client.call(
            "india_compliance.gst_india.utils.e_invoice.generate_e_invoice",
            docname=ctx["invoice"],
            throw=False,
        )
    except Exception as exc:  # noqa: BLE001 - API off / not applicable is a skip, not a failure
        raise SkipStep(f"e-invoice not attempted: {exc}")
    inv = client.get_doc("Sales Invoice", ctx["invoice"])
    if inv.get("irn"):
        ctx["irn"] = inv["irn"]
        return
    raise SkipStep("e-invoice API not configured on this site (no IRN returned)")


class IndiaComplianceSuite(ReleaseSuite):
    name = "india_compliance"
    required_app = "india_compliance"
    description = (
        "GST setup (company/customer GSTIN, item tax templates at 5/12/18%) -> inter-state GST "
        "Sales Invoice -> best-effort e-invoice IRN (skips if the IC API isn't configured)."
    )

    def build_steps(self, versions: Versions) -> list[Step]:
        return [
            Step("ensure GST masters (GSTINs + tax templates + items)", _masters),
            Step("create + submit GST Sales Invoice", _gst_invoice),
            Step("verify GST tax computed", _verify_gst),
            Step("attempt e-invoice (IRN)", _e_invoice),
        ]
