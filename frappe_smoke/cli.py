"""Command-line entry point: ``frappe-smoke {run,list-suites,detect}``."""

from __future__ import annotations

import argparse
import sys

from . import __version__
from .config import connect, load_targets, select_targets
from .report import overall_ok, print_console, write_json
from .runner import run_target
from .suites import suite_names


def _cmd_list_suites(args: argparse.Namespace) -> int:
    for name in suite_names():
        print(name)
    return 0


def _cmd_detect(args: argparse.Namespace) -> int:
    targets = select_targets(load_targets(args.config), args.target)
    for target in targets:
        print(f"\n{target.label} ({target.url})")
        try:
            client = connect(target)
            versions = client.get_versions()
        except Exception as exc:  # noqa: BLE001
            print(f"  ERROR: {exc}")
            continue
        for app, info in sorted(versions.items()):
            print(f"  {app:24} {info.get('version') or '?':12} {info.get('branch') or ''}")
    return 0


def _cmd_run(args: argparse.Namespace) -> int:
    targets = select_targets(load_targets(args.config), args.target)
    results = []
    for target in targets:
        try:
            client = connect(target)
        except Exception as exc:  # noqa: BLE001
            from .runner import TargetResult

            tr = TargetResult(label=target.label, url=target.url)
            tr.error = f"connection/auth failed: {exc}"
            results.append(tr)
            continue
        results.append(
            run_target(
                target.label,
                target.url,
                client,
                only_suite=args.suite,
                continue_on_fail=args.continue_on_fail,
            )
        )

    print_console(results)
    if not args.no_json:
        path = write_json(results, args.results_dir)
        print(f"\nJSON report: {path}")
    return 0 if overall_ok(results) else 1


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(prog="frappe-smoke", description=__doc__)
    parser.add_argument("--version", action="version", version=f"%(prog)s {__version__}")
    sub = parser.add_subparsers(dest="command", required=True)

    def add_target_args(p: argparse.ArgumentParser) -> None:
        p.add_argument("--config", default="targets.toml", help="path to targets TOML")
        p.add_argument("--target", default="all", help="target label or 'all'")

    p_list = sub.add_parser("list-suites", help="list registered suites")
    p_list.set_defaults(func=_cmd_list_suites)

    p_detect = sub.add_parser("detect", help="print installed apps + versions for a target")
    add_target_args(p_detect)
    p_detect.set_defaults(func=_cmd_detect)

    p_run = sub.add_parser("run", help="run smoke suites against target(s)")
    add_target_args(p_run)
    p_run.add_argument("--suite", default=None, help="run only this suite (default: all)")
    p_run.add_argument(
        "--continue-on-fail",
        action="store_true",
        help="keep running a suite's steps after a failure (default: block dependents)",
    )
    p_run.add_argument("--results-dir", default="results", help="directory for JSON reports")
    p_run.add_argument("--no-json", action="store_true", help="skip writing the JSON report")
    p_run.set_defaults(func=_cmd_run)

    return parser


def main(argv: list[str] | None = None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)
    return args.func(args)


if __name__ == "__main__":
    sys.exit(main())
