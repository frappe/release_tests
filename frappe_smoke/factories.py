"""Idempotent get-or-create helpers shared across suites.

Every helper queries by a deterministic name first and only inserts when the
record is missing, so re-running the harness against the same site is safe and
never piles up duplicate master data.
"""

from __future__ import annotations

from typing import Any

from .client import FrappeClient

# Deterministic names so re-runs are idempotent and easy to spot/clean up.
SMOKE_COMPANY = "Smoke Test Co"
SMOKE_COMPANY_ABBR = "STC"
SMOKE_CUSTOMER = "Smoke Test Customer"
SMOKE_ITEM = "SMOKE-ITEM"
SMOKE_EMPLOYEE = "Smoke Test Employee"


def _get_or_create(client: FrappeClient, doctype: str, name: str, doc: dict[str, Any]) -> str:
    """Return the name of an existing doc, else insert ``doc`` and return its name."""
    existing = client.get_list(doctype, filters={"name": name}, fields=["name"], limit=1)
    if existing:
        return existing[0]["name"]
    created = client.insert({"doctype": doctype, **doc})
    return created["name"]


def ensure_company(client: FrappeClient) -> str:
    existing = client.get_list("Company", fields=["name"], limit=1)
    if existing:
        # Prefer whatever company the site already has — fresh sites have one
        # from the setup wizard; we only create our own if none exists.
        return existing[0]["name"]
    return _get_or_create(
        client,
        "Company",
        SMOKE_COMPANY,
        {
            "company_name": SMOKE_COMPANY,
            "abbr": SMOKE_COMPANY_ABBR,
            "default_currency": "INR",
            "country": "India",
        },
    )


def ensure_customer(client: FrappeClient) -> str:
    return _get_or_create(
        client,
        "Customer",
        SMOKE_CUSTOMER,
        {"customer_name": SMOKE_CUSTOMER, "customer_type": "Company"},
    )


def ensure_item(client: FrappeClient) -> str:
    return _get_or_create(
        client,
        "Item",
        SMOKE_ITEM,
        {
            "item_code": SMOKE_ITEM,
            "item_name": "Smoke Test Item",
            "is_stock_item": 0,
            "stock_uom": "Nos",
            "item_group": "All Item Groups",
        },
    )


def ensure_employee(client: FrappeClient, company: str) -> str:
    existing = client.get_list(
        "Employee",
        filters={"employee_name": SMOKE_EMPLOYEE},
        fields=["name"],
        limit=1,
    )
    if existing:
        return existing[0]["name"]
    created = client.insert(
        {
            "doctype": "Employee",
            "employee_name": SMOKE_EMPLOYEE,
            "first_name": "Smoke Test",
            "company": company,
            "gender": "Other",
            "date_of_joining": "2020-01-01",
            "date_of_birth": "1990-01-01",
            "status": "Active",
        }
    )
    return created["name"]
