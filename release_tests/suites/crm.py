"""Frappe CRM: create a Lead, a Deal, and an (ERPNext) Customer.

All idempotent (keyed on deterministic email / organization / name), so re-runs
against the same site stay clean.
"""

from __future__ import annotations

from .. import factories
from ..client import FrappeClient
from ..gating import Versions
from .base import ReleaseSuite, Step

_ORG = "Release Test Org"


def _lead(client: FrappeClient, ctx: dict) -> None:
    ctx["lead"] = factories.ensure_crm_lead(client)


def _deal(client: FrappeClient, ctx: dict) -> None:
    ctx["deal"] = factories.ensure_crm_deal(client, _ORG)


def _customer(client: FrappeClient, ctx: dict) -> None:
    ctx["customer"] = factories.ensure_customer(client)


class CRMSuite(ReleaseSuite):
    name = "crm"
    required_app = "crm"
    description = "Frappe CRM: create a Lead, a Deal, and a Customer."

    def build_steps(self, versions: Versions) -> list[Step]:
        return [
            Step("create CRM Lead", _lead),
            Step("create CRM Deal", _deal),
            Step("ensure Customer", _customer),
        ]
