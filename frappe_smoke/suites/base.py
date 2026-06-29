"""Suite + step abstractions.

A *suite* is a named, app-gated sequence of *steps*. Steps run in order and
share a mutable ``context`` dict, so a later step can use a record an earlier
step created (e.g. invoice the customer created two steps back). This ordered,
stateful model is why the harness uses a custom runner rather than pytest's
isolated test functions.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Callable

from ..client import FrappeClient
from ..gating import Versions

# A step takes the client and the shared per-suite context; it raises on failure.
StepFn = Callable[[FrappeClient, dict], None]


@dataclass
class Step:
    name: str
    fn: StepFn


class SmokeSuite:
    """Base class for an app's smoke suite.

    Subclasses set :attr:`name` and :attr:`required_app`, override
    :meth:`build_steps`, and may override :meth:`applies` for version gating.
    """

    name: str = ""
    required_app: str | None = None
    description: str = ""

    def applies(self, versions: Versions) -> bool:
        """Whether this suite should run against a site with these app versions.

        Default: run iff the required app is installed (or no app is required).
        Override to add version constraints.
        """
        if self.required_app is None:
            return True
        return self.required_app in versions

    def build_steps(self, versions: Versions) -> list[Step]:  # pragma: no cover - abstract
        raise NotImplementedError


@dataclass
class StepResult:
    suite: str
    step: str
    status: str  # "pass" | "fail" | "skip"
    duration_ms: int
    error: str | None = None


@dataclass
class SuiteResult:
    suite: str
    app: str | None
    app_version: str | None
    status: str  # "pass" | "fail" | "skip"
    steps: list[StepResult] = field(default_factory=list)
