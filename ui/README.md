# UI (Cypress) tests

Browser-level release tests for Frappe/ERPNext, organised **by version** so the
UI differences between v15 and v16 stay isolated:

```
cypress/e2e/
  v16/   login.cy.js, sales_invoice.cy.js   # validated against a live v16 site
  v15/   login.cy.js, sales_invoice.cy.js   # same structure; validate on a real v15 site
```

Each version currently has two simple specs: **login** (login page → Desk) and
**Sales Invoice** (create + save an invoice reusing an existing customer + item).

## Run

```bash
cd ui && npm install                     # first time (downloads Cypress)

# v16 against the local mysite (defaults baked into cypress.config.js)
npm run test:v16

# any site / creds / master data via env vars:
CYPRESS_BASE_URL=https://site.example.com \
CYPRESS_ADMIN_USER=Administrator \
CYPRESS_ADMIN_PASSWORD=... \
CYPRESS_CUSTOMER="Some Customer" \
CYPRESS_ITEM="SOME-ITEM" \
npx cypress run --spec 'cypress/e2e/v16/**/*.cy.js'

npm run cy:open                          # interactive runner
```

Each spec drops a screenshot in `cypress/screenshots/` (e.g.
`v16-sales-invoice-created.png`, `v16-login-desk.png`) plus one automatically on
any failure — handy to attach to a pull request. Videos are recorded when run via
Release Manager (`run.js` sets `video: true`).

There is no local v15 site on this one-app-version bench, so the **v15 specs are
structure-only** until you point `CYPRESS_BASE_URL` at a real v15 site.

## Choosing which tests run (Release Manager)

Every spec declares its app on its **first line**:

```js
// @app erpnext
```

Release Manager reads that tag to fill the **App** and **Test suites** pickers on
its New Run page (UI mode). New specs appear there automatically, so tag every
new spec; an untagged one is listed under `frappe`. Suites whose app the site
doesn't have (per the site's last "Test Connection") start unticked.

A site on `v16-polished` lists the `v16-polished` specs plus the plain `v16`
ones, because polished keeps v16's flows. To run a selection outside Release
Manager, set `SPECS` (comma-separated paths) for `run.js`, or pass
`--spec <path>` to `cypress run`.

## Flow specs

`v16/06-purchase_cycle.cy.js` works a buying cycle the way a purchase user does:
Material Request → Purchase Order → Purchase Receipt → Purchase Invoice →
Payment. Each next document comes from the previous one's **Create** menu, and
the spec ends by checking that the invoice is Paid and the Material Request and
Purchase Order are fully ordered, received and billed. It uses the supplier and
stock item that the API suites create (`CYPRESS_SUPPLIER`, `CYPRESS_ITEM`).

The shared steps live in `cypress/support/commands.js`:

- `saveForm`: clicks Save, not Ctrl+S, which means *submit* on a saved form.
- `submitForm`: clicks Submit and confirms the prompt.
- `createFrom`: opens the next document from the Create menu.

Two waits are deliberate. Both stop the test acting faster than a person can,
which otherwise causes failures no user would see:

- before saving, it waits for the page's lookups to finish (`data-ajax-state`);
- before confirming, it waits for the prompt to finish opening.

A problem a user *would* hit but can work around, such as a form showing
"Not Saved" straight after a save, is recorded as a finding. The flow then
carries on, and the spec fails at the end listing every finding, so the rest
of the process is still tested.

## macOS: bench must run in a GUI Terminal
Cypress is an Electron app. On **macOS** it can only launch inside a GUI (Aqua)
session — even in headless mode there is no `xvfb`. So when you trigger UI tests
from Release Manager, the bench (and its RQ worker) **must be started from
`bench start` in Terminal.app**, not a headless/SSH context. Headed shows the
browser window; headless just skips the window (still needs the session) and
records a video. A launch from a non-GUI context fails with
`Could not find Cypress test run results` — Release Manager surfaces this with a
hint in the run's Output/log.

## CI / unattended (Linux, no desktop)
`.github/workflows/ui-tests.yml` runs the specs on `ubuntu-latest` via the
official `cypress-io/github-action` (virtual display handled for you) — the only
truly display-less path, for staging / Frappe Cloud sites. Configure repo
**Variables** `BASE_URL`, `ADMIN_USER`, `CUSTOMER`, `ITEM` and the **Secret**
`ADMIN_PASSWORD`, then run the workflow (choose `v16`/`v15`). Screenshots + videos
are uploaded as artifacts.

## Notes / roadmap
- The invoice spec reuses **existing** master data (customer + item) — set them via
  `CYPRESS_CUSTOMER` / `CYPRESS_ITEM`; they must already exist on the target site.
- Later: fold Cypress results into the Release Manager dashboard alongside the
  API suites, and add failure-attribution (standard-flow break vs new-release change).
