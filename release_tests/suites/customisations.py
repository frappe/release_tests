"""The customisation layer: does a customised site survive this release?

A stock site passing every flow suite proves very little about a real deployment.
This suite provisions a realistic customisation pack (Custom Fields, Property
Setters, a Client Script, Server Scripts and a custom DocType with a child table)
and then proves each layer still functions after the upgrade.

Run it against the dedicated customisation Testing Site. Running the same flow
suites against both a clean and a customised site is the point: a failure only on
the customised site localises the break to the customisation layer immediately.
"""

from __future__ import annotations

from typing import ClassVar

from .. import customisations, factories
from ..client import FrappeClient
from ..gating import Versions
from .base import ReleaseSuite, SkipStep, Step


def _needs_pack(step_fn):
    """Skip a step when provisioning was refused, rather than let it fail on missing state.

    A SkipStep does not block the rest of the suite, so without this every later
    step would raise KeyError on context the provisioning step never set — turning
    one honest skip into six misleading failures.
    """

    def wrapped(client: FrappeClient, ctx: dict) -> None:
        if ctx.get("not_permitted"):
            raise SkipStep(ctx["not_permitted"])
        step_fn(client, ctx)

    wrapped.__name__ = step_fn.__name__
    wrapped.__doc__ = step_fn.__doc__
    return wrapped


def _provision(client: FrappeClient, ctx: dict) -> None:
    try:
        ctx["pack"] = customisations.ensure_customisations(client)
    except customisations.CustomisationsNotPermitted as exc:
        ctx["not_permitted"] = str(exc)
        raise SkipStep(str(exc)) from exc
    ctx["company"] = factories.ensure_company(client)
    ctx["customer"] = factories.ensure_customer(client)
    ctx["item"] = factories.ensure_item(client)


def _meta_fields(client: FrappeClient, doctype: str) -> list[dict]:
    """Fetch a doctype's *effective* fields — customisations merged in.

    ``frappe.desk.form.load.getdoctype`` is the whitelisted route to meta; there is
    no ``frappe.client.get_meta``. Reading meta rather than the Custom Field table
    is the point: it proves the customisation is actually merged into the doctype
    the way a form would see it, which is what meta-cache changes upstream break.
    """
    response = client.call("frappe.desk.form.load.getdoctype", doctype=doctype, with_parent=1)
    docs = (response or {}).get("docs") if isinstance(response, dict) else None
    if not docs:
        raise AssertionError(f"could not read meta for {doctype}: {str(response)[:200]}")
    return docs[0].get("fields", [])


def _custom_field_in_meta(client: FrappeClient, ctx: dict) -> None:
    """The Custom Field must show up in Sales Invoice's meta, not just its own table."""
    fieldnames = {f.get("fieldname") for f in _meta_fields(client, "Sales Invoice")}
    if customisations.RT_SI_FIELD not in fieldnames:
        raise AssertionError(
            f"{customisations.RT_SI_FIELD} missing from Sales Invoice meta — "
            "the custom field did not survive"
        )


def _property_setter_applied(client: FrappeClient, ctx: dict) -> None:
    """The Property Setter must actually override the shipped label."""
    for field in _meta_fields(client, "Sales Invoice"):
        if field.get("fieldname") == "po_no":
            if field.get("label") != "RT PO Ref":
                raise AssertionError(
                    f"property setter not applied: po_no label is {field.get('label')!r}"
                )
            return
    raise AssertionError("po_no not present in Sales Invoice meta")


def _custom_field_round_trips(client: FrappeClient, ctx: dict) -> None:
    """A value written to the custom field must persist through submit."""
    doc = {
        "doctype": "Sales Invoice",
        "company": ctx["company"],
        "customer": ctx["customer"],
        "update_stock": 0,
        "items": [{"item_code": ctx["item"], "qty": 1, "rate": 100}],
        customisations.RT_SI_FIELD: "RT-ROUNDTRIP",
    }
    submitted = client.submit({**client.insert(doc)})
    ctx["invoice"] = submitted["name"]
    stored = client.get_doc("Sales Invoice", ctx["invoice"]).get(customisations.RT_SI_FIELD)
    if stored != "RT-ROUNDTRIP":
        raise AssertionError(f"custom field lost through submit: {stored!r}")


def _server_script_fires(client: FrappeClient, ctx: dict) -> None:
    """The Before Save DocType Event script must stamp an unset custom field."""
    if ctx["pack"].get("server_scripts_skipped"):
        raise SkipStep(ctx["pack"]["server_scripts_skipped"])
    doc = {
        "doctype": "Sales Invoice",
        "company": ctx["company"],
        "customer": ctx["customer"],
        "update_stock": 0,
        "items": [{"item_code": ctx["item"], "qty": 1, "rate": 100}],
    }
    created = client.insert(doc)
    stamped = client.get_doc("Sales Invoice", created["name"]).get(customisations.RT_SI_FIELD)
    if not stamped or not stamped.startswith("RT-"):
        raise AssertionError(
            f"Before Save server script did not stamp the field (got {stamped!r})"
        )


def _custom_doctype_accepts_child_rows(client: FrappeClient, ctx: dict) -> None:
    """The custom DocType must insert, name from its series, and keep child rows."""
    from ..reset import purge

    # Each run needs a fresh insert to prove naming and child rows still work, so
    # clear the previous run's note rather than letting them accumulate.
    purge(client, customisations.RT_NOTE_DOCTYPE, {})

    note = client.insert(
        {
            "doctype": customisations.RT_NOTE_DOCTYPE,
            "naming_series": "RT-NOTE-.#####",
            "title": "Release customisation check",
            "sales_invoice": ctx.get("invoice"),
            "notes": [
                {"item_code": ctx["item"], "remark": "provisioned by release_tests"},
                {"item_code": ctx["item"], "remark": "second row"},
            ],
        }
    )
    stored = client.get_doc(customisations.RT_NOTE_DOCTYPE, note["name"])
    if not str(stored.get("name", "")).startswith("RT-NOTE-"):
        raise AssertionError(f"naming series not applied: {stored.get('name')!r}")
    if len(stored.get("notes") or []) != 2:
        raise AssertionError(f"child rows lost: {len(stored.get('notes') or [])} of 2")


def _client_script_present(client: FrappeClient, ctx: dict) -> None:
    """The engine cannot run browser JS — assert the record is intact and enabled.

    Actual behaviour is covered by ui/cypress/e2e/v16/05-customisations.cy.js.
    """
    script = client.get_doc("Client Script", customisations.RT_CLIENT_SCRIPT)
    if not script.get("enabled"):
        raise AssertionError("RT client script is disabled")
    if "add_custom_button" not in (script.get("script") or ""):
        raise AssertionError("RT client script body was altered or truncated")


class CustomisationsSuite(ReleaseSuite):
    name = "customisations"
    required_app = "erpnext"  # the pack customises Sales Invoice / Item
    description = (
        "Customisation layer: provision Custom Fields, Property Setters, a Client Script, "
        "Server Scripts and a custom DocType with a child table, then prove each still "
        "works after the release."
    )
    guards: ClassVar[list[str]] = [
        "frappe@e197a37a",  # revert: stronger checks in save/set_value broke legit writes
        "frappe@4af19414",  # assignment permission bypass
        "frappe@6fe8b3c2",  # 16.21.1 hotfix: disable render safe globals by default
    ]

    def build_steps(self, versions: Versions) -> list[Step]:
        return [
            Step("provision customisation pack", _provision),
            Step("custom field present in meta", _needs_pack(_custom_field_in_meta)),
            Step("property setter applied", _needs_pack(_property_setter_applied)),
            Step(
                "custom field round-trips through submit",
                _needs_pack(_custom_field_round_trips),
            ),
            Step("server script fires on save", _needs_pack(_server_script_fires)),
            Step(
                "custom doctype accepts child rows",
                _needs_pack(_custom_doctype_accepts_child_rows),
            ),
            Step("client script intact", _needs_pack(_client_script_present)),
        ]
