# release_tests

External HTTP release-test harness for Frappe sites. Given a running site, it logs
in over the REST API and exercises a defined set of flows per **installed app**,
adapting to whatever **version** is present (develop / v16 / v15), then reports
pass/fail per app and step.

It is a **standalone client** — *not* a Frappe app installed on the site. It only
speaks HTTP, so the same harness runs against a local bench site today and a
remote / press-deployed site tomorrow with no change.

## Deploying to Frappe Cloud

**Do not add this repo through "Add app from GitHub".** It is a Python library, not
a Frappe app: there is no `hooks.py` and nothing to install onto a site, so Frappe
Cloud rejects it with *"Not a valid Frappe App! Files hooks.py or patches.txt does
not exist"*. That error is correct — the repo is being used the wrong way.

It reaches a bench as an ordinary pip dependency of
[`release_manager`](https://github.com/frappe/release_manager), which declares it as

```toml
dependencies = [
    "release_tests @ git+https://github.com/frappe/release_tests.git@main",
]
```

So on Frappe Cloud you add **only `release_manager`**; this engine is pulled in with
it. Because that reference tracks `main`, whatever is on `main` at build time is what
gets deployed — push here before rebuilding the bench.

## Why

Frappe ships many app releases monthly, and regressions — including cross-app
breakage (e.g. CRM or India-compliance changes breaking ERPNext) — are often
catchable by simple release flows: log in, create master data, push one
transaction through. This tool automates exactly that across versions.

## Install

```bash
uv venv && uv pip install -e ".[dev]"   # dev extras add pytest/responses/ruff
```

## Configure targets

Copy the example and fill in credentials (the real file is gitignored):

```bash
cp targets.example.toml targets.toml
export RELEASE_ADMIN_PW='...'             # values like "$RELEASE_ADMIN_PW" resolve from env
```

Each `[[target]]` is one site: a URL plus either `login` (username/password) or
`token` (API key/secret) auth. The client sends an explicit `Host` header so
local multi-tenant bench sites route correctly.

## Use

```bash
release-tests list-suites                       # registered suites
release-tests detect  --target v16-local        # installed apps + versions
release-tests run     --target v16-local        # run all applicable suites
release-tests run     --target all --suite erpnext
```

`run` prints a per-target table, writes a JSON report to `results/`, and exits
non-zero if any step failed (CI-friendly). Suites whose app isn't installed are
**skipped** automatically.

## Suites

| Suite | App | Status |
|-------|-----|--------|
| `core_frappe` | frappe | login, whoami, ToDo CRUD round-trip |
| `erpnext` (+ `erpnext_*`) | erpnext | masters → submit Sales Invoice → Payment Entry → settled; selling/buying/stock/accounts/service/serialised/batched/manufacturing |
| `hrms` (+ `hrms_*`) | hrms | Employee, org, leave, expense flows |
| `crm` | crm | create Lead → Deal → Customer |
| `india_compliance` | india_compliance | GST masters → GST Sales Invoice → best-effort e-invoice |
| `insights` | insights (+erpnext) | Workbook → query on Sales Invoice → charts → dashboard |
| `helpdesk` | helpdesk | create Agent → open Ticket |
| `webshop` | webshop | publish Website Item → top-bar link → item page loads |
| `builder` | builder | author page (hero + cards) → publish → page loads |
| `learning`, `ksa_compliance` | respective | **stub** — gated reachability probe; fill in real flows |

> `helpdesk`, `webshop`, and `builder` are written against each app's schema but
> not yet validated end-to-end here (those apps weren't installable in the dev
> bench). Every suite auto-skips when its app is absent, so they're exercised on
> the first target that has the app.

### version-16-polished release suites

Six `v16p_*` suites cover the polished release's security fixes and features. They
run **as ordinary users with different roles** (see `release_tests/personas.py`),
because Administrator bypasses the permission checks that break. There is also a
Cypress folder, `ui/cypress/e2e/v16-polished`, whose specs act as those users
through Frappe's Impersonate. They skip on any site that isn't polished.

```bash
release-tests run --target v16p --suite 'v16p_*' --continue-on-fail
cd ui && CYPRESS_BASE_URL=https://your-site CYPRESS_ADMIN_PASSWORD=... npm run test:v16p
```

The target needs `allow_customisations = true` for the permission probe DocType,
and a background worker for the data-import checks. The full case list is in
[docs/v16-polished-test-cases.md](docs/v16-polished-test-cases.md).

**Reading a run.** The summary leads with the **run rate**: how many checks reached a
verdict. Then it lists **issues found**. Each failure is labelled *issue* (the product
misbehaved), *needs triage* (the server unexpectedly refused a step), or *harness* (the
test broke). It names the check, the user and roles, expected vs actual, the endpoint
and the upstream change. `results/release-<ts>-failures.md` lists issues first.

### Adding / extending a suite

Subclass `ReleaseSuite`, set `name` + `required_app`, and return ordered `Step`s
from `build_steps`. Steps share a `context` dict so later steps reuse earlier
records. Use the idempotent helpers in `release_tests/factories.py`. For
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
