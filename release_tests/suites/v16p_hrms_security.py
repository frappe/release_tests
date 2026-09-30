"""version-16-polished HRMS: attendance marking permission fixes, per role.

The release made the attendance tools check, before any record is written, that
the caller may create attendance *and* can see every employee named — and it
rejects malformed input before those checks. The personas:

* ``hr_scoped`` — an HR User limited by a User Permission to one employee (A).
  They must be able to mark A, and be refused for employee B.
* ``employee`` — an Employee-role user linked to employee A (self service).
  They can check in for themselves, not for B, and can't mark attendance.
"""

from __future__ import annotations

import json
from datetime import date, timedelta
from typing import ClassVar

from .. import factories, personas
from ..checks import ensure, expect_allowed, expect_denied, expect_rejected
from ..client import FrappeClient
from ..gating import Versions
from ._v16p import polished_precheck
from .base import ReleaseSuite, Step

RT_SELF_EMPLOYEE = "Release Self Service"
BULK = "hrms.hr.doctype.attendance.attendance.mark_bulk_attendance"
TOOL = "hrms.hr.doctype.employee_attendance_tool.employee_attendance_tool.mark_employee_attendance"
GUARD_ACCESS = "hrms@00e9f9d674, hrms@054dffef4d"
GUARD_TYPES = "hrms@5b71c3da71"


def _setup(client: FrappeClient, ctx: dict) -> None:
    ctx["company"] = factories.ensure_company(client)
    ctx["emp_b"] = factories.ensure_employee(client, ctx["company"])
    ctx["emp_a"] = factories._ensure_employee(client, ctx["company"], RT_SELF_EMPLOYEE)

    employee_user = personas.ensure_user(client, "employee").email
    doc = client.get_doc("Employee", ctx["emp_a"])
    if doc.get("user_id") != employee_user:
        # Saving with user_id set makes HRMS create the user's Employee permission.
        doc["user_id"] = employee_user
        doc["create_user_permission"] = 1
        client.call("frappe.client.save", doc=json.dumps(doc, default=str))

    scoped = personas.ensure_user(client, "hr_scoped").email
    has_scope = client.get_list(
        "User Permission",
        filters={"user": scoped, "allow": "Employee", "for_value": ctx["emp_a"]},
        fields=["name"],
        limit=1,
    )
    if not has_scope:
        client.insert(
            {
                "doctype": "User Permission",
                "user": scoped,
                "allow": "Employee",
                "for_value": ctx["emp_a"],
                "apply_to_all_doctypes": 1,
            }
        )
    ctx["date"] = _unmarked_date(client, ctx["emp_a"])


def _unmarked_date(client: FrappeClient, employee: str) -> str:
    """A recent past weekday with no attendance for ``employee`` — keeps re-runs clean."""
    marked = {
        row["attendance_date"]
        for row in client.get_list(
            "Attendance",
            filters={"employee": employee, "docstatus": ["!=", 2]},
            fields=["attendance_date"],
            limit=1000,
        )
    }
    day = date.today()
    for _ in range(400):
        day -= timedelta(days=1)
        if day.weekday() < 5 and str(day) not in marked:
            return str(day)
    raise RuntimeError(f"no unmarked weekday in the last 400 days for {employee}")


def _invalid_input_rejected(client: FrappeClient, ctx: dict) -> None:
    hr = personas.login_as(client, "hr")
    expect_rejected(
        hr,
        "bulk attendance with a list where the employee id should be",
        lambda: hr.call(BULK, data=json.dumps({"employee": [ctx["emp_a"]], "unmarked_days": []})),
        message="Employee must be a non-empty string",
        endpoint=BULK,
        guards=GUARD_TYPES,
    )
    expect_rejected(
        hr,
        "bulk attendance with a single date string instead of a list of dates",
        lambda: hr.call(
            BULK, data=json.dumps({"employee": ctx["emp_a"], "unmarked_days": ctx["date"]})
        ),
        message="Unmarked days must be a list",
        endpoint=BULK,
        guards=GUARD_TYPES,
    )


def _scoped_hr_refused_for_other_employee(client: FrappeClient, ctx: dict) -> None:
    scoped = personas.login_as(client, "hr_scoped")
    expect_denied(
        scoped,
        f"HR User scoped to {ctx['emp_a']} bulk-marks attendance for {ctx['emp_b']}",
        lambda: scoped.call(
            BULK,
            data=json.dumps(
                {"employee": ctx["emp_b"], "unmarked_days": [ctx["date"]], "status": "Present"}
            ),
        ),
        endpoint=BULK,
        guards=GUARD_ACCESS,
    )
    expect_denied(
        scoped,
        f"HR User scoped to {ctx['emp_a']} updates half-day attendance for {ctx['emp_b']}",
        lambda: scoped.call(
            TOOL,
            employee_list="[]",
            status="Present",
            date=ctx["date"],
            company=ctx["company"],
            mark_half_day=1,
            half_day_status="Present",
            half_day_employee_list=json.dumps([ctx["emp_b"]]),
        ),
        endpoint=f"{TOOL} (mark_half_day)",
        guards=GUARD_ACCESS,
    )


def _scoped_hr_marks_own_employee(client: FrappeClient, ctx: dict) -> None:
    scoped = personas.login_as(client, "hr_scoped")
    expect_allowed(
        scoped,
        f"HR User scoped to {ctx['emp_a']} marks attendance for {ctx['emp_a']} on {ctx['date']}",
        lambda: scoped.call(
            TOOL,
            employee_list=json.dumps([ctx["emp_a"]]),
            status="Present",
            date=ctx["date"],
            company=ctx["company"],
        ),
        endpoint=TOOL,
        guards=GUARD_ACCESS,
        hint="the new access checks must not block an HR user's permitted employees",
    )
    marked = client.get_list(
        "Attendance",
        filters={"employee": ctx["emp_a"], "attendance_date": ctx["date"], "docstatus": ["!=", 2]},
        fields=["name"],
        limit=1,
    )
    ensure(
        bool(marked),
        "attendance record exists after marking",
        expected=f"Attendance for {ctx['emp_a']} on {ctx['date']}",
        actual="none found",
        who=scoped,
        endpoint=TOOL,
    )


def _employee_self_service(client: FrappeClient, ctx: dict) -> None:
    me = personas.login_as(client, "employee")
    info = expect_allowed(
        me,
        "employee looks up their own Employee record (Quick Check In)",
        lambda: me.call("hrms.api.get_current_employee_info"),
        endpoint="hrms.api.get_current_employee_info",
    )
    ensure(
        (info or {}).get("name") == ctx["emp_a"],
        "Quick Check In finds the logged-in employee",
        expected=ctx["emp_a"],
        actual=(info or {}).get("name"),
        who=me,
        endpoint="hrms.api.get_current_employee_info",
    )
    now = f"{date.today()} 09:00:00"
    expect_allowed(
        me,
        "employee checks themselves in",
        lambda: me.insert(
            {"doctype": "Employee Checkin", "employee": ctx["emp_a"], "log_type": "IN", "time": now}
        ),
        endpoint="POST /api/resource/Employee Checkin",
        guards="hrms#5089",
    )
    expect_denied(
        me,
        f"employee checks in on behalf of another employee ({ctx['emp_b']})",
        lambda: me.insert(
            {"doctype": "Employee Checkin", "employee": ctx["emp_b"], "log_type": "IN", "time": now}
        ),
        endpoint="POST /api/resource/Employee Checkin",
        guards="hrms#5089",
    )
    expect_denied(
        me,
        f"employee bulk-marks attendance for another employee ({ctx['emp_b']})",
        lambda: me.call(
            BULK,
            data=json.dumps(
                {"employee": ctx["emp_b"], "unmarked_days": [ctx["date"]], "status": "Present"}
            ),
        ),
        endpoint=BULK,
        guards=GUARD_ACCESS,
    )


class V16PHRMSSecuritySuite(ReleaseSuite):
    name = "v16p_hrms_security"
    required_app = "hrms"
    description = (
        "version-16-polished HRMS: attendance tools check create access and per-employee "
        "access before writing, reject malformed input, and self-service stays self-only."
    )
    guards: ClassVar[list[str]] = [
        "hrms@00e9f9d674",
        "hrms@054dffef4d",
        "hrms@5b71c3da71",
        "hrms#5089",
    ]

    # Each check stands alone; one failure must not hide the others.
    independent_steps = True

    def precheck(self, client: FrappeClient) -> str | None:
        return polished_precheck(client)

    def build_steps(self, versions: Versions) -> list[Step]:
        return [
            Step("setup: employees A/B, scoped HR user, self-service user", _setup, blocks_on_fail=True),
            Step("malformed attendance input rejected [hr]", _invalid_input_rejected),
            Step(
                "attendance for an employee outside scope refused [hr_scoped]",
                _scoped_hr_refused_for_other_employee,
            ),
            Step(
                "attendance for an employee in scope allowed [hr_scoped]",
                _scoped_hr_marks_own_employee,
            ),
            Step("self check-in only, no attendance for others [employee]", _employee_self_service),
        ]
