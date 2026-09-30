"""version-16-polished HRMS features: Job Offer, Job Opening, Employee links.

Runs as the ``hr`` persona (HR User): these are the screens an HR user works in.
"""

from __future__ import annotations

from datetime import date
from typing import ClassVar

from .. import factories, personas
from ..checks import ensure, expect_allowed, expect_rejected
from ..client import FrappeClient
from ..gating import Versions
from ._v16p import polished_precheck
from .base import ReleaseSuite, Step

RT_DESIGNATION = "Release Tester"
RT_OPENING_TITLE = "RT Release Opening"


def _setup(client: FrappeClient, ctx: dict) -> None:
    ctx["company"] = factories.ensure_company(client)
    if not client.get_list(
        "Designation", filters={"name": RT_DESIGNATION}, fields=["name"], limit=1
    ):
        client.insert({"doctype": "Designation", "designation_name": RT_DESIGNATION})
    personas.login_as(client, "hr")


def _job_offer_without_applicant(client: FrappeClient, ctx: dict) -> None:
    hr = personas.login_as(client, "hr")
    offer = {
        "doctype": "Job Offer",
        "applicant_name": "RT Walk-in Candidate",
        "applicant_email": "rt.candidate@example.com",
        "offer_date": str(date.today()),
        "designation": RT_DESIGNATION,
        "company": ctx["company"],
        "status": "Awaiting Response",
    }
    expect_allowed(
        hr,
        "Job Offer saved without a Job Applicant",
        lambda: hr.insert(dict(offer)),
        endpoint="POST /api/resource/Job Offer",
        hint="release note: Job Offer no longer requires a Job Applicant",
    )
    no_email = {k: v for k, v in offer.items() if k != "applicant_email"}
    expect_rejected(
        hr,
        "Job Offer saved without an applicant email",
        lambda: hr.insert(no_email),
        message="applicant",
        endpoint="POST /api/resource/Job Offer",
        hint="release note: applicant_email is now mandatory",
    )


def _employee_job_fields(client: FrappeClient, ctx: dict) -> None:
    found = {
        row["fieldname"]
        for row in client.get_list(
            "Custom Field",
            filters={"dt": "Employee", "fieldname": ["in", ["job_applicant", "job_offer"]]},
            fields=["fieldname"],
            limit=5,
        )
    }
    ensure(
        found == {"job_applicant", "job_offer"},
        "Employee carries the Job Applicant and Job Offer fields",
        expected="custom fields job_applicant and job_offer on Employee",
        actual=sorted(found) or "neither present",
        endpoint="Custom Field (Employee)",
        guards="hrms patch set_job_offer_in_employee",
    )


def _job_opening_close_reopen(client: FrappeClient, ctx: dict) -> None:
    hr = personas.login_as(client, "hr")
    rows = hr.get_list(
        "Job Opening", filters={"job_title": RT_OPENING_TITLE}, fields=["name"], limit=1
    )
    if rows:
        name = rows[0]["name"]
        hr.call(
            "frappe.client.set_value",
            doctype="Job Opening",
            name=name,
            fieldname="status",
            value="Open",
        )
    else:
        name = expect_allowed(
            hr,
            "HR User creates a Job Opening",
            lambda: hr.insert(
                {
                    "doctype": "Job Opening",
                    "job_title": RT_OPENING_TITLE,
                    "company": ctx["company"],
                    "designation": RT_DESIGNATION,
                    "status": "Open",
                    "posted_on": f"{date.today()} 00:00:00",
                }
            ),
            endpoint="POST /api/resource/Job Opening",
        )["name"]
    for status in ("Closed", "Open"):
        expect_allowed(
            hr,
            f"HR User sets Job Opening to {status}",
            lambda status=status: hr.call(
                "frappe.client.set_value",
                doctype="Job Opening",
                name=name,
                fieldname="status",
                value=status,
            ),
            endpoint="frappe.client.set_value (Job Opening.status)",
            hint="release note: close and reopen buttons on Job Opening",
        )
        got = hr.get_doc("Job Opening", name).get("status")
        ensure(
            got == status,
            f"Job Opening is {status}",
            expected=status,
            actual=got,
            who=hr,
            endpoint="Job Opening",
        )


class V16PHRMSSuite(ReleaseSuite):
    name = "v16p_hrms"
    required_app = "hrms"
    description = "version-16-polished HRMS features: Job Offer without applicant, Job Opening close/reopen, Employee job links."
    guards: ClassVar[list[str]] = ["hrms patch set_job_offer_in_employee"]

    # Each check stands alone; one failure must not hide the others.
    independent_steps = True

    def precheck(self, client: FrappeClient) -> str | None:
        return polished_precheck(client)

    def build_steps(self, versions: Versions) -> list[Step]:
        return [
            Step("setup: designation + HR user", _setup),
            Step("Job Offer without applicant; email mandatory [hr]", _job_offer_without_applicant),
            Step("Employee has Job Applicant / Job Offer fields", _employee_job_fields),
            Step("Job Opening close and reopen [hr]", _job_opening_close_reopen),
        ]
