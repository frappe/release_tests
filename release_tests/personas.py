"""Role-based test users ("personas") and a logged-in session for each.

Permission fixes only show up for ordinary users: Administrator bypasses the very
checks that change, so a suite run as Administrator stays green through every
permission regression. Each persona here is a real User with a fixed set of
ordinary roles, and :func:`login_as` returns a separate :class:`FrappeClient`
that is genuinely logged in as that user — the same session a person would get
in the browser, so what the server allows or refuses is exactly what they'd see.

Passwords follow :func:`factories.ensure_limited_user`: regenerated per process,
never written down, and reset on the target at the start of each run, so no
account this leaves behind has a password anyone holding the repo can use.
"""

from __future__ import annotations

import secrets
from dataclasses import dataclass

from .client import FrappeAPIError, FrappeClient

# Custom roles the permission-probe DocType grants rights to. They exist only for
# the probe, so no real DocType's permissions ever change.
RT_READER_ROLE = "RT Reader"
RT_EXPORTER_ROLE = "RT Exporter"
RT_OWNER_EXPORTER_ROLE = "RT Owner Exporter"
RT_CUSTOM_ROLES = (RT_READER_ROLE, RT_EXPORTER_ROLE, RT_OWNER_EXPORTER_ROLE)


@dataclass(frozen=True)
class Persona:
    key: str
    email: str
    first_name: str
    roles: tuple[str, ...]


PERSONAS: dict[str, Persona] = {
    p.key: p
    for p in (
        Persona("sales", "rt.sales@example.com", "RT Sales", ("Sales User",)),
        Persona("sales_mgr", "rt.salesmgr@example.com", "RT Sales Manager", ("Sales Manager",)),
        Persona("purchase", "rt.purchase@example.com", "RT Purchase", ("Purchase User",)),
        Persona("stock", "rt.stock@example.com", "RT Stock", ("Stock User",)),
        Persona(
            "item_mgr",
            "rt.itemmgr@example.com",
            "RT Item Manager",
            ("Item Manager", "Stock Manager"),
        ),
        Persona("accounts", "rt.accounts@example.com", "RT Accounts", ("Accounts User",)),
        Persona("hr", "rt.hr@example.com", "RT HR", ("HR User",)),
        # HR User limited by a User Permission to one Employee — see the HRMS suite.
        Persona("hr_scoped", "rt.hrscoped@example.com", "RT HR Scoped", ("HR User",)),
        Persona("employee", "rt.employee@example.com", "RT Employee", ("Employee",)),
        Persona("reader", "rt.reader@example.com", "RT Reader", (RT_READER_ROLE,)),
        Persona("exporter", "rt.exporter@example.com", "RT Exporter", (RT_EXPORTER_ROLE,)),
        Persona(
            "owner_exporter",
            "rt.ownerexporter@example.com",
            "RT Owner Exporter",
            (RT_OWNER_EXPORTER_ROLE,),
        ),
        # No roles at all: Frappe makes a role-less user a Website User (no desk).
        Persona("website", "rt.website@example.com", "RT Website", ()),
    )
}

_PASSWORD = secrets.token_urlsafe(24) + "aA1!"

# (base url, host, persona key) -> logged-in client, so a run logs each persona
# in once rather than once per step.
_SESSIONS: dict[tuple[str, str | None, str], FrappeClient] = {}
# Users whose password this run has already set. Setting a password logs out every
# session of that user, so doing it twice would silently turn a live persona
# session into a Guest one mid-run.
_PASSWORD_SET: set[tuple[str, str | None, str]] = set()


def ensure_custom_roles(client: FrappeClient) -> None:
    """Create the probe-only roles (desk access on) if missing."""
    for role in RT_CUSTOM_ROLES:
        if not client.get_list("Role", filters={"name": role}, fields=["name"], limit=1):
            client.insert({"doctype": "Role", "role_name": role, "desk_access": 1})


def ensure_user(client: FrappeClient, key: str) -> Persona:
    """Get-or-create the persona's User, enabled, with at least its roles, and this
    run's password. Roles are only ever added, never removed, so a person who
    reuses one of these accounts on a shared site doesn't lose what they added."""
    from .suites.base import SkipStep

    persona = PERSONAS[key]
    if any(r in RT_CUSTOM_ROLES for r in persona.roles):
        ensure_custom_roles(client)
    absent = [
        r
        for r in persona.roles
        if not client.get_list("Role", filters={"name": r}, fields=["name"], limit=1)
    ]
    if absent:
        # e.g. "HR User" on a site without HRMS: the persona can't exist here.
        raise SkipStep(
            f"role(s) {', '.join(absent)} not on this site; cannot create {persona.email}"
        )

    existing = client.get_list("User", filters={"name": persona.email}, fields=["name"], limit=1)
    if not existing:
        _PASSWORD_SET.add((client.url, client.session.headers.get("Host"), persona.email))
        client.insert(
            {
                "doctype": "User",
                "email": persona.email,
                "first_name": persona.first_name,
                "send_welcome_email": 0,
                "enabled": 1,
                "new_password": _PASSWORD,
                "roles": [{"role": role} for role in persona.roles],
            }
        )
        return persona

    run_key = (client.url, client.session.headers.get("Host"), persona.email)
    doc = client.get_doc("User", persona.email)
    have = {row.get("role") for row in doc.get("roles") or []}
    missing = [r for r in persona.roles if r not in have]
    if missing or not doc.get("enabled"):
        doc["roles"] = (doc.get("roles") or []) + [{"role": r} for r in missing]
        doc["enabled"] = 1
        client.call("frappe.client.save", doc=_json(doc))
    if run_key not in _PASSWORD_SET:
        client.call(
            "frappe.client.set_value",
            doctype="User",
            name=persona.email,
            fieldname="new_password",
            value=_PASSWORD,
        )
        _PASSWORD_SET.add(run_key)
    return persona


def login_as(client: FrappeClient, key: str) -> FrappeClient:
    """A separate session logged in as the persona (created on first use).

    The returned client carries ``persona`` so every check made through it can
    report who it ran as.
    """
    host = client.session.headers.get("Host")
    cache_key = (client.url, host, key)
    if cache_key in _SESSIONS:
        return _SESSIONS[cache_key]
    persona = ensure_user(client, key)
    session = FrappeClient(client.url, host_header=host, timeout=client.timeout)
    try:
        session.login(persona.email, _PASSWORD)
    except FrappeAPIError as exc:
        raise RuntimeError(
            f"could not log in as {persona.email} ({', '.join(persona.roles) or 'no roles'}): "
            f"HTTP {exc.status} {str(exc.server_messages)[:200]}"
        ) from exc
    session.persona = persona  # type: ignore[attr-defined]
    _SESSIONS[cache_key] = session
    return session


def guest(client: FrappeClient) -> FrappeClient:
    """An anonymous session (no login) against the same site."""
    session = FrappeClient(
        client.url, host_header=client.session.headers.get("Host"), timeout=client.timeout
    )
    session.persona = Persona("guest", "Guest", "Guest", ())  # type: ignore[attr-defined]
    return session


def describe(client: FrappeClient) -> tuple[str, tuple[str, ...]]:
    """(user, roles) a client acts as — for failure reports."""
    persona = getattr(client, "persona", None)
    if persona is not None:
        return persona.email, persona.roles
    return client.logged_in_user or "API token user (target credentials)", ("target admin",)


def _json(value) -> str:
    import json

    return json.dumps(value, default=str)
