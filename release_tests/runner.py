"""Orchestration: run applicable suites against a target and collect results."""

from __future__ import annotations

import fnmatch
import time
from dataclasses import dataclass, field

from .client import FrappeAPIError, FrappeClient
from .gating import Versions, version_of
from .suites import all_suites
from .suites.base import CheckFailed, ReleaseSuite, SkipStep, StepResult, SuiteResult


@dataclass
class TargetResult:
    label: str
    url: str
    versions: Versions = field(default_factory=dict)
    suites: list[SuiteResult] = field(default_factory=list)
    error: str | None = None  # set if the target could not be reached/authed at all

    @property
    def ok(self) -> bool:
        if self.error:
            return False
        return all(s.status != "fail" for s in self.suites)


def _version_str(versions: Versions, app: str | None) -> str | None:
    if not app:
        return None
    v = version_of(versions, app)
    if v is not None:
        return str(v)
    info = versions.get(app) or {}
    return info.get("branch") or info.get("version")


def run_suite(
    client: FrappeClient,
    suite: ReleaseSuite,
    versions: Versions,
    *,
    continue_on_fail: bool = False,
) -> SuiteResult:
    """Run one suite's ordered steps, sharing a context dict across them."""
    app_version = _version_str(versions, suite.required_app)
    result = SuiteResult(
        suite=suite.name, app=suite.required_app, app_version=app_version, status="pass"
    )

    if not suite.applies(versions):
        result.status = "skip"
        result.skip_reason = "app not installed or version not supported"
        return result

    try:
        reason = suite.precheck(client)
    except Exception as exc:  # noqa: BLE001 - a broken probe is a failure, not a skip
        reason = None
        result.status = "fail"
        result.steps.append(
            StepResult(suite.name, "precheck", "fail", 0, error=str(exc), details=_details(exc))
        )
        return result
    if reason:
        result.status = "skip"
        result.skip_reason = reason
        return result

    context: dict = {}
    blocked = False
    for step in suite.build_steps(versions):
        if blocked:
            result.steps.append(
                StepResult(suite.name, step.name, "skip", 0, error="blocked by earlier failure")
            )
            continue
        started = time.perf_counter()
        try:
            step.fn(client, context)
            elapsed = int((time.perf_counter() - started) * 1000)
            result.steps.append(StepResult(suite.name, step.name, "pass", elapsed))
        except SkipStep as exc:
            # Best-effort step whose precondition isn't met — record + keep going.
            elapsed = int((time.perf_counter() - started) * 1000)
            result.steps.append(StepResult(suite.name, step.name, "skip", elapsed, error=str(exc)))
        except Exception as exc:  # noqa: BLE001 - we want any failure recorded, not raised
            elapsed = int((time.perf_counter() - started) * 1000)
            result.steps.append(
                StepResult(
                    suite.name, step.name, "fail", elapsed, error=str(exc), details=_details(exc)
                )
            )
            result.status = "fail"
            if step.blocks_on_fail or not (continue_on_fail or suite.independent_steps):
                blocked = True

    if result.status != "fail" and all(s.status == "skip" for s in result.steps):
        result.status = "skip"
    return result


# What a failure means, for the run summary. The suites exist to catch problems end
# users would hit, so a failure is only a *finding* when the product misbehaved; one
# caused by the harness itself is a gap in coverage, not a result.
ISSUE = "issue"  # the product misbehaved (wrong permission/result, or a server error)
TRIAGE = "needs triage"  # the server rejected a step unexpectedly: regression or test data?
HARNESS = "harness"  # the test itself broke (code error, lost session) — no verdict reached


def _details(exc: Exception) -> dict:
    from .checks import server_said

    """Structured failure context for the report.

    A :class:`CheckFailed` carries its own; an unexpected API error still has an
    HTTP status and a server message worth surfacing separately from the traceback
    text, so the reader sees *what the server said* without parsing the error line.
    """
    if isinstance(exc, CheckFailed):
        hint = exc.details.get("hint") or ""
        harness = "session was lost" in hint or "CSRF" in hint
        return {**exc.details, "kind": HARNESS if harness else ISSUE}
    if isinstance(exc, FrappeAPIError):
        if exc.status == 400 and "invalid request" in f"{exc} {exc.server_messages}".lower():
            return {
                "check": "the test's request was refused as a CSRF failure",
                "actual": server_said(exc),
                "kind": HARNESS,
                "hint": "CSRF token missing on the test's request — fix the test",
            }
        server_error = bool(exc.status and exc.status >= 500)
        return {
            "check": "unexpected server error while running the step",
            "actual": server_said(exc),
            "kind": ISSUE if server_error else TRIAGE,
            "hint": "a user doing this would hit the same server error"
            if server_error
            else "the server refused a step the test expected to work — a regression, "
            "or test data this site doesn't accept",
        }
    return {
        "check": "the test itself raised an error",
        "actual": f"{type(exc).__name__}: {exc}",
        "kind": HARNESS,
        "hint": "fix the test; this area was not actually checked",
    }


def suite_selected(name: str, only_suite: str | None) -> bool:
    """Whether ``name`` matches ``--suite``: a name, a glob (``v16p_*``) or a comma list."""
    if not only_suite:
        return True
    return any(
        fnmatch.fnmatchcase(name, pattern.strip())
        for pattern in only_suite.split(",")
        if pattern.strip()
    )


def run_target(
    label: str,
    url: str,
    client: FrappeClient,
    *,
    only_suite: str | None = None,
    suite_filter: set[str] | None = None,
    continue_on_fail: bool = False,
) -> TargetResult:
    """Detect installed apps/versions, then run every applicable suite.

    ``only_suite`` runs just one named suite; ``suite_filter`` restricts to a set
    of suite names (used by the release_manager control plane to run a selection).
    """
    target_result = TargetResult(label=label, url=url)
    try:
        versions = client.get_versions()
    except Exception as exc:  # noqa: BLE001
        target_result.error = f"could not detect versions: {exc}"
        return target_result
    target_result.versions = versions

    for suite in all_suites():
        if not suite_selected(suite.name, only_suite):
            continue
        if suite_filter is not None and suite.name not in suite_filter:
            continue
        target_result.suites.append(
            run_suite(client, suite, versions, continue_on_fail=continue_on_fail)
        )
    return target_result
