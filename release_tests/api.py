"""Programmatic API for embedding the engine in other apps (e.g. release_manager).

Everything here takes/returns plain dicts and lists so a caller (a Frappe app's
background job) never needs to touch the engine's dataclasses.
"""

from __future__ import annotations

import dataclasses
from typing import Any, Iterable

from .config import Target, connect
from .runner import run_target
from .suites import all_suites


def catalog() -> list[dict[str, Any]]:
    """Describe every registered suite for the Test Case master.

    Steps are introspected with an empty versions dict (our suites don't branch
    on version at build time), giving a stable preview without a live site.
    """
    entries = []
    for suite in all_suites():
        try:
            steps = [step.name for step in suite.build_steps({})]
        except Exception:  # noqa: BLE001 - a malformed suite shouldn't break sync
            steps = []
        entries.append(
            {
                "suite": suite.name,
                "required_app": suite.required_app,
                "description": getattr(suite, "description", "") or "",
                "steps": steps,
            }
        )
    return entries


def _target_from_config(site_config: dict[str, Any]) -> Target:
    return Target(
        label=site_config["label"],
        url=site_config["url"],
        auth=site_config.get("auth", "login"),
        username=site_config.get("username"),
        password=site_config.get("password"),
        api_key=site_config.get("api_key"),
        api_secret=site_config.get("api_secret"),
        host_header=site_config.get("host_header"),
    )


def detect_site(site_config: dict[str, Any]) -> dict[str, Any]:
    """Connect and return ``{app: {title, branch, version}}`` for a site."""
    client = connect(_target_from_config(site_config))
    return client.get_versions()


def run_site(
    site_config: dict[str, Any],
    suites: Iterable[str] | None = None,
    *,
    continue_on_fail: bool = False,
) -> dict[str, Any]:
    """Run selected suites against one site; return the result as a plain dict."""
    target = _target_from_config(site_config)
    client = connect(target)
    result = run_target(
        target.label,
        target.url,
        client,
        suite_filter=set(suites) if suites else None,
        continue_on_fail=continue_on_fail,
    )
    data = dataclasses.asdict(result)
    data["transactions"] = client.submitted_count
    return data


def iter_run_site(
    site_config: dict[str, Any],
    suites: Iterable[str] | None = None,
    *,
    continue_on_fail: bool = False,
):
    """Run selected suites, yielding an event as each suite finishes.

    Events (plain dicts): ``{"type":"versions",...}`` first, then one
    ``{"type":"suite","suite":{...}}`` per suite as it completes, then
    ``{"type":"done","transactions":N}``. On connect/detect failure a single
    ``{"type":"error","error":...}`` is yielded. Lets a caller persist each
    suite result live for a real-time UI, instead of only after the whole run.
    """
    from .runner import run_suite

    target = _target_from_config(site_config)
    try:
        client = connect(target)
        versions = client.get_versions()
    except Exception as exc:  # noqa: BLE001
        yield {"type": "error", "error": str(exc)}
        return

    yield {"type": "versions", "versions": versions}
    wanted = set(suites) if suites else None
    for suite in all_suites():
        if wanted is not None and suite.name not in wanted:
            continue
        result = run_suite(client, suite, versions, continue_on_fail=continue_on_fail)
        yield {"type": "suite", "suite": dataclasses.asdict(result)}
    yield {"type": "done", "transactions": client.submitted_count, "versions": versions}
