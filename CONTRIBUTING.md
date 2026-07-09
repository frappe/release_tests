# Contributing to release_tests

`release_tests` is the **execution engine** behind Release Manager: a standalone
HTTP harness that logs into a running Frappe site and drives realistic
**release flows** (log in → create master data → push a transaction through),
adapting to whatever app **version** is present, and reports pass/fail per app
and step.

Its whole reason to exist is to **catch regressions across Frappe app releases
before they reach production**. Keep that goal in mind for every change.

## Golden rules

1. **Stay Frappe-free.** The engine speaks HTTP only — never `import frappe`.
   That is what lets it run in CI and against remote/press sites.
2. **Non-destructive & idempotent.** A suite must create its own data and be
   safe to re-run against a live site. Never delete or mutate data you did not
   create. Prefer the idempotent helpers in `release_tests/factories.py`.
3. **Version-aware.** Branch behaviour with `gating.at_least(versions, app, "16")`
   rather than assuming a single version.
4. **Skip cleanly.** If a suite's `required_app` isn't installed, it must be
   skipped, not failed.
5. **Never commit credentials.** Real targets live in a gitignored `targets.toml`;
   use `$ENV_VAR` references. `results/` is gitignored too — don't commit run
   artifacts.

## Dev setup

```bash
uv venv && uv pip install -e ".[dev]"   # dev extras: pytest, responses, ruff
cp targets.example.toml targets.toml    # fill in creds (gitignored)
export RELEASE_ADMIN_PW='...'
```

## Before you open a PR

```bash
uv run pytest                       # fully mocked — no live site needed
uvx ruff check release_tests tests  # lint (same command CI runs)
```

If your change affects real flows, also run it against a live site and note
which versions you exercised:

```bash
release-tests run --target v16-local
```

## Adding or extending a suite

Subclass `ReleaseSuite`, set `name` + `required_app`, and return ordered `Step`s
from `build_steps`. Steps share a `context` dict so later steps can reuse records
created by earlier ones. Keep each step idempotent and non-destructive, and gate
any version-specific behaviour. If the suite maps to a Release Manager catalog
entry, make sure `list-suites` reports it so **Sync Catalog** picks it up.

## Pull requests

- Fork, branch, and open a PR against `main`.
- `main` is protected: **1 approving review** is required and **CI must pass**
  before merge. Merge rights are held by the maintainers.
- Fill in the PR template, especially the release-safety checklist.
