"""Orchestration: run applicable suites against a target and collect results."""

from __future__ import annotations

import time
from dataclasses import dataclass, field

from .client import FrappeClient
from .gating import Versions, version_of
from .suites import all_suites
from .suites.base import SmokeSuite, StepResult, SuiteResult


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
    suite: SmokeSuite,
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
        except Exception as exc:  # noqa: BLE001 - we want any failure recorded, not raised
            elapsed = int((time.perf_counter() - started) * 1000)
            result.steps.append(StepResult(suite.name, step.name, "fail", elapsed, error=str(exc)))
            result.status = "fail"
            if not continue_on_fail:
                blocked = True

    if result.status != "fail" and all(s.status == "skip" for s in result.steps):
        result.status = "skip"
    return result


def run_target(
    label: str,
    url: str,
    client: FrappeClient,
    *,
    only_suite: str | None = None,
    continue_on_fail: bool = False,
) -> TargetResult:
    """Detect installed apps/versions, then run every applicable suite."""
    target_result = TargetResult(label=label, url=url)
    try:
        versions = client.get_versions()
    except Exception as exc:  # noqa: BLE001
        target_result.error = f"could not detect versions: {exc}"
        return target_result
    target_result.versions = versions

    for suite in all_suites():
        if only_suite and suite.name != only_suite:
            continue
        target_result.suites.append(
            run_suite(client, suite, versions, continue_on_fail=continue_on_fail)
        )
    return target_result
