"""App + version gating helpers.

All gating decisions are driven by the dict returned from
``FrappeClient.get_versions()`` — ``{app: {title, branch, version}}`` — so app
presence and version checks share a single source of truth.
"""

from __future__ import annotations

from typing import Any

from packaging.version import InvalidVersion, Version

Versions = dict[str, dict[str, Any]]


def app_installed(versions: Versions, app: str) -> bool:
    return app in versions


def version_of(versions: Versions, app: str) -> Version | None:
    """Return the parsed :class:`~packaging.version.Version` for an app, if known."""
    info = versions.get(app)
    if not info:
        return None
    raw = info.get("version")
    if not raw:
        return None
    try:
        return Version(str(raw))
    except InvalidVersion:
        return None


def at_least(versions: Versions, app: str, minimum: str) -> bool:
    """True when the installed app version is >= ``minimum``.

    Unknown/unparseable versions (e.g. a ``develop`` branch with no tag) are
    treated as "latest" and therefore satisfy any minimum.
    """
    current = version_of(versions, app)
    if current is None:
        return app_installed(versions, app)
    return current >= Version(minimum)


def major_of(versions: Versions, app: str) -> int | None:
    current = version_of(versions, app)
    return current.major if current else None
