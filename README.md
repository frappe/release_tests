# frappe_smoke

External HTTP smoke-test harness for Frappe sites. Given a running site, it logs
in over the REST API and exercises a defined set of flows per **installed app**,
adapting to whatever **version** is present (develop / v16 / v15), then reports
pass/fail per app and step.

It is a **standalone client** — *not* a Frappe app installed on the site. It only
speaks HTTP, so the same harness runs against a local bench site today and a
remote / press-deployed site tomorrow with no change.

## Why

Frappe ships many app releases monthly, and regressions — including cross-app
breakage (e.g. CRM or India-compliance changes breaking ERPNext) — are often
catchable by simple smoke flows: log in, create master data, push one
transaction through. This tool automates exactly that across versions.

## Install

```bash
uv venv && uv pip install -e ".[dev]"   # dev extras add pytest/responses/ruff
```

## Configure targets

Copy the example and fill in credentials (the real file is gitignored):

```bash
cp targets.example.toml targets.toml
export SMOKE_ADMIN_PW='...'             # values like "$SMOKE_ADMIN_PW" resolve from env
```

Each `[[target]]` is one site: a URL plus either `login` (username/password) or
`token` (API key/secret) auth. The client sends an explicit `Host` header so
local multi-tenant bench sites route correctly.

## Use

```bash
frappe-smoke list-suites                       # registered suites
frappe-smoke detect  --target v16-local        # installed apps + versions
frappe-smoke run     --target v16-local        # run all applicable suites
frappe-smoke run     --target all --suite erpnext
```

`run` prints a per-target table, writes a JSON report to `results/`, and exits
non-zero if any step failed (CI-friendly). Suites whose app isn't installed are
**skipped** automatically.

## Suites

| Suite | App | Status |
|-------|-----|--------|
| `core_frappe` | frappe | login, whoami, ToDo CRUD round-trip |
| `erpnext` | erpnext | masters → submit Sales Invoice → Payment Entry → settled |
| `hrms` | hrms | create Employee, Leave Type fixtures present |
| `crm`, `helpdesk`, `learning`, `insights`, `builder`, `webshop`, `india_compliance`, `ksa_compliance` | respective | **stub** — gated reachability probe; fill in real flows |

### Adding / extending a suite

Subclass `SmokeSuite`, set `name` + `required_app`, and return ordered `Step`s
from `build_steps`. Steps share a `context` dict so later steps reuse earlier
records. Use the idempotent helpers in `frappe_smoke/factories.py`. For
version-specific behavior, branch with `gating.at_least(versions, app, "16")`.

## Testing the harness

```bash
uv run pytest          # fully mocked — no live site required
```

## Roadmap

- v2 ERPNext: full Quotation → Sales Order → Delivery Note → Sales Invoice →
  Payment → reconciliation chain.
- Press path: provision a site + install an app set, then feed its URL in as a
  runtime target — the runner already accepts arbitrary target URLs.
- Flesh out the stub suites as those apps become available to test against.
