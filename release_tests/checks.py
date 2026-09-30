"""Assertions that explain themselves.

Every helper here raises :class:`CheckFailed` with the full picture — the
condition checked, the user and roles it ran as, expected vs actual (including
the HTTP status and server message), the endpoint, and the upstream change it
guards — so a red step in the report says what to fix, not just that something
broke.
"""

from __future__ import annotations

from collections.abc import Callable
from typing import Any

from .client import FrappeAPIError, FrappeClient
from .personas import describe
from .suites.base import CheckFailed

# How a 403 reads when the session is gone rather than the action refused. A dead
# session must never pass as "permission held" — it would hide exactly the kind
# of breakage these suites exist to catch.
_SESSION_LOST = ("user guest", "login to access", "session expired", "not logged in")


def is_denial(exc: FrappeAPIError) -> bool:
    """A genuine permission refusal — not a 5xx, a validation error or a lost session.

    Frappe words refusals many ways (and some arrive with no message at all), so a
    401/403 counts unless it says the caller is Guest.
    """
    if exc.status not in (401, 403):
        return False
    return not any(marker in str(exc).lower() for marker in _SESSION_LOST)


def _csrf_refused(exc: FrappeAPIError) -> bool:
    """Frappe's CSRF refusal: HTTP 400 "Invalid Request". A browser never hits it, so
    it is always the test's own session handling, never something a user would see."""
    text = f"{exc} {exc.server_messages}".lower()
    return exc.status == 400 and "invalid request" in text


_CSRF_HINT = (
    "CSRF token missing on the test's request (HTTP 400 Invalid Request) — a test-harness "
    "problem, not something a user would see"
)


def server_said(exc: FrappeAPIError) -> str:
    return f"HTTP {exc.status}: {_clean(exc.server_messages)}"


def expect_allowed(
    who: FrappeClient,
    check: str,
    fn: Callable[[], Any],
    *,
    endpoint: str,
    guards: str | None = None,
    hint: str | None = None,
) -> Any:
    """Run ``fn`` as ``who``; fail with details if the server refuses or errors."""
    try:
        return fn()
    except FrappeAPIError as exc:
        user, roles = describe(who)
        lost = exc.status in (401, 403) and any(m in str(exc).lower() for m in _SESSION_LOST)
        raise CheckFailed(
            check,
            expected="allowed",
            actual=server_said(exc),
            user=user,
            roles=roles,
            endpoint=endpoint,
            guards=guards,
            hint="the persona's session was lost (request ran as Guest) — a harness or "
            "login problem, not a verdict on the permission"
            if lost
            else _CSRF_HINT
            if _csrf_refused(exc)
            else hint,
        ) from exc


def expect_denied(
    who: FrappeClient,
    check: str,
    fn: Callable[[], Any],
    *,
    endpoint: str,
    guards: str | None = None,
    hint: str | None = None,
) -> FrappeAPIError:
    """Run ``fn`` as ``who``; pass only on a genuine permission refusal."""
    user, roles = describe(who)
    try:
        fn()
    except FrappeAPIError as exc:
        if is_denial(exc):
            return exc
        lost = exc.status in (401, 403)
        raise CheckFailed(
            check,
            expected="refused with a permission error (HTTP 403)",
            actual=server_said(exc),
            user=user,
            roles=roles,
            endpoint=endpoint,
            guards=guards,
            hint="the persona's session was lost (request ran as Guest) — a harness or "
            "login problem, not a verdict on the permission"
            if lost
            else _CSRF_HINT
            if _csrf_refused(exc)
            else hint or "the call failed, but not because of permissions",
        ) from exc
    raise CheckFailed(
        check,
        expected="refused with a permission error (HTTP 403)",
        actual="the request succeeded — the user was allowed",
        user=user,
        roles=roles,
        endpoint=endpoint,
        guards=guards,
        hint=hint or "permission check missing or too loose — a security regression",
    )


def expect_rejected(
    who: FrappeClient,
    check: str,
    fn: Callable[[], Any],
    *,
    message: str,
    endpoint: str,
    guards: str | None = None,
    hint: str | None = None,
) -> FrappeAPIError:
    """Run ``fn``; pass only when the server rejects it with ``message`` in the error.

    For validation refusals (HTTP 417 and friends), where the wording is the thing
    under test — e.g. "Employee must be a non-empty string."
    """
    user, roles = describe(who)
    expected = f"rejected with “{message}”"
    try:
        fn()
    except FrappeAPIError as exc:
        if message.lower() in str(exc).lower():
            return exc
        raise CheckFailed(
            check,
            expected=expected,
            actual=server_said(exc),
            user=user,
            roles=roles,
            endpoint=endpoint,
            guards=guards,
            hint=_CSRF_HINT if _csrf_refused(exc) else hint,
        ) from exc
    raise CheckFailed(
        check,
        expected=expected,
        actual="the request succeeded",
        user=user,
        roles=roles,
        endpoint=endpoint,
        guards=guards,
        hint=hint,
    )


def ensure(
    condition: bool,
    check: str,
    *,
    expected: str,
    actual: Any,
    who: FrappeClient | None = None,
    endpoint: str | None = None,
    guards: str | None = None,
    hint: str | None = None,
) -> None:
    """Plain assertion with the same failure details as the helpers above."""
    if condition:
        return
    user, roles = describe(who) if who is not None else (None, None)
    raise CheckFailed(
        check,
        expected=expected,
        actual=str(actual),
        user=user,
        roles=roles,
        endpoint=endpoint,
        guards=guards,
        hint=hint,
    )


def _clean(messages: Any) -> str:
    """Server messages arrive as JSON-in-JSON with HTML; flatten to one readable line."""
    import json
    import re

    text = messages
    if isinstance(messages, str):
        try:
            parsed = json.loads(messages)
            if isinstance(parsed, list):
                parts = []
                for item in parsed:
                    try:
                        item = json.loads(item)
                    except (TypeError, ValueError):
                        pass
                    parts.append(item.get("message", item) if isinstance(item, dict) else item)
                text = " | ".join(str(p) for p in parts)
        except ValueError:
            pass
    text = re.sub(r"<[^>]+>", "", str(text))
    text = re.sub(r"\s+", " ", text).strip()
    # A traceback's last line is the useful part.
    if "Traceback" in text:
        text = text.rsplit("Error:", 1)[-1].strip() if "Error:" in text else text[-300:]
    return text[:300]
