"""HRMS leave flow: allocate leave, apply for leave, verify the balance drops.

Allocates 10 days for the current-year Leave Period, then submits an approved
2-weekday Leave Application and asserts the balance fell by exactly the number of
leave days ERPNext itself computes (robust to holidays/half-days).
"""

from __future__ import annotations

from datetime import date, timedelta

from .. import factories
from ..client import FrappeClient
from ..gating import Versions
from ..reset import purge
from .base import SmokeSuite, Step

_LEAVE_APP = "hrms.hr.doctype.leave_application.leave_application"


def _num(value) -> float:
    if isinstance(value, dict):
        value = value.get("leave_balance", 0)
    return float(value or 0)


def _two_weekdays_within(from_date: str, to_date: str) -> tuple[str, str]:
    """Return two consecutive weekdays (Mon+Tue) inside the period, near today."""
    start = date.today() + timedelta(days=3)
    while start.weekday() != 0:  # advance to a Monday
        start += timedelta(days=1)
    end = start + timedelta(days=1)
    lo, hi = date.fromisoformat(str(from_date)), date.fromisoformat(str(to_date))
    start = min(max(start, lo), hi)
    end = min(max(end, lo), hi)
    return str(start), str(end)


def _masters(client: FrappeClient, ctx: dict) -> None:
    ctx["company"] = factories.ensure_company(client)
    ctx["employee"] = factories.ensure_employee(client, ctx["company"])
    factories.ensure_holiday_list(client, ctx["employee"])
    ctx["leave_type"] = factories.ensure_leave_type(client)
    ctx["period"] = factories.ensure_leave_period(client, ctx["company"])


def _reset(client: FrappeClient, ctx: dict) -> None:
    # Prior runs' allocation/application would collide; clear them first.
    both = {"employee": ctx["employee"], "leave_type": ctx["leave_type"]}
    purge(client, "Leave Application", both)
    purge(client, "Leave Allocation", both)


def _allocate(client: FrappeClient, ctx: dict) -> None:
    period = client.get_doc("Leave Period", ctx["period"])
    ctx["from_date"], ctx["to_date"] = period["from_date"], period["to_date"]
    doc = {
        "doctype": "Leave Allocation",
        "employee": ctx["employee"],
        "leave_type": ctx["leave_type"],
        "from_date": ctx["from_date"],
        "to_date": ctx["to_date"],
        "new_leaves_allocated": 10,
    }
    ctx["allocation"] = client.submit({**client.insert(doc)})["name"]


def _leave_balance(client: FrappeClient, ctx: dict) -> float:
    # consider_all_leaves_in_the_allocation_period counts leaves anywhere in the
    # allocation window, so a future-dated application still reduces the balance.
    return _num(
        client.call(
            f"{_LEAVE_APP}.get_leave_balance_on",
            employee=ctx["employee"],
            leave_type=ctx["leave_type"],
            date=str(date.today()),
            consider_all_leaves_in_the_allocation_period=1,
        )
    )


def _balance_after_allocation(client: FrappeClient, ctx: dict) -> None:
    balance = _leave_balance(client, ctx)
    ctx["balance_before"] = balance
    if balance < 10 - 0.01:
        raise AssertionError(f"expected >= 10 days allocated, balance is {balance}")


def _apply_leave(client: FrappeClient, ctx: dict) -> None:
    frm, to = _two_weekdays_within(ctx["from_date"], ctx["to_date"])
    ctx["applied_days"] = _num(
        client.call(
            f"{_LEAVE_APP}.get_number_of_leave_days",
            employee=ctx["employee"],
            leave_type=ctx["leave_type"],
            from_date=frm,
            to_date=to,
        )
    )
    doc = {
        "doctype": "Leave Application",
        "employee": ctx["employee"],
        "leave_type": ctx["leave_type"],
        "from_date": frm,
        "to_date": to,
        "company": ctx["company"],
        "status": "Approved",
    }
    ctx["application"] = client.submit({**client.insert(doc)})["name"]


def _verify_balance_dropped(client: FrappeClient, ctx: dict) -> None:
    balance = _leave_balance(client, ctx)
    expected = ctx["balance_before"] - ctx["applied_days"]
    if abs(balance - expected) > 0.01:
        raise AssertionError(
            f"balance {balance} != expected {expected} "
            f"(before {ctx['balance_before']} - applied {ctx['applied_days']})"
        )


class HRMSLeaveSuite(SmokeSuite):
    name = "hrms_leave"
    required_app = "hrms"
    description = "Leave flow: allocate 10 days, apply for an approved leave, verify the balance drops by the applied days."

    def build_steps(self, versions: Versions) -> list[Step]:
        return [
            Step("ensure masters (employee/leave type/period)", _masters),
            Step("reset prior smoke leave docs", _reset),
            Step("submit Leave Allocation (10 days)", _allocate),
            Step("verify balance allocated", _balance_after_allocation),
            Step("submit approved Leave Application", _apply_leave),
            Step("verify balance dropped by applied days", _verify_balance_dropped),
        ]
