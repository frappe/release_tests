// Programmatic Cypress runner used by Release Manager (release_manager.api.run_ui_test).
// Runs one version's spec folder and writes a structured results JSON that the
// Frappe side parses into Test Result records. Configured entirely via env vars.
//
//   SPEC_DIR      cypress/e2e/v16   (which version's specs to run)
//   RESULT_FILE   absolute path to write the results JSON to
//   HEADED        "1" (default) shows the browser; "0" runs headless
//   CY_BROWSER    electron (default) | chrome
//   CYPRESS_BASE_URL / CYPRESS_ADMIN_USER / CYPRESS_ADMIN_PASSWORD /
//   CYPRESS_CUSTOMER / CYPRESS_ITEM   forwarded to the specs as usual.
const cypress = require("cypress");
const fs = require("fs");

const specDir = process.env.SPEC_DIR || "cypress/e2e/v16";
const resultFile = process.env.RESULT_FILE || "cy-results.json";

function summarise(results) {
  // Flatten Cypress' run results into a compact, stable shape for the parser.
  const specs = (results.runs || []).map((run) => ({
    spec: run.spec && (run.spec.relative || run.spec.name),
    video: run.video || null,
    tests: (run.tests || []).map((t) => ({
      title: Array.isArray(t.title) ? t.title.join(" › ") : t.title,
      state: t.state, // passed | failed | pending | skipped
      duration: (t.attempts && t.attempts[0] && t.attempts[0].duration) || t.duration || 0,
      error: t.displayError || (t.attempts && t.attempts[0] && t.attempts[0].error && t.attempts[0].error.message) || null,
    })),
  }));
  return {
    totalPassed: results.totalPassed || 0,
    totalFailed: results.totalFailed || 0,
    totalPending: results.totalPending || 0,
    totalSkipped: results.totalSkipped || 0,
    browserName: results.browserName || null,
    specs,
  };
}

cypress
  .run({
    spec: `${specDir}/**/*.cy.js`,
    headed: process.env.HEADED !== "0",
    browser: process.env.CY_BROWSER || "electron",
    config: { video: true },
  })
  .then((results) => {
    const payload = results.status === "failed" ? { error: results.message } : summarise(results);
    fs.writeFileSync(resultFile, JSON.stringify(payload, null, 2));
    process.exit(0);
  })
  .catch((err) => {
    fs.writeFileSync(resultFile, JSON.stringify({ error: String(err && err.message ? err.message : err) }));
    process.exit(1);
  });
