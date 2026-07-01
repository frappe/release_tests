"""Suite registry.

Suites are listed in execution order. ``core_frappe`` runs first (it proves the
basics), then ERPNext/HRMS, then the gated stub suites which auto-skip when their
app isn't installed.
"""

from __future__ import annotations

from .base import SmokeSuite


def all_suites() -> list[SmokeSuite]:
    # Imported lazily so importing the package never requires every submodule.
    from . import (
        builder,
        core_frappe,
        crm,
        erpnext,
        erpnext_accounts,
        erpnext_buying,
        erpnext_selling,
        erpnext_stock,
        helpdesk,
        hrms,
        hrms_leave,
        hrms_org,
        india_compliance,
        insights,
        ksa_compliance,
        learning,
        webshop,
    )

    return [
        core_frappe.CoreFrappeSuite(),
        erpnext.ERPNextSuite(),
        erpnext_selling.ERPNextSellingSuite(),
        erpnext_buying.ERPNextBuyingSuite(),
        erpnext_stock.ERPNextStockSuite(),
        erpnext_accounts.ERPNextAccountsSuite(),
        hrms.HRMSSuite(),
        hrms_org.HRMSOrgSuite(),
        hrms_leave.HRMSLeaveSuite(),
        crm.CRMSuite(),
        helpdesk.HelpdeskSuite(),
        learning.LearningSuite(),
        insights.InsightsSuite(),
        builder.BuilderSuite(),
        webshop.WebshopSuite(),
        india_compliance.IndiaComplianceSuite(),
        ksa_compliance.KSAComplianceSuite(),
    ]


def suite_names() -> list[str]:
    return [s.name for s in all_suites()]
