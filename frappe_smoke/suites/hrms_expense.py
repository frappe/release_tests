"""HRMS expense claim: create and self-approve an Expense Claim for the employee.

Self-approved as Administrator for now (real reports-to approver login is roadmap).
"""

from __future__ import annotations

from datetime import date

from .. import factories
from ..client import FrappeClient
from ..gating import Versions
from ..reset import purge
from .base import SmokeSuite, Step


def _masters(client: FrappeClient, ctx: dict) -> None:
    ctx["company"] = factories.ensure_company(client)
    ctx["employee"] = factories.ensure_employee(client, ctx["company"])
    ctx["expense_type"] = factories.ensure_expense_claim_type(client)
    payable = client.get_list(
        "Account",
        filters={"company": ctx["company"], "account_type": "Payable", "is_group": 0},
        fields=["name"],
        limit=1,
    )
    expense = client.get_list(
        "Account",
        filters={"company": ctx["company"], "root_type": "Expense", "is_group": 0},
        fields=["name"],
        limit=1,
    )
    if not payable or not expense:
        raise AssertionError("company needs a Payable and an Expense account")
    ctx["payable"], ctx["expense_account"] = payable[0]["name"], expense[0]["name"]
    centers = client.get_list(
        "Cost Center", filters={"company": ctx["company"], "is_group": 0}, fields=["name"], limit=1
    )
    ctx["cost_center"] = centers[0]["name"] if centers else None
    row = client.get_list(
        "Company", filters={"name": ctx["company"]}, fields=["default_currency"], limit=1
    )
    ctx["currency"] = (row and row[0].get("default_currency")) or "INR"


def _reset(client: FrappeClient, ctx: dict) -> None:
    purge(client, "Expense Claim", {"employee": ctx["employee"]})


def _claim(client: FrappeClient, ctx: dict) -> None:
    row = {"expense_type": ctx["expense_type"], "amount": 250, "default_account": ctx["expense_account"]}
    if ctx["cost_center"]:
        row["cost_center"] = ctx["cost_center"]
    doc = {
        "doctype": "Expense Claim",
        "employee": ctx["employee"],
        "company": ctx["company"],
        "posting_date": str(date.today()),
        "approval_status": "Approved",
        "payable_account": ctx["payable"],
        "currency": ctx["currency"],
        "exchange_rate": 1,
        "expenses": [row],
    }
    submitted = client.submit({**client.insert(doc)})
    if submitted.get("docstatus") != 1:
        raise AssertionError("expense claim not submitted")
    ctx["claim"] = submitted["name"]


def _verify_approved(client: FrappeClient, ctx: dict) -> None:
    doc = client.get_doc("Expense Claim", ctx["claim"])
    if doc.get("approval_status") != "Approved" or doc.get("docstatus") != 1:
        raise AssertionError(
            f"claim not approved+submitted: status={doc.get('approval_status')}, docstatus={doc.get('docstatus')}"
        )


class HRMSExpenseSuite(SmokeSuite):
    name = "hrms_expense"
    required_app = "hrms"
    description = "Expense claim: create + self-approve an Expense Claim for the employee, verify submitted."

    def build_steps(self, versions: Versions) -> list[Step]:
        return [
            Step("ensure masters (employee/expense type/accounts)", _masters),
            Step("reset prior smoke expense claims", _reset),
            Step("submit approved Expense Claim", _claim),
            Step("verify approved + submitted", _verify_approved),
        ]
