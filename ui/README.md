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

There is no local v15 site on this one-app-version bench, so the **v15 specs are
structure-only** until you point `CYPRESS_BASE_URL` at a real v15 site.

## Notes / roadmap
- The invoice spec reuses **existing** master data (customer + item) — set them via
  `CYPRESS_CUSTOMER` / `CYPRESS_ITEM`; they must already exist on the target site.
- Later: fold Cypress results into the Release Manager dashboard alongside the
  API suites, and add failure-attribution (standard-flow break vs new-release change).
