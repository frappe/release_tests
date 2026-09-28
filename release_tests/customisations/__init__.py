"""Idempotent provisioning of a realistic customisation layer, over REST.

Real deployments are never stock: they carry Custom Fields, Property Setters,
Client Scripts, Server Scripts and custom DocTypes, and upstream releases break
those more often than they break core flows. This package ships that layer as
reviewable fixture JSON and pushes it onto a target site through the ordinary
``/api/resource`` endpoints — the engine stays Frappe-free and the pack works
against Frappe Cloud, where installing an app is not an option.

Every helper mirrors :mod:`release_tests.factories`: query by the deterministic
name first, insert only when missing, so re-running against the same site is a
no-op rather than a pile of duplicates.
"""

from __future__ import annotations

import json
from importlib import resources
from typing import Any

from ..client import FrappeAPIError, FrappeClient

# Deterministic names, mirroring the RT_* convention in factories.py.
RT_SI_FIELD = "rt_release_ref"
RT_ITEM_FIELD = "rt_risk_score"
RT_EMPLOYEE_FIELD = "rt_badge"
RT_CLIENT_SCRIPT = "RT Sales Invoice Form"
RT_EVENT_SCRIPT = "RT SI Before Save"
RT_API_SCRIPT = "RT Filter Probe"
RT_API_METHOD = "rt_filter_probe"
RT_NOTE_DOCTYPE = "RT Release Note"
RT_NOTE_CHILD_DOCTYPE = "RT Release Note Item"


class ServerScriptsDisabled(RuntimeError):
    """Target site has ``server_script_enabled`` off, so scripts cannot be pushed."""


def _fixture(filename: str) -> list[dict[str, Any]]:
    # Chained joinpath: multi-argument joinpath on Traversable is 3.12+, and this
    # package supports 3.10.
    return json.loads(
        resources.files(__package__).joinpath("fixtures").joinpath(filename).read_text()
    )


def _exists(client: FrappeClient, doctype: str, name: str) -> bool:
    return bool(client.get_list(doctype, filters={"name": name}, fields=["name"], limit=1))


def _sync_script(client: FrappeClient, doctype: str, definition: dict[str, Any]) -> None:
    """Create the script, or push the body when the target's copy has drifted.

    Scripts are the one part of the pack whose *content* is the thing under test,
    so a stale copy left on a target from an earlier fixture revision would quietly
    invalidate the run. Plain get-or-create is not enough here.
    """
    name = definition["name"]
    if not _exists(client, doctype, name):
        client.insert({"doctype": doctype, **definition})
        return
    current = client.get_doc(doctype, name)
    if current.get("script") != definition["script"]:
        client.call(
            "frappe.client.set_value",
            doctype=doctype,
            name=name,
            fieldname="script",
            value=definition["script"],
        )


# ------------------------------------------------------------------ each layer
def ensure_custom_fields(client: FrappeClient) -> list[str]:
    """Custom Fields autoname to ``{dt}-{fieldname}``, which is our idempotency key."""
    created = []
    for field in _fixture("custom_fields.json"):
        name = f"{field['dt']}-{field['fieldname']}"
        if not _exists(client, "Custom Field", name):
            client.insert({"doctype": "Custom Field", **field})
        created.append(name)
    return created


def ensure_property_setters(client: FrappeClient) -> list[str]:
    """Property Setters autoname to ``{doc_type}-{field_name}-{property}``."""
    created = []
    for setter in _fixture("property_setters.json"):
        name = f"{setter['doc_type']}-{setter['field_name']}-{setter['property']}"
        if not _exists(client, "Property Setter", name):
            client.insert({"doctype": "Property Setter", **setter})
        created.append(name)
    return created


def ensure_client_scripts(client: FrappeClient) -> list[str]:
    """Client Scripts are ``autoname: Prompt``, so the fixture supplies the name."""
    created = []
    for script in _fixture("client_scripts.json"):
        _sync_script(client, "Client Script", script)
        created.append(script["name"])
    return created


def ensure_server_scripts(client: FrappeClient) -> list[str]:
    """Push the Server Scripts, or raise :class:`ServerScriptsDisabled`.

    Order matters, and not for tidiness. Frappe happily *creates* a Server Script
    record while safe-exec is off and only refuses to **run** it — so a DocType
    Event script installed on a site with server scripts disabled makes every
    subsequent save of that doctype throw "Server Scripts are disabled". Creating
    them blind would brick Sales Invoice on the target.

    So the API-type script goes first as a canary: it is inert until explicitly
    called, we call it, and only if it actually executes do we install the DocType
    Event script. Note the flag is read via ``frappe.get_common_site_config()`` —
    it must be set in the bench's common_site_config.json; a per-site
    site_config.json entry is silently ignored.
    """
    scripts = {s["name"]: s for s in _fixture("server_scripts.json")}
    api_script = scripts[RT_API_SCRIPT]
    event_script = scripts[RT_EVENT_SCRIPT]

    _sync_script(client, "Server Script", api_script)

    try:
        client.call(RT_API_METHOD, probe_doc="{}", probe_filters="[]")
    except FrappeAPIError as exc:
        if "server script" in str(exc).lower():
            raise ServerScriptsDisabled(
                "Server scripts are disabled on the target. Set "
                '"server_script_enabled": 1 in the bench\'s common_site_config.json '
                "(a per-site site_config.json entry is ignored) to cover this layer."
            ) from exc
        raise

    _sync_script(client, "Server Script", event_script)
    return [RT_API_SCRIPT, RT_EVENT_SCRIPT]


def ensure_custom_doctypes(client: FrappeClient) -> list[str]:
    """Create the custom DocTypes; the child table must exist before its parent."""
    created = []
    for definition in _fixture("custom_doctypes.json"):
        name = definition["name"]
        if not _exists(client, "DocType", name):
            client.insert({"doctype": "DocType", **definition})
        created.append(name)
    return created


# ----------------------------------------------------------------- entry point
def ensure_customisations(client: FrappeClient) -> dict[str, Any]:
    """Provision the whole pack. Returns what exists, plus any layer that skipped.

    Only the Server Script layer is optional; everything else is expected to work
    on any site the engine can authenticate against.
    """
    result: dict[str, Any] = {
        "custom_fields": ensure_custom_fields(client),
        "property_setters": ensure_property_setters(client),
        "client_scripts": ensure_client_scripts(client),
        "custom_doctypes": ensure_custom_doctypes(client),
        "server_scripts": [],
        "server_scripts_skipped": None,
    }
    try:
        result["server_scripts"] = ensure_server_scripts(client)
    except ServerScriptsDisabled as exc:
        result["server_scripts_skipped"] = str(exc)
    return result
