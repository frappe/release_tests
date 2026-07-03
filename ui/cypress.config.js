const { defineConfig } = require("cypress");

// Per-version target sites. Override any value via CYPRESS_* env vars, e.g.
//   CYPRESS_BASE_URL=http://v15site:8000 npm run test:v15
// v16 defaults to the local mysite; v15 has no local site yet (structure only).
module.exports = defineConfig({
  e2e: {
    baseUrl: process.env.CYPRESS_BASE_URL || "http://mysite.localhost:8000",
    specPattern: "cypress/e2e/**/*.cy.js",
    supportFile: "cypress/support/e2e.js",
    video: false,
    screenshotOnRunFailure: true,
    defaultCommandTimeout: 15000,
    pageLoadTimeout: 60000,
  },
  env: {
    admin_user: process.env.CYPRESS_ADMIN_USER || "Administrator",
    admin_password: process.env.CYPRESS_ADMIN_PASSWORD || "SmokeTest@123",
    // Existing master data the invoice test reuses (must already exist on the site).
    customer: process.env.CYPRESS_CUSTOMER || "Smoke Test Customer",
    item: process.env.CYPRESS_ITEM || "SMOKE-ITEM",
  },
});
