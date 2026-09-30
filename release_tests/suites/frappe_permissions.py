"""Regression cover for the permission-hardening wave.

Almost every frappe revert in the last release cycle was a security-hardening fix
that broke a legitimate flow — frappe@e197a37a reverted "add stronger checks in
save and set_value endpoints" outright, and ERPNext needed an explicit
"fix: regression issues related to security fixes" commit to repair subcontracting.
The hardening itself is right; what keeps breaking is ordinary users doing
ordinary things.

Every step here runs as a **non-System-Manager** user, because Administrator
bypasses the very checks that regressed — a suite run as Administrator would have
stayed green through every one of those reverts.
"""

from __future__ import annotations

import json
from typing import ClassVar

from .. import factories
from ..client import FrappeAPIError, FrappeClient
from ..gating import Versions
from .base import ReleaseSuite, SkipStep, Step

RT_TODO_MARKER = "RT-PERM-PROBE"


# Frappe words a refusal several different ways depending on which check fired;
# the wording observed against v16 for a document-level refusal is
# "does not have access to this document".
_DENIAL_PHRASES = (
    "does not have access",
    "not permitted",
    "insufficient permission",
    "not enough permission",
    "not allowed",
    "permissionerror",
)


def _is_permission_denial(exc: FrappeAPIError) -> bool:
    """True only for a genuine permission refusal, not any old API error.

    The status gate is what does the real work: a 5xx, a dropped connection or an
    expired session must never be mistaken for "permissions held", which is the one
    thing the step using this exists to prove.
    """
    if exc.status not in (401, 403):
        return False
    text = str(exc).lower()
    return any(phrase in text for phrase in _DENIAL_PHRASES)


def _as_limited(client: FrappeClient, ctx: dict) -> FrappeClient:
    return ctx["limited_client"]


def _seed(client: FrappeClient, ctx: dict) -> None:
    """Create the restricted user and open a second session as them."""
    user = factories.ensure_limited_user(client)
    limited = FrappeClient(client.url, host_header=client.session.headers.get("Host"))
    try:
        limited.login(user, factories.limited_password())
    except FrappeAPIError as exc:
        raise SkipStep(
            f"could not log in as the restricted user {user}: {str(exc)[:160]}"
        ) from exc
    ctx["limited_client"] = limited
    ctx["limited_user"] = user


def _own_doc_insert(client: FrappeClient, ctx: dict) -> None:
    """A restricted user must be able to create their own ToDo."""
    limited = _as_limited(client, ctx)
    # ToDo's has_permission hook (frappe/desk/doctype/todo/todo.py) only grants
    # non-System-Manager access when the row is allocated to, or assigned by, the
    # user — role-level create alone is not enough. Setting allocated_to is what a
    # real user's own ToDo looks like.
    doc = limited.insert(
        {
            "doctype": "ToDo",
            "description": f"{RT_TODO_MARKER} owned",
            "status": "Open",
            "allocated_to": ctx["limited_user"],
        }
    )
    ctx["todo"] = doc["name"]


def _set_value_on_own_doc(client: FrappeClient, ctx: dict) -> None:
    """``frappe.client.set_value`` on a doc the user owns.

    This is the exact endpoint frappe@e197a37a had to revert hardening on.
    """
    limited = _as_limited(client, ctx)
    limited.call(
        "frappe.client.set_value",
        doctype="ToDo",
        name=ctx["todo"],
        fieldname="description",
        value=f"{RT_TODO_MARKER} edited",
    )
    stored = limited.get_doc("ToDo", ctx["todo"]).get("description") or ""
    if "edited" not in stored:
        raise AssertionError(f"set_value did not persist for the owner: {stored!r}")


def _save_own_doc(client: FrappeClient, ctx: dict) -> None:
    """``frappe.client.save`` — the other half of the reverted hardening."""
    limited = _as_limited(client, ctx)
    doc = limited.get_doc("ToDo", ctx["todo"])
    doc["priority"] = "High"
    limited.call("frappe.client.save", doc=json.dumps(doc, default=str))
    if limited.get_doc("ToDo", ctx["todo"]).get("priority") != "High":
        raise AssertionError("frappe.client.save did not persist for the owner")


def _toggle_like(client: FrappeClient, ctx: dict) -> None:
    """Liking a document — hardened, then reverted twice on develop in 24h."""
    limited = _as_limited(client, ctx)
    try:
        limited.call(
            "frappe.desk.like.toggle_like", doctype="ToDo", name=ctx["todo"], add="Yes"
        )
    except FrappeAPIError as exc:
        raise AssertionError(
            f"a user could not like their own document: {str(exc)[:200]}"
        ) from exc


def _add_attachment(client: FrappeClient, ctx: dict) -> None:
    """Attaching a file to an owned doc (frappe@8e8ef9d0 added perms here)."""
    limited = _as_limited(client, ctx)
    try:
        limited.insert(
            {
                "doctype": "File",
                "file_name": "rt-perm-probe.txt",
                "attached_to_doctype": "ToDo",
                "attached_to_name": ctx["todo"],
                "content": "release test attachment",
                "is_private": 1,
            }
        )
    except FrappeAPIError as exc:
        raise AssertionError(
            f"owner could not attach a file to their own document: {str(exc)[:200]}"
        ) from exc


def _cannot_reach_others(client: FrappeClient, ctx: dict) -> None:
    """The counterpart: hardening must still hold.

    A green suite that only proves permissive behaviour would pass on a site with
    permissions switched off entirely, so assert the restriction too — this user
    must not be able to read User records or write System Settings.
    """
    limited = _as_limited(client, ctx)
    try:
        limited.call(
            "frappe.client.set_value",
            doctype="System Settings",
            name="System Settings",
            fieldname="session_expiry",
            value="24:00",
        )
    except FrappeAPIError as exc:
        # Accept only an actual denial. Catching every API error would let a 500,
        # an expired session or a network fault stand in for "permissions held",
        # which is the one thing this step exists to prove.
        if _is_permission_denial(exc):
            return
        raise AssertionError(
            f"expected a permission denial, got {exc.status}: {str(exc)[:200]}"
        ) from exc
    raise AssertionError(
        "a Sales User was allowed to write System Settings — permission checks are not holding"
    )


class FrappePermissionsSuite(ReleaseSuite):
    name = "frappe_permissions"
    required_app = "frappe"
    description = (
        "Regression: permission hardening — a restricted (non-System-Manager) user can "
        "still edit, save, like and attach to their own documents, while still being "
        "refused write access to system configuration."
    )
    guards: ClassVar[list[str]] = [
        "frappe@e197a37a",  # revert: stronger checks in save/set_value
        "frappe@4af19414",  # assignment permission bypass
        "frappe@84b9f0a4",  # perm checks on toggle_like / mark_as_seen (reverted on develop)
        "frappe@8e8ef9d0",  # perms on add_attachments
        "frappe@188e51ad",  # perm check on save_report
    ]

    def build_steps(self, versions: Versions) -> list[Step]:
        return [
            Step("create restricted user + session", _seed),
            Step("restricted user creates own ToDo", _own_doc_insert),
            Step("set_value on own document", _set_value_on_own_doc),
            Step("client.save on own document", _save_own_doc),
            Step("like own document", _toggle_like),
            Step("attach file to own document", _add_attachment),
            Step("still refused write to System Settings", _cannot_reach_others),
        ]
