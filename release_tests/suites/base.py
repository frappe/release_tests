"""Suite + step abstractions.

A *suite* is a named, app-gated sequence of *steps*. Steps run in order and
share a mutable ``context`` dict, so a later step can use a record an earlier
step created (e.g. invoice the customer created two steps back). This ordered,
stateful model is why the harness uses a custom runner rather than pytest's
isolated test functions.
"""

from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass, field
from typing import Any, ClassVar

from ..client import FrappeClient
from ..gating import Versions

# A step takes the client and the shared per-suite context; it raises on failure.
StepFn = Callable[[FrappeClient, dict], None]


class SkipStep(Exception):
    """Raised by a step to record itself as skipped rather than failed.

    For best-effort steps whose precondition isn't met on a given site (e.g. the
    e-invoice step when the India Compliance API isn't configured). A skip does
    not block the suite — later steps still run.
    """


class CheckFailed(AssertionError):
    """A failed check that says exactly what broke, for whom, and where.

    A bare ``AssertionError("refused")`` tells the reader something failed; this
    tells them what to fix. ``details`` lands verbatim on the step's result, so the
    console, the JSON report and the failures summary all carry the same facts:
    the condition checked, the user and roles it ran as, what was expected, what
    actually came back, the endpoint touched and the upstream change it guards.
    """

    def __init__(
        self,
        check: str,
        *,
        expected: str,
        actual: str,
        user: str | None = None,
        roles: list[str] | tuple[str, ...] | None = None,
        endpoint: str | None = None,
        guards: str | None = None,
        hint: str | None = None,
    ):
        who = f" [as {user}]" if user else ""
        super().__init__(f"{check}{who}: expected {expected}; got {actual}")
        self.details: dict[str, Any] = {
            k: v
            for k, v in {
                "check": check,
                "user": user,
                "roles": list(roles) if roles else None,
                "expected": expected,
                "actual": actual,
                "endpoint": endpoint,
                "guards": guards,
                "hint": hint,
            }.items()
            if v
        }


@dataclass
class Step:
    name: str
    fn: StepFn
    # A step the rest depend on (e.g. setup). If it fails, later steps are blocked
    # even in an independent_steps suite, rather than failing with confusing errors.
    blocks_on_fail: bool = False


class ReleaseSuite:
    """Base class for an app's release suite.

    Subclasses set :attr:`name` and :attr:`required_app`, override
    :meth:`build_steps`, and may override :meth:`applies` for version gating.
    """

    name: str = ""
    required_app: str | None = None
    description: str = ""
    # Upstream changes this suite guards, as "app@commit" or "app#pr" strings.
    # Regression suites cite what broke so a reviewer can see why the suite exists;
    # flow suites leave it empty.
    guards: ClassVar[list[str]] = []
    # True when steps don't depend on each other: a failure then doesn't stop the
    # rest from running. Flow suites (create → submit → pay) leave it False, since
    # later steps need what earlier ones made.
    independent_steps: ClassVar[bool] = False

    def applies(self, versions: Versions) -> bool:
        """Whether this suite should run against a site with these app versions.

        Default: run iff the required app is installed (or no app is required).
        Override to add version constraints.
        """
        if self.required_app is None:
            return True
        return self.required_app in versions

    def precheck(self, client: FrappeClient) -> str | None:
        """Probe the live site before any step runs; return a reason to skip, or None.

        :meth:`applies` only sees version numbers, which cannot tell a
        ``version-16-polished`` site from a plain ``version-16`` one — both report
        16.x. Suites for a specific release override this to look for something
        only that release ships.
        """
        return None

    def build_steps(self, versions: Versions) -> list[Step]:  # pragma: no cover - abstract
        raise NotImplementedError


@dataclass
class StepResult:
    suite: str
    step: str
    status: str  # "pass" | "fail" | "skip"
    duration_ms: int
    error: str | None = None
    # Structured context for a failure (see CheckFailed): check, user, roles,
    # expected, actual, endpoint, guards, hint.
    details: dict[str, Any] | None = None


@dataclass
class SuiteResult:
    suite: str
    app: str | None
    app_version: str | None
    status: str  # "pass" | "fail" | "skip"
    steps: list[StepResult] = field(default_factory=list)
    skip_reason: str | None = None
