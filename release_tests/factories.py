"""Idempotent get-or-create helpers shared across suites.

Every helper queries by a deterministic name first and only inserts when the
record is missing, so re-running the harness against the same site is safe and
never piles up duplicate master data.
"""

from __future__ import annotations

from typing import Any

from .client import FrappeClient

# Deterministic names so re-runs are idempotent and easy to spot/clean up.
RT_COMPANY = "Release Test Co"
RT_COMPANY_ABBR = "RTC"
RT_CUSTOMER = "Release Test Customer"
RT_ITEM = "RT-ITEM"
RT_STOCK_ITEM = "RT-STOCK-ITEM"
RT_SERIAL_ITEM = "RT-SERIAL-ITEM"
RT_BATCH_ITEM = "RT-BATCH-ITEM"
RT_SERVICE_ITEM = "RT-SERVICE-ITEM"
RT_FG_ITEM = "RT-FG-ITEM"
RT_RAW_ITEM = "RT-RAW-ITEM"
RT_WAREHOUSE = "Release Warehouse"
RT_SUPPLIER = "Release Test Supplier"
RT_EMPLOYEE = "Release Test Employee"
RT_EMPLOYEE_2 = "Release Report Employee"
RT_LEAVE_TYPE = "Release Leave Type"
RT_EXPENSE_TYPE = "Release Expense Type"


def _get_or_create(client: FrappeClient, doctype: str, name: str, doc: dict[str, Any]) -> str:
    """Return the name of an existing doc, else insert ``doc`` and return its name."""
    existing = client.get_list(doctype, filters={"name": name}, fields=["name"], limit=1)
    if existing:
        return existing[0]["name"]
    created = client.insert({"doctype": doctype, **doc})
    return created["name"]


def _hsn_code(client: FrappeClient) -> str | None:
    """A valid HSN/SAC code, if India Compliance's master is present.

    India Compliance makes ``gst_hsn_code`` mandatory on Items; we borrow the
    first code from its master. Returns None on sites without the app so item
    creation stays generic.
    """
    # India Compliance requires the code to be exactly 6 or 8 digits; the master
    # also holds shorter chapter headings, so match an 8-char name via LIKE.
    try:
        codes = client.get_list(
            "GST HSN Code", filters={"name": ["like", "________"]}, fields=["name"], limit=1
        )
    except Exception:  # noqa: BLE001 - doctype absent when the app isn't installed
        return None
    return codes[0]["name"] if codes else None


def ensure_company(client: FrappeClient) -> str:
    existing = client.get_list("Company", fields=["name"], limit=1)
    if existing:
        # Prefer whatever company the site already has — fresh sites have one
        # from the setup wizard; we only create our own if none exists.
        return existing[0]["name"]
    return _get_or_create(
        client,
        "Company",
        RT_COMPANY,
        {
            "company_name": RT_COMPANY,
            "abbr": RT_COMPANY_ABBR,
            "default_currency": "INR",
            "country": "India",
        },
    )


def ensure_customer(client: FrappeClient) -> str:
    return _get_or_create(
        client,
        "Customer",
        RT_CUSTOMER,
        {"customer_name": RT_CUSTOMER, "customer_type": "Company"},
    )


def ensure_item(client: FrappeClient) -> str:
    doc = {
        "item_code": RT_ITEM,
        "item_name": "Release Test Item",
        "is_stock_item": 0,
        "stock_uom": "Nos",
        "item_group": "All Item Groups",
    }
    hsn = _hsn_code(client)
    if hsn:
        doc["gst_hsn_code"] = hsn
    return _get_or_create(client, "Item", RT_ITEM, doc)


def ensure_employee(client: FrappeClient, company: str) -> str:
    return _ensure_employee(client, company, RT_EMPLOYEE)


def ensure_employee2(client: FrappeClient, company: str, reports_to: str) -> str:
    """A second Employee that reports to ``reports_to`` (the manager)."""
    return _ensure_employee(client, company, RT_EMPLOYEE_2, reports_to)


def _ensure_employee(
    client: FrappeClient,
    company: str,
    first_name: str,
    reports_to: str | None = None,
) -> str:
    # Key on first_name: HRMS overwrites employee_name from the name parts, so a
    # get-or-create on employee_name never matches. order_by keeps it stable.
    existing = client.get_list(
        "Employee",
        filters={"first_name": first_name},
        fields=["name"],
        order_by="creation asc",
        limit=1,
    )
    if existing:
        return existing[0]["name"]
    doc = {
        "doctype": "Employee",
        "first_name": first_name,
        "company": company,
        "gender": "Other",
        "date_of_joining": "2020-01-01",
        "date_of_birth": "1990-01-01",
        "status": "Active",
    }
    if reports_to:
        doc["reports_to"] = reports_to
    return client.insert(doc)["name"]


# ------------------------------------------------------------------- stock
def ensure_warehouse(client: FrappeClient, company: str) -> str:
    # ERPNext suffixes warehouse names with the company abbreviation.
    abbr = client.get_list("Company", filters={"name": company}, fields=["abbr"], limit=1)[0]["abbr"]
    name = f"{RT_WAREHOUSE} - {abbr}"
    existing = client.get_list("Warehouse", filters={"name": name}, fields=["name"], limit=1)
    if existing:
        return existing[0]["name"]
    return client.insert(
        {"doctype": "Warehouse", "warehouse_name": RT_WAREHOUSE, "company": company}
    )["name"]


def ensure_stock_item(client: FrappeClient, company: str, warehouse: str) -> str:
    existing = client.get_list("Item", filters={"name": RT_STOCK_ITEM}, fields=["name"], limit=1)
    if existing:
        return existing[0]["name"]
    doc = {
        "doctype": "Item",
        "item_code": RT_STOCK_ITEM,
        "item_name": "Release Stock Item",
        "is_stock_item": 1,
        "stock_uom": "Nos",
        "item_group": "All Item Groups",
        "item_defaults": [{"company": company, "default_warehouse": warehouse}],
    }
    hsn = _hsn_code(client)
    if hsn:
        doc["gst_hsn_code"] = hsn
    return client.insert(doc)["name"]


def ensure_supplier(client: FrappeClient) -> str:
    return _get_or_create(
        client,
        "Supplier",
        RT_SUPPLIER,
        {"supplier_name": RT_SUPPLIER, "supplier_group": "All Supplier Groups"},
    )


def ensure_stock_on_hand(
    client: FrappeClient, company: str, item: str, warehouse: str, qty: float, rate: float = 100
) -> None:
    """Top up stock via a Material Receipt only if the Bin is short of ``qty``."""
    bins = client.get_list(
        "Bin", filters={"item_code": item, "warehouse": warehouse}, fields=["actual_qty"], limit=1
    )
    on_hand = float(bins[0]["actual_qty"]) if bins else 0.0
    if on_hand >= qty:
        return
    receipt = {
        "doctype": "Stock Entry",
        "stock_entry_type": "Material Receipt",
        "company": company,
        "items": [
            {"item_code": item, "qty": qty - on_hand, "basic_rate": rate, "t_warehouse": warehouse}
        ],
    }
    client.submit({**client.insert(receipt)})


# -------------------------------------------------------------------- leave
def ensure_leave_type(client: FrappeClient) -> str:
    return _get_or_create(
        client,
        "Leave Type",
        RT_LEAVE_TYPE,
        {"leave_type_name": RT_LEAVE_TYPE, "max_leaves_allowed": 20},
    )


def ensure_holiday_list(client: FrappeClient, employee: str) -> str:
    """Ensure a current-year Holiday List is assigned to the employee.

    HRMS v16 resolves an employee's holidays through a submittable "Holiday List
    Assignment" record (the ``Employee.holiday_list`` field is no longer consulted
    for leave-day calculation), so we create + submit one if the employee has none.
    """
    from datetime import date

    year = date.today().year
    name = f"Release Holiday List {year}"
    existing = client.get_list("Holiday List", filters={"name": name}, fields=["name"], limit=1)
    holiday_list = (
        existing[0]["name"]
        if existing
        else client.insert(
            {
                "doctype": "Holiday List",
                "holiday_list_name": name,
                "from_date": f"{year}-01-01",
                "to_date": f"{year}-12-31",
            }
        )["name"]
    )
    assigned = client.get_list(
        "Holiday List Assignment",
        filters={"assigned_to": employee, "docstatus": 1},
        fields=["name"],
        limit=1,
    )
    if not assigned:
        client.submit(
            {
                **client.insert(
                    {
                        "doctype": "Holiday List Assignment",
                        "applicable_for": "Employee",
                        "assigned_to": employee,
                        "holiday_list": holiday_list,
                        "from_date": f"{year}-01-01",
                    }
                )
            }
        )
    return holiday_list


def ensure_leave_period(client: FrappeClient, company: str) -> str:
    """A Leave Period spanning the current calendar year."""
    from datetime import date

    year = date.today().year
    from_date, to_date = f"{year}-01-01", f"{year}-12-31"
    existing = client.get_list(
        "Leave Period",
        filters={"from_date": from_date, "to_date": to_date, "company": company},
        fields=["name"],
        limit=1,
    )
    if existing:
        return existing[0]["name"]
    return client.insert(
        {
            "doctype": "Leave Period",
            "from_date": from_date,
            "to_date": to_date,
            "company": company,
            "is_active": 1,
        }
    )["name"]


# ------------------------------------------------------- item types + mfg
def _company_currency(client: FrappeClient, company: str) -> str:
    row = client.get_list("Company", filters={"name": company}, fields=["default_currency"], limit=1)
    return (row and row[0].get("default_currency")) or "INR"


def _new_item(client: FrappeClient, code: str, name: str, extra: dict[str, Any]) -> str:
    existing = client.get_list("Item", filters={"name": code}, fields=["name"], limit=1)
    if existing:
        return existing[0]["name"]
    doc = {
        "doctype": "Item",
        "item_code": code,
        "item_name": name,
        "item_group": "All Item Groups",
        "stock_uom": "Nos",
        **extra,
    }
    hsn = _hsn_code(client)
    if hsn:
        doc["gst_hsn_code"] = hsn
    return client.insert(doc)["name"]


def ensure_serialised_item(client: FrappeClient, company: str, warehouse: str) -> str:
    return _new_item(
        client,
        RT_SERIAL_ITEM,
        "Release Serial Item",
        {
            "is_stock_item": 1,
            "has_serial_no": 1,
            "serial_no_series": "RT-SER-.#####",
            "item_defaults": [{"company": company, "default_warehouse": warehouse}],
        },
    )


def ensure_batched_item(client: FrappeClient, company: str, warehouse: str) -> str:
    return _new_item(
        client,
        RT_BATCH_ITEM,
        "Release Batch Item",
        {
            "is_stock_item": 1,
            "has_batch_no": 1,
            "create_new_batch": 1,
            "batch_number_series": "RT-BATCH-.#####",
            "item_defaults": [{"company": company, "default_warehouse": warehouse}],
        },
    )


def ensure_service_item(client: FrappeClient) -> str:
    return _new_item(client, RT_SERVICE_ITEM, "Release Service Item", {"is_stock_item": 0})


def ensure_serial_batch_enabled(client: FrappeClient) -> None:
    """Turn on Stock Settings' master serial/batch toggle if it's off (site-wide)."""
    settings = client.get_doc("Stock Settings", "Stock Settings")
    if not settings.get("enable_serial_and_batch_no_for_item"):
        client.call(
            "frappe.client.set_value",
            doctype="Stock Settings",
            name="Stock Settings",
            fieldname="enable_serial_and_batch_no_for_item",
            value=1,
        )


def ensure_named_warehouse(client: FrappeClient, company: str, base_name: str) -> str:
    abbr = client.get_list("Company", filters={"name": company}, fields=["abbr"], limit=1)[0]["abbr"]
    name = f"{base_name} - {abbr}"
    existing = client.get_list("Warehouse", filters={"name": name}, fields=["name"], limit=1)
    if existing:
        return existing[0]["name"]
    return client.insert(
        {"doctype": "Warehouse", "warehouse_name": base_name, "company": company}
    )["name"]


def ensure_fg_item(client: FrappeClient, company: str, warehouse: str) -> str:
    return _new_item(
        client,
        RT_FG_ITEM,
        "Release Finished Good",
        {"is_stock_item": 1, "item_defaults": [{"company": company, "default_warehouse": warehouse}]},
    )


def ensure_raw_item(client: FrappeClient, company: str, warehouse: str) -> str:
    return _new_item(
        client,
        RT_RAW_ITEM,
        "Release Raw Material",
        {"is_stock_item": 1, "item_defaults": [{"company": company, "default_warehouse": warehouse}]},
    )


def ensure_manufacturing_warehouses(client: FrappeClient, company: str) -> dict[str, str]:
    return {
        "source": ensure_named_warehouse(client, company, "Release Source WH"),
        "wip": ensure_named_warehouse(client, company, "Release WIP WH"),
        "fg": ensure_named_warehouse(client, company, "Release FG WH"),
    }


def ensure_bom(client: FrappeClient, company: str, fg_item: str, raw_items: list[tuple]) -> str:
    """Get-or-create a submitted, active BOM. ``raw_items`` = [(item_code, qty, rate), ...]."""
    existing = client.get_list(
        "BOM",
        filters={"item": fg_item, "is_active": 1, "docstatus": 1},
        fields=["name"],
        limit=1,
    )
    if existing:
        return existing[0]["name"]
    doc = {
        "doctype": "BOM",
        "item": fg_item,
        "quantity": 1,
        "company": company,
        "currency": _company_currency(client, company),
        "conversion_rate": 1,
        "with_operations": 0,
        "is_active": 1,
        "is_default": 1,
        "items": [
            {"item_code": code, "qty": qty, "uom": "Nos", "rate": rate}
            for code, qty, rate in raw_items
        ],
    }
    return client.submit({**client.insert(doc)})["name"]


def ensure_expense_claim_type(client: FrappeClient) -> str:
    return _get_or_create(
        client,
        "Expense Claim Type",
        RT_EXPENSE_TYPE,
        {"expense_type": RT_EXPENSE_TYPE},
    )
