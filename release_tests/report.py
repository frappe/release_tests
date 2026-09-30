"""Reporting: human-readable console table + machine-readable JSON."""

from __future__ import annotations

import dataclasses
import json
from datetime import datetime, timezone
from pathlib import Path

from .runner import TargetResult

_SYMBOL = {"pass": "PASS", "fail": "FAIL", "skip": "SKIP"}

# Order and wording of a failure's details, as the reader should scan them:
# what was checked, as whom, what should have happened, what did happen, where.
_DETAIL_LABELS = (
    ("kind", "Kind"),
    ("check", "Check"),
    ("user", "User"),
    ("roles", "Roles"),
    ("expected", "Expected"),
    ("actual", "Actual"),
    ("endpoint", "Endpoint"),
    ("guards", "Guards"),
    ("hint", "Hint"),
)


def _detail_lines(details: dict | None) -> list[tuple[str, str]]:
    if not details:
        return []
    lines = []
    for key, label in _DETAIL_LABELS:
        value = details.get(key)
        if value:
            lines.append((label, ", ".join(value) if isinstance(value, list) else str(value)))
    return lines


def print_console(results: list[TargetResult]) -> None:
    for tr in results:
        header = f"Target: {tr.label}  ({tr.url})"
        print("\n" + header)
        print("=" * len(header))
        if tr.error:
            print(f"  ERROR: {tr.error}")
            continue
        if tr.versions:
            apps = ", ".join(
                f"{app} {info.get('version') or info.get('branch') or '?'}"
                for app, info in sorted(tr.versions.items())
            )
            print(f"  Apps: {apps}")
        for sr in tr.suites:
            label = sr.suite + (f" ({sr.app_version})" if sr.app_version else "")
            print(f"\n  [{_SYMBOL[sr.status]}] suite: {label}")
            if sr.skip_reason:
                print(f"            -> {sr.skip_reason}")
            for step in sr.steps:
                line = f"      {_SYMBOL[step.status]:4}  {step.step}  ({step.duration_ms} ms)"
                print(line)
                detail_lines = _detail_lines(step.details) if step.status == "fail" else []
                if detail_lines:
                    for label, value in detail_lines:
                        print(f"            {label + ':':10} {value}")
                elif step.error:
                    print(f"            -> {step.error}")
    _print_summary(results)


def summarise(results: list[TargetResult]) -> dict[str, int]:
    """Counts for the run summary.

    ``run_rate`` is the headline: the share of steps that reached a genuine verdict
    (passed, or found an issue). Skips and harness failures learned nothing about the
    product, so a run full of them is a weak run however green it looks.
    """
    counts = {"total": 0, "pass": 0, "issue": 0, "needs triage": 0, "harness": 0, "skip": 0}
    for tr in results:
        for sr in tr.suites:
            for step in sr.steps:
                counts["total"] += 1
                if step.status == "fail":
                    counts[(step.details or {}).get("kind", "needs triage")] += 1
                else:
                    counts[step.status] += 1
    reached = counts["pass"] + counts["issue"]
    counts["run_rate"] = round(100 * reached / counts["total"]) if counts["total"] else 0
    return counts


def _print_summary(results: list[TargetResult]) -> None:
    c = summarise(results)
    print("\n" + "-" * 60)
    print(
        f"Run rate: {c['run_rate']}%  ({c['pass'] + c['issue']} of {c['total']} checks reached a verdict)"
    )
    print(f"  Issues found:      {c['issue']}")
    print(f"  Needs triage:      {c['needs triage']}")
    print(f"  Passed:            {c['pass']}")
    print(f"  Not checked:       {c['skip']} skipped, {c['harness']} broken tests")
    print("Overall:", "PASS" if all(tr.ok for tr in results) else "FAIL")


def write_json(results: list[TargetResult], out_dir: str | Path = "results") -> Path:
    out_dir = Path(out_dir)
    out_dir.mkdir(parents=True, exist_ok=True)
    ts = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
    path = out_dir / f"release-{ts}.json"
    payload = {
        "generated_at": ts,
        "overall": "pass" if all(tr.ok for tr in results) else "fail",
        "summary": summarise(results),
        "targets": [dataclasses.asdict(tr) for tr in results],
    }
    path.write_text(json.dumps(payload, indent=2, default=str))
    write_failures(results, path.with_name(f"release-{ts}-failures.md"))
    return path


def write_failures(results: list[TargetResult], path: str | Path) -> Path | None:
    """Write a Markdown list of every failed step, one block per failure.

    The JSON report is complete but not something a person reads; this is the page
    to hand whoever fixes things. Each block says what was checked, the user and
    roles it ran as, expected vs actual, and the endpoint and upstream change, so the
    failure can be acted on without re-running the suite. Returns None (and writes
    nothing) when there are no failures.
    """
    order = {"issue": 0, "needs triage": 1, "harness": 2}
    blocks: list[tuple[int, str]] = []
    for tr in results:
        if tr.error:
            blocks.append((2, f"### {tr.label}: could not run\n\n- **Error:** {tr.error}\n"))
            continue
        for sr in tr.suites:
            for step in sr.steps:
                if step.status != "fail":
                    continue
                lines = [f"### {tr.label} · {sr.suite} · {step.step}", ""]
                detail_lines = _detail_lines(step.details)
                for label, value in detail_lines:
                    lines.append(f"- **{label}:** {value}")
                if not detail_lines or not (step.details or {}).get("actual"):
                    lines.append(f"- **Error:** {step.error}")
                kind = (step.details or {}).get("kind", "needs triage")
                blocks.append((order.get(kind, 1), "\n".join(lines) + "\n"))
    if not blocks:
        return None
    path = Path(path)
    c = summarise(results)
    header = (
        f"# Release test failures ({len(blocks)})\n\n"
        f"Run rate {c['run_rate']}% — {c['issue']} issue(s) found, {c['needs triage']} to triage, "
        f"{c['harness']} broken test(s), {c['skip']} skipped. Issues first.\n\n"
    )
    path.write_text(header + "\n".join(text for _, text in sorted(blocks, key=lambda b: b[0])))
    return path


def overall_ok(results: list[TargetResult]) -> bool:
    return all(tr.ok for tr in results)
