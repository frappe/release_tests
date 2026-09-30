"""version-16-polished: the upgrade patches left the site in the state they promise.

Read-only. Each check is written so it also holds on a fresh polished site; on a
v16 site that was *upgraded* to polished it proves the patch actually ran. Checks
that only mean something after an upgrade skip on a fresh site and say so.
"""

from __future__ import annotations

from typing import ClassVar

from ..checks import ensure
from ..client import FrappeClient
from ..gating import Versions, app_installed
from ._v16p import polished_precheck
from .base import ReleaseSuite, SkipStep, Step

LUCIDE_RENAMES = {
    "Website": "website",
    "Integrations": "integration",
    "Welcome Workspace": "image-view",
}


def _workspaces(client: FrappeClient, ctx: dict) -> None:
    no_module = client.get_list(
        "Workspace", filters={"module": ["in", ["", None]]}, fields=["name"], limit=50
    )
    ensure(
        not no_module,
        "every Workspace has a module (now mandatory)",
        expected="0 workspaces without a module",
        actual=f"{len(no_module)}: {[w['name'] for w in no_module][:10]}",
        endpoint="Workspace.module",
        guards="patch backfill_workspace_module",
    )
    standard = client.get_list("Workspace", filters={"standard": 1}, fields=["name"], limit=1)
    ensure(
        bool(standard),
        "workspaces shipped by apps are flagged standard",
        expected="at least one Workspace with standard = 1",
        actual="none",
        endpoint="Workspace.standard",
        guards="patch workspace.patches.set_standard_flag",
    )
    stale = client.get_list(
        "Workspace",
        filters={"name": ["in", list(LUCIDE_RENAMES)]},
        fields=["name", "icon"],
        limit=10,
    )
    old_icons = [
        f"{w['name']} ({w['icon']})" for w in stale if w.get("icon") == LUCIDE_RENAMES[w["name"]]
    ]
    ensure(
        not old_icons,
        "workspace icons renamed to Lucide names",
        expected="Website → app-window, Integrations → cable, Welcome Workspace → sparkles",
        actual=f"still on old icon: {old_icons}",
        endpoint="Workspace.icon",
        guards="patch rename_lucide_workspace_icons",
    )


def _sidebars(client: FrappeClient, ctx: dict) -> None:
    new = client.get_list("Sidebar", fields=["name"], limit=1)
    ensure(
        bool(new),
        "per-module Sidebars exist",
        expected="at least one Sidebar",
        actual="none",
        endpoint="Sidebar",
        guards="patch convert_sidebars",
    )
    try:
        old = client.get_list("Workspace Sidebar", fields=["name"], limit=1)
    except Exception:  # noqa: BLE001 - DocType absent on a fresh polished site
        old = None
    if not old:
        raise SkipStep("no old Workspace Sidebar records (fresh site): nothing to carry over")


def _print_settings(client: FrappeClient, ctx: dict) -> None:
    settings = client.get_doc("Print Settings", "Print Settings")
    docs, exports = settings.get("max_bulk_print_docs"), settings.get("max_concurrent_bulk_exports")
    ensure(
        bool(docs) and bool(exports),
        "bulk print limits are set",
        expected="max_bulk_print_docs and max_concurrent_bulk_exports set (100 / 5 by default)",
        actual=f"max_bulk_print_docs={docs}, max_concurrent_bulk_exports={exports}",
        endpoint="Print Settings",
        guards="patch backfill_print_settings_bulk_export_limits",
    )


def _print_formats(client: FrappeClient, ctx: dict) -> None:
    no_for = client.get_list(
        "Print Format", filters={"print_format_for": ["in", ["", None]]}, fields=["name"], limit=50
    )
    ensure(
        not no_for,
        "every print format says what it prints for",
        expected="print_format_for set on all formats",
        actual=f"{len(no_for)} unset: {[r['name'] for r in no_for][:20]}",
        endpoint="Print Format.print_format_for",
        guards="patch set_print_format_for_doctype",
        hint="printing still lists them (the picker accepts an empty value), but the Print "
        "Format form hides Edit Format and no preview is generated. On a fresh install the "
        "patch never runs, so formats shipped without the field stay empty",
    )
    unset = client.get_list(
        "Print Format",
        filters={
            "print_format_builder_beta": 1,
            "custom_format": 0,
            "raw_printing": 0,
            "pdf_generator": ["not in", ["Typst", "WeasyPrint"]],
            "standard": "No",
        },
        fields=["name", "pdf_generator"],
        limit=50,
    )
    ensure(
        not unset,
        "site-made builder formats keep a supported renderer",
        expected="pdf_generator = WeasyPrint or Typst on custom builder formats",
        actual=f"{[(r['name'], r.get('pdf_generator')) for r in unset][:10]}",
        endpoint="Print Format.pdf_generator",
        guards="patch set_weasyprint_generator_for_beta_formats",
    )


def _list_layouts(client: FrappeClient, ctx: dict) -> None:
    missing = client.get_list(
        "List Filter", filters={"route_signature": ["is", "not set"]}, fields=["name"], limit=50
    )
    ensure(
        not missing,
        "saved list layouts carry a route signature",
        expected="0 List Filter rows without route_signature",
        actual=f"{len(missing)} rows: {[r['name'] for r in missing][:10]}",
        endpoint="List Filter.route_signature",
        guards="patch backfill_list_layout_route_signature",
    )


def _desktop(client: FrappeClient, ctx: dict) -> None:
    page = client.get_doc("Desktop Settings", "Desktop Settings").get("desktop_page")
    ctx["desktop_page"] = page
    if page and "icon" in page.lower():
        icons = client.get_list("Desktop Icon", fields=["name"], limit=1)
        # Reported as an issue, not skipped: users on the icon grid see an empty desktop.
        ensure(
            bool(icons),
            "desktop icon grid has icons",
            expected="at least one Desktop Icon for a site on the icon grid",
            actual=f"desktop_page = {page!r}, 0 Desktop Icons",
            endpoint="Desktop Settings / Desktop Icon",
            guards="patch keep_existing_sites_on_desktop_icons",
            hint="KNOWN ISSUE (fix pending): framework Desktop Icons removed on upgrade",
        )


def _hrms_job_offer_backfill(client: FrappeClient, ctx: dict) -> None:
    hired = client.get_list(
        "Employee",
        filters={"job_applicant": ["is", "set"]},
        fields=["name", "job_applicant", "job_offer"],
        limit=500,
    )
    if not hired:
        raise SkipStep("no employees hired through a Job Applicant on this site")
    gaps = []
    for emp in hired:
        if emp.get("job_offer"):
            continue
        offer = client.get_list(
            "Job Offer",
            filters={"job_applicant": emp["job_applicant"], "docstatus": ["!=", 2]},
            fields=["name"],
            limit=1,
        )
        if offer:
            gaps.append(f"{emp['name']} (offer {offer[0]['name']})")
    ensure(
        not gaps,
        "employees hired through an applicant have their Job Offer set",
        expected="Employee.job_offer filled wherever a Job Offer exists",
        actual=f"{len(gaps)} missing: {gaps[:10]}",
        endpoint="Employee.job_offer",
        guards="hrms patch set_job_offer_in_employee",
    )


class V16PUpgradeChecksSuite(ReleaseSuite):
    name = "v16p_upgrade_checks"
    required_app = "frappe"
    description = (
        "version-16-polished upgrade patches: workspaces, sidebars, print settings/formats, list "
        "layouts, desktop, HRMS job offer backfill. Read-only."
    )
    guards: ClassVar[list[str]] = [
        "frappe patches v16_0 (polished)",
        "hrms patch set_job_offer_in_employee",
    ]

    # Each check stands alone; one failure must not hide the others.
    independent_steps = True

    def precheck(self, client: FrappeClient) -> str | None:
        return polished_precheck(client)

    def build_steps(self, versions: Versions) -> list[Step]:
        steps = [
            Step("workspaces: module, standard flag, Lucide icons", _workspaces),
            Step("sidebars converted", _sidebars),
            Step("print settings bulk limits", _print_settings),
            Step("print formats: print_format_for + renderer", _print_formats),
            Step("list layouts have route signature", _list_layouts),
            Step("desktop icon grid not empty", _desktop),
        ]
        if app_installed(versions, "hrms"):
            steps.append(Step("HRMS: Job Offer backfilled on Employee", _hrms_job_offer_backfill))
        return steps
