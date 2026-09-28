const { defineConfig } = require("cypress");

// Per-version target sites. Override any value via CYPRESS_* env vars, e.g.
//   CYPRESS_BASE_URL=http://v15site:8000 npm run test:v15
// v16 defaults to the local mysite; v15 has no local site yet (structure only).
module.exports = defineConfig({
  e2e: {
    baseUrl: process.env.CYPRESS_BASE_URL || "http://mysite.localhost:8000",
    specPattern: "cypress/e2e/**/*.cy.js",
    supportFile: "cypress/support/e2e.js",
    // Roomy viewport so grid rows / dropdowns stay on-screen (less scrolling).
    viewportWidth: 1440,
    viewportHeight: 900,
    video: false,
    screenshotOnRunFailure: true,
    defaultCommandTimeout: 15000,
    pageLoadTimeout: 60000,
    // Frappe's Desk has a fixed top navbar and grids have sticky column headers.
    // Cypress's default auto-scroll ("top") lines the target up right behind those
    // fixed elements, so the click/type lands on the wrong thing. "center" keeps
    // every auto-scrolled target clear of fixed chrome on all four specs.
    scrollBehavior: "center",
    // Targets are real remote sites (e.g. *.m.frappe.cloud), not localhost — a
    // search_link round trip can easily exceed Cypress's 5s default requestTimeout,
    // which fails cy.wait("@alias") with "no request ever occurred" even though the
    // request lands a moment later. Give it real network-round-trip headroom.
    requestTimeout: 20000,
  },
  env: {
    admin_user: process.env.CYPRESS_ADMIN_USER || "Administrator",
    admin_password: process.env.CYPRESS_ADMIN_PASSWORD || "SmokeTest@123",
    // Existing master data the invoice test reuses (must already exist on the site).
    customer: process.env.CYPRESS_CUSTOMER || "Release Test Customer",
    item: process.env.CYPRESS_ITEM || "RT-STOCK-ITEM",
    // India Compliance (GST) invoice test — masters created by the API suite.
    gst_customer: process.env.CYPRESS_GST_CUSTOMER || "Release GST Customer",
    gst_item: process.env.CYPRESS_GST_ITEM || "RT-GST-18",
    // Frappe CRM lead test.
    crm_lead_first: process.env.CYPRESS_CRM_LEAD_FIRST || "Release",
    crm_lead_email: process.env.CYPRESS_CRM_LEAD_EMAIL || "release.ui.lead@example.com",
  },
});
