"""Regression cover for the Jinja render sandbox.

``frappe/utils/safe_exec.py`` took 39 commits in six weeks — the single most
churned file in the framework — when ``get_safe_globals`` was split into
``render_safe_globals`` (templates) and ``exec_safe_globals`` (server scripts).
It shipped enabled in v16.21.0 and broke print formats, notifications and web
templates in the field; frappe@6fe8b3c2 disabled it by default one day later in
the v16.21.1 hotfix.

That default can flip again, and the allowlist keeps moving. These steps assert
the user-visible contract from outside: a print format that uses Jinja renders,
and a template reaching for something outside the sandbox fails as a clean
handled error rather than a 500.
"""

from __future__ import annotations

import re
from typing import ClassVar

from .. import factories
from ..client import FrappeAPIError, FrappeClient
from ..gating import Versions
from .base import ReleaseSuite, SkipStep, Step

RT_PRINT_FORMAT = "RT Jinja Probe"
RT_BLOCKED_FORMAT = "RT Jinja Blocked Probe"

# Exercises the filters and doc access a real print format relies on.
_ALLOWED_TEMPLATE = """
<div class="rt-probe">
  <span id="rt-name">{{ doc.name }}</span>
  <span id="rt-total">{{ frappe.utils.fmt_money(doc.grand_total, currency=doc.currency) }}</span>
  <span id="rt-when">{{ frappe.utils.formatdate(doc.posting_date, "dd-MM-yyyy") }}</span>
  <span id="rt-rows">{{ doc.items | length }}</span>
</div>
"""

# `import` is not reachable inside the sandbox; this must fail, and fail cleanly.
_BLOCKED_TEMPLATE = """
<div>{{ __import__("os").listdir("/") }}</div>
"""


def _ensure_print_format(client: FrappeClient, name: str, html: str) -> None:
    existing = client.get_list("Print Format", filters={"name": name}, fields=["name"], limit=1)
    if not existing:
        client.insert(
            {
                "doctype": "Print Format",
                "name": name,
                "doc_type": "Sales Invoice",
                "module": "Accounts",
                "print_format_type": "Jinja",
                "custom_format": 1,
                "standard": "No",
                "disabled": 0,
                "html": html,
            }
        )
        return
    current = client.get_doc("Print Format", name)
    if current.get("html") != html:
        client.call(
            "frappe.client.set_value",
            doctype="Print Format",
            name=name,
            fieldname="html",
            value=html,
        )


def _seed(client: FrappeClient, ctx: dict) -> None:
    ctx["company"] = factories.ensure_company(client)
    ctx["customer"] = factories.ensure_customer(client)
    ctx["item"] = factories.ensure_item(client)
    invoice = client.submit(
        {
            **client.insert(
                {
                    "doctype": "Sales Invoice",
                    "company": ctx["company"],
                    "customer": ctx["customer"],
                    "update_stock": 0,
                    # Two rows deliberately: the row count must differ from every qty
                    # so a template rendering the wrong value cannot pass by accident.
                    "items": [
                        {"item_code": ctx["item"], "qty": 3, "rate": 250},
                        {"item_code": ctx["item"], "qty": 5, "rate": 100},
                    ],
                }
            )
        }
    )
    ctx["invoice"] = invoice["name"]
    ctx["expected_rows"] = 2
    _ensure_print_format(client, RT_PRINT_FORMAT, _ALLOWED_TEMPLATE)
    _ensure_print_format(client, RT_BLOCKED_FORMAT, _BLOCKED_TEMPLATE)


def _render_html(client: FrappeClient, name: str, print_format: str) -> str:
    result = client.call(
        "frappe.www.printview.get_html_and_style",
        doc="Sales Invoice",
        name=name,
        print_format=print_format,
    )
    html = result.get("html") if isinstance(result, dict) else None
    if html is None:
        raise AssertionError(f"unexpected print payload: {str(result)[:200]}")
    return html


def _allowed_jinja_renders(client: FrappeClient, ctx: dict) -> None:
    """A print format using doc access and utils filters must still render."""
    html = _render_html(client, ctx["invoice"], RT_PRINT_FORMAT)
    if ctx["invoice"] not in html:
        raise AssertionError("print format did not render the document name")
    for marker in ("rt-total", "rt-when", "rt-rows"):
        if marker not in html:
            raise AssertionError(f"print format lost the {marker} block — Jinja did not render")
    ctx["rendered"] = html


def _utils_filters_resolve(client: FrappeClient, ctx: dict) -> None:
    """``frappe.utils`` helpers must resolve to real values, not empty output.

    A sandbox that silently yields nothing is the failure mode that matters here:
    the page still renders, so nothing looks broken, but every computed field on a
    customer-facing invoice comes out blank. Each helper is therefore checked for
    its actual value, not merely that its marker survived — fmt_money and
    formatdate are exactly the calls a restricted render context drops.
    """
    html = ctx["rendered"]

    def fragment(marker: str) -> str:
        start = html.find(f'id="{marker}"')
        if start == -1:
            raise SkipStep(f"{marker} marker missing; the allowed-render step already reported it")
        chunk = html[start : start + 200]
        inner = chunk.split(">", 1)[1] if ">" in chunk else chunk
        return inner.split("<", 1)[0].strip()

    rows = fragment("rt-rows")
    if rows != str(ctx["expected_rows"]):
        raise AssertionError(
            f"'doc.items | length' rendered {rows!r}, expected {ctx['expected_rows']}"
        )

    # fmt_money must produce the grand total with digits, not an empty string.
    money = fragment("rt-total")
    if not any(ch.isdigit() for ch in money):
        raise AssertionError(f"frappe.utils.fmt_money rendered no value: {money!r}")

    # formatdate must honour the dd-MM-yyyy pattern the template asks for.
    when = fragment("rt-when")
    if not re.fullmatch(r"\d{2}-\d{2}-\d{4}", when):
        raise AssertionError(
            f"frappe.utils.formatdate rendered {when!r}, expected dd-MM-yyyy"
        )


def _blocked_jinja_fails_cleanly(client: FrappeClient, ctx: dict) -> None:
    """Reaching outside the sandbox must be a handled error, never a 500.

    The distinction is the whole point of the split: blocked is correct, but it has
    to surface as a Frappe error the caller can act on.
    """
    try:
        html = _render_html(client, ctx["invoice"], RT_BLOCKED_FORMAT)
    except FrappeAPIError as exc:
        if exc.status and exc.status >= 500:
            raise AssertionError(
                f"blocked template caused a server error ({exc.status}) instead of a "
                f"handled failure: {str(exc)[:200]}"
            ) from exc
        return  # handled 4xx — correct
    if "root" in html or "usr" in html:
        raise AssertionError("sandbox escape: blocked template rendered filesystem contents")


class FrappeJinjaSandboxSuite(ReleaseSuite):
    name = "frappe_jinja_sandbox"
    required_app = "erpnext"  # renders a Sales Invoice print format
    description = (
        "Regression: the Jinja render sandbox — a print format using doc access and "
        "frappe.utils filters still renders, and a template reaching outside the sandbox "
        "fails cleanly rather than 500-ing."
    )
    guards: ClassVar[list[str]] = [
        "frappe@6fe8b3c2",  # v16.21.1 hotfix: disable render safe globals by default
        "frappe@6658228c",  # split get_safe_globals into render/exec
        "frappe@415f82d9",  # restrict render_template usage
        "frappe@5c1e1eee",  # block QB writes in render
        "frappe@493a2d47",  # block queries that export records
    ]

    def build_steps(self, versions: Versions) -> list[Step]:
        return [
            Step("seed invoice + Jinja print formats", _seed),
            Step("allowed Jinja print format renders", _allowed_jinja_renders),
            Step("frappe.utils filters resolve in template", _utils_filters_resolve),
            Step("blocked template fails cleanly", _blocked_jinja_fails_cleanly),
        ]
