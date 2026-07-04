"""ERPNext accounts: post a balanced Journal Entry against real chart-of-accounts."""

from __future__ import annotations

from datetime import date

from .. import factories
from ..client import FrappeClient
from ..gating import Versions
from .base import ReleaseSuite, Step

_AMOUNT = 100


def _first_account(client: FrappeClient, company: str, **filters) -> str | None:
    rows = client.get_list(
        "Account",
        filters={"company": company, "is_group": 0, **filters},
        fields=["name"],
        limit=1,
    )
    return rows[0]["name"] if rows else None


def _pick_accounts(client: FrappeClient, ctx: dict) -> None:
    company = ctx["company"] = factories.ensure_company(client)
    expense = _first_account(client, company, root_type="Expense")
    cash = _first_account(client, company, account_type="Cash") or _first_account(
        client, company, account_type="Bank"
    )
    if not expense or not cash:
        raise AssertionError("could not find an Expense and a Cash/Bank account for the company")
    ctx["expense_account"], ctx["cash_account"] = expense, cash
    centers = client.get_list(
        "Cost Center", filters={"company": company, "is_group": 0}, fields=["name"], limit=1
    )
    ctx["cost_center"] = centers[0]["name"] if centers else None


def _journal_entry(client: FrappeClient, ctx: dict) -> None:
    expense_line = {"account": ctx["expense_account"], "debit_in_account_currency": _AMOUNT}
    if ctx["cost_center"]:
        expense_line["cost_center"] = ctx["cost_center"]
    doc = {
        "doctype": "Journal Entry",
        "voucher_type": "Journal Entry",
        "company": ctx["company"],
        "posting_date": str(date.today()),
        "accounts": [
            expense_line,
            {"account": ctx["cash_account"], "credit_in_account_currency": _AMOUNT},
        ],
    }
    submitted = client.submit({**client.insert(doc)})
    if submitted.get("docstatus") != 1:
        raise AssertionError("Journal Entry not submitted")
    ctx["journal_entry"] = submitted["name"]


def _verify_balanced(client: FrappeClient, ctx: dict) -> None:
    doc = client.get_doc("Journal Entry", ctx["journal_entry"])
    debit = float(doc.get("total_debit") or 0)
    credit = float(doc.get("total_credit") or 0)
    if abs(debit - credit) > 0.01 or debit <= 0:
        raise AssertionError(f"Journal Entry not balanced: debit {debit} vs credit {credit}")


class ERPNextAccountsSuite(ReleaseSuite):
    name = "erpnext_accounts"
    required_app = "erpnext"
    description = "Accounts: post a balanced Journal Entry (expense debit / cash credit) and verify it submits."

    def build_steps(self, versions: Versions) -> list[Step]:
        return [
            Step("pick company accounts", _pick_accounts),
            Step("submit Journal Entry", _journal_entry),
            Step("verify balanced + submitted", _verify_balanced),
        ]
