"""Reporting: human-readable console table + machine-readable JSON."""

from __future__ import annotations

import dataclasses
import json
from datetime import datetime, timezone
from pathlib import Path

from .runner import TargetResult

_SYMBOL = {"pass": "PASS", "fail": "FAIL", "skip": "SKIP"}


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
            for step in sr.steps:
                line = f"      {_SYMBOL[step.status]:4}  {step.step}  ({step.duration_ms} ms)"
                print(line)
                if step.error:
                    print(f"            -> {step.error}")
    _print_summary(results)


def _print_summary(results: list[TargetResult]) -> None:
    total = passed = failed = skipped = 0
    for tr in results:
        for sr in tr.suites:
            for step in sr.steps:
                total += 1
                passed += step.status == "pass"
                failed += step.status == "fail"
                skipped += step.status == "skip"
    print("\n" + "-" * 40)
    print(f"Steps: {total}  pass={passed}  fail={failed}  skip={skipped}")
    print("Overall:", "PASS" if all(tr.ok for tr in results) else "FAIL")


def write_json(results: list[TargetResult], out_dir: str | Path = "results") -> Path:
    out_dir = Path(out_dir)
    out_dir.mkdir(parents=True, exist_ok=True)
    ts = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
    path = out_dir / f"smoke-{ts}.json"
    payload = {
        "generated_at": ts,
        "overall": "pass" if all(tr.ok for tr in results) else "fail",
        "targets": [dataclasses.asdict(tr) for tr in results],
    }
    path.write_text(json.dumps(payload, indent=2, default=str))
    return path


def overall_ok(results: list[TargetResult]) -> bool:
    return all(tr.ok for tr in results)
