// Shared helpers for the version specs.

// Fast session login via the REST API (sets the sid cookie) — used to set up
// state for tests that aren't themselves testing the login page.
Cypress.Commands.add("apiLogin", (usr, pwd) => {
  cy.request({
    method: "POST",
    url: "/api/method/login",
    form: true,
    body: {
      usr: usr || Cypress.env("admin_user"),
      pwd: pwd || Cypress.env("admin_password"),
    },
  });
});

// Select a value in a Frappe Link input (works for form + grid inputs): type,
// wait for the matching suggestion to actually render, then click that exact
// suggestion. Three independent failure modes fed into this, in the order we
// found them (none of them about slow networks):
//
// 1. Frappe's Desk has a fixed top navbar and grids have sticky column headers, so
//    a plain scrollIntoView() (which aligns to the top of the scroll container)
//    tucks the field right behind that fixed chrome — the click then lands on the
//    navbar/header instead of the input. Scrolling to the viewport *center* keeps
//    the target clear of any fixed edge, and asserting visibility (not just
//    existence) makes Cypress retry until it's truly clickable instead of racing a
//    still-settling scroll/render.
//
// 2. We used to `cy.wait()` on an intercepted search_link request. That's racy:
//    any Link field's lookup on the page (not just the one we're driving) matches
//    the same alias, so the wait can consume an unrelated call and resolve before
//    our own query's results ever render — "no request ever occurred" even though
//    one did, just not the one we meant.
//
// 3. `ul[role="listbox"] [role="option"]` (and even a plain `<ul>`, and even
//    `.closest(".awesomplete")`'s own subtree) all assumed something about
//    where the suggestion actually lives in the DOM. Link fields configured to
//    also show a description (seen live on an Item field: code + "Release
//    Stock Item, All Item Groups" + a "Filtered by…" hint + "Create a new
//    Item"/"Advanced Search" links) render a richer, custom-built popup that —
//    confirmed by screenshots showing the exact text on screen while every one
//    of those scoped queries still found zero matches — isn't even nested
//    inside `.awesomplete`; that class gets reused for positioning only. Search
//    for the value at document scope instead of guessing at containment. This
//    is safe here specifically because these values are distinctive test
//    fixtures (item codes, customer names) that won't coincidentally appear
//    elsewhere on the page — unlike a generic word, which is a real risk (see
//    the CRM spec's Status-field comment for a case where it bit us).
//
// 4. Between a real (cypress-real-events) click on the matched suggestion and
//    keyboard selection (ArrowDown+Enter), only the click actually commits
//    anything: the grid cell re-renders as "code: title", proving the field's
//    raw value got set. Keyboard selection on this specific rich, site-
//    customized popup left the dropdown open with the raw typed text still in
//    the input — worse, not better. The click also does correctly trigger
//    Frappe's own item-selected fetch (rate + tax template), but not
//    synchronously — see waitForItemRate below, which is why selecting an item
//    needs an explicit wait for that fetch to land before saving.
Cypress.Commands.add("selectLink", (selector, value) => {
  cy.get(selector).first().scrollIntoView({ block: "center", inline: "center" }).should("be.visible").click();
  cy.wait(200); // let the control open before typing, else the first keystrokes get dropped
  cy.get(selector).first().should("be.visible").clear().type(value, { delay: 60 });
  cy.contains(value, { matchCase: false, timeout: 20000 }).scrollIntoView({ block: "center" }).should("be.visible").realClick();
});

// Convenience for a top-level form Link field, by fieldname.
Cypress.Commands.add("fillLink", (fieldname, value) => {
  cy.selectLink(`[data-fieldname="${fieldname}"] input:visible`, value);
});

// Fill a Link cell in an existing grid row, by 1-based row index.
//
// Frappe grids always render one empty row up front — row 1 exists before you've
// clicked anything. Its cells start as static, read-only display divs (`input`
// doesn't exist at all yet); clicking the cell is what swaps in the real, editable
// `<input>`. Specs used to click `.grid-add-row` first, which doesn't touch row 1
// at all — it *appends a new row* (row 2), so the value ended up one row below
// where every downstream assertion expected it. Click row 1's own cell instead.
//
// Selecting an Item here also triggers an async server fetch for its rate +
// tax template, which doesn't land synchronously with the click. We register
// the intercept *before* triggering that click (not inside waitForItemRate,
// which runs after — by then the request may already have fired, and the
// intercept would never see it) so waitForItemRate can wait on the real fetch
// completing.
//
// Waiting on the *rendered value* instead (an earlier version of this fix)
// looks appealing but is genuinely broken: before the fetch response arrives,
// the cell can sit at its pre-fetch "0.00" default across several consecutive
// polls just as validly as it would once truly settled post-fetch — a value-
// only check can't tell "hasn't started" from "finished" apart (a real review
// finding). Waiting on the actual request removes that ambiguity. This is
// more targeted than the search_link alias problem documented on selectLink
// above: this intercept is registered immediately before the one click that
// triggers it and consumed immediately after, rather than left open across a
// whole test where unrelated fields' calls could land first.
//
// The endpoint itself isn't stable across versions: v16 fires the generic
// frappe.client.validate_link_and_fetch, but the same interaction on v15
// never calls it at all ("No request ever occurred") — v15 uses the older,
// item-specific erpnext.stock.get_item_details.get_item_details instead.
// Match either under the one alias rather than hardcode a single version's.
Cypress.Commands.add("fillGridLink", (gridFieldname, rowIdx, cellFieldname, value) => {
  const cell = `[data-fieldname="${gridFieldname}"] .grid-body .grid-row[data-idx="${rowIdx}"] [data-fieldname="${cellFieldname}"]`;
  cy.intercept(
    "POST",
    "**/api/method/{frappe.client.validate_link_and_fetch,erpnext.stock.get_item_details.get_item_details}*"
  ).as("gridLinkFetch");
  cy.get(cell).scrollIntoView({ block: "center" }).should("be.visible").click();
  cy.selectLink(`${cell} input:visible`, value);
});

Cypress.Commands.add("waitForItemRate", () => {
  cy.wait("@gridLinkFetch", { timeout: 20000 });
});

// ---------------------------------------------------------------- personas
// Test users created by the API suites (release_tests/personas.py). Browser specs
// act as them through Frappe's own Impersonate, so no password ever reaches the
// browser: log in as the admin, impersonate, and the session is now that user's —
// same permissions, plus a red "You are impersonating" banner.
Cypress.env("personas", {
  sales: "rt.sales@example.com",
  sales_mgr: "rt.salesmgr@example.com",
  accounts: "rt.accounts@example.com",
  reader: "rt.reader@example.com",
  exporter: "rt.exporter@example.com",
});

Cypress.Commands.add("asAdmin", () => {
  cy.clearCookies();
  cy.apiLogin();
  cy.visit("/desk/todo");
});

// Fail with a clear reason when the API suites haven't created the persona yet.
Cypress.Commands.add("requirePersona", (key) => {
  const user = Cypress.env("personas")[key];
  cy.request({ url: `/api/resource/User/${encodeURIComponent(user)}`, failOnStatusCode: false })
    .its("status")
    .should((status) => {
      expect(
        status,
        `test user ${user} — run \`release-tests run --suite 'v16p_*'\` against this site first`
      ).to.eq(200);
    });
});

Cypress.Commands.add("impersonate", (key) => {
  const user = Cypress.env("personas")[key];
  cy.asAdmin();
  cy.requirePersona(key);
  cy.window()
    .its("frappe.csrf_token")
    .then((token) =>
      cy.request({
        method: "POST",
        url: "/api/method/frappe.core.doctype.user.user.impersonate",
        form: true,
        headers: { "X-Frappe-CSRF-Token": token },
        body: { user, reason: "Release test (Cypress)" },
      })
    );
  return cy.wrap(user);
});

// Open a list view's view-switcher menu (Espresso dropdown).
Cypress.Commands.add("openViewSwitcher", () => {
  cy.get(".custom-btn-group.view-switcher button", { timeout: 20000 }).first().click();
  return cy.get(".es-menu[data-state='open']");
});

Cypress.Commands.add("closeMenu", () => {
  cy.focused().trigger("keydown", { key: "Escape" });
});

// Skip a polished spec on a site that isn't running version-16-polished, the same
// way the API suites do: the per-module Sidebar DocType ships only in polished.
// Uses requests only — plain v16 has no /desk route to visit.
Cypress.Commands.add("skipUnlessPolished", (ctx) => {
  cy.clearCookies();
  cy.apiLogin();
  cy.request({ url: "/api/resource/DocType/Sidebar", failOnStatusCode: false }).then((resp) => {
    if (resp.status !== 200) {
      cy.log("Not a version-16-polished site (no Sidebar DocType): skipping");
      ctx.skip();
    }
  });
});

// ------------------------------------------------------- document lifecycle
// The steps every transaction goes through in the Desk, written once so a flow
// spec reads as the business process: save, submit, then Create → next document.

// Problems noticed mid-flow that a user would hit but can work around (e.g. a form
// that flips back to "Not Saved"). They are recorded and the flow carries on, so
// one problem doesn't leave the rest of the process untested; the spec then fails
// at the end with every finding listed (see assertNoFindings).
let findings = [];
let saveCount = 0;
Cypress.Commands.add("noteFinding", (text) => {
  findings.push(text);
  cy.log(`FINDING: ${text}`);
});
Cypress.Commands.add("assertNoFindings", () => {
  cy.then(() => {
    const found = findings;
    findings = [];
    expect(found, `issues a user would hit:\n- ${found.join("\n- ")}`).to.have.length(0);
  });
});

// Save the open form with its primary "Save" button, and wait until it has left
// the "New" state. Not Ctrl/Cmd+S: on a form that is already saved, that same
// shortcut means *submit*, so a repeated keystroke opens a stray submit prompt.
// If the form shows "Not Saved" again right after saving (scripts that run after
// the save changed a value), that is noted as a finding and the form saved again.
Cypress.Commands.add("saveForm", () => {
  const clickSave = () => {
    // A unique alias per save: reusing one lets the wait match an earlier save.
    const alias = `savedocs${++saveCount}`;
    cy.intercept("POST", "**/frappe.desk.form.save.savedocs").as(alias);
    // Wait for the form's own lookups to finish first (picking a supplier fetches
    // its details, including GST Category). Saving mid-lookup gets a refusal no
    // person would see, since nobody clicks Save within milliseconds of a pick.
    cy.get("body", { timeout: 30000 }).should("have.attr", "data-ajax-state", "complete");
    cy.get(".page-actions .primary-action:visible", { timeout: 20000 })
      .should("contain.text", "Save")
      .click();
    // If the server refuses the save, fail now with its own message (e.g. a
    // mandatory field) instead of waiting for a form state that never comes.
    cy.wait(`@${alias}`, { timeout: 60000 }).then(({ response }) => {
      if (response && response.statusCode !== 200) {
        const raw = JSON.stringify((response.body || {})._server_messages || response.body || "");
        const message = raw.replace(/\\"/g, '"').replace(/<[^>]+>/g, "").slice(0, 400);
        throw new Error(`Save refused (HTTP ${response.statusCode}): ${message}`);
      }
    });
  };
  clickSave();
  cy.window({ timeout: 30000 }).should((win) => {
    // is_new() is undefined, not false, once saved — compare as booleans.
    expect(Boolean(win.cur_frm && win.cur_frm.is_new()), "form saved").to.eq(false);
  });
  cy.wait(2000); // let the scripts that run after a save settle
  cy.window().then((win) => {
    if (!win.cur_frm.is_dirty()) return;
    cy.noteFinding(
      `${win.cur_frm.doctype} ${win.cur_frm.doc.name} showed "Not Saved" right after being saved; ` +
        "the user has to save it a second time before they can submit"
    );
    clickSave();
  });
  cy.window({ timeout: 30000 }).should((win) => {
    expect(Boolean(win.cur_frm.is_dirty()), "no unsaved changes").to.eq(false);
  });
  cy.get(".modal:visible").should("not.exist");
});

// Submit through the primary button + the "Permanently Submit?" confirmation,
// then wait for the dialog to close: anything under its overlay counts as hidden.
Cypress.Commands.add("submitForm", () => {
  cy.get(".page-actions .primary-action:visible", { timeout: 20000 })
    .should("contain.text", "Submit")
    .click();
  // Wait for the prompt to finish fading in before answering it. A dialog asked to
  // close mid-animation ignores the request, so a too-fast "Yes" submits the
  // document but leaves the prompt open over the page. No person clicks that fast.
  cy.get(".modal.show:visible", { timeout: 20000 }).should("have.css", "opacity", "1");
  cy.contains(".modal:visible .btn-primary", "Yes").click();
  // Generous: submitting posts stock and accounting entries, and a small dev
  // server can take well over 30s for an invoice.
  cy.window({ timeout: 120000 }).its("cur_frm.doc.docstatus").should("eq", 1);
  cy.get(".modal:visible", { timeout: 20000 }).should("not.exist");
});

// Create → <label>: open the next document from the form's Create menu and wait
// until the new (mapped) form of that DocType is showing.
Cypress.Commands.add("createFrom", (label, doctype = label) => {
  const group = '.inner-group-button[data-label="Create"]';
  cy.get(`${group} button:visible`, { timeout: 20000 }).first().click();
  cy.get(`${group} .dropdown-item[data-label="${encodeURIComponent(label)}"]:visible`)
    .first()
    .click();
  cy.window({ timeout: 30000 }).should((win) => {
    expect(win.cur_frm && win.cur_frm.doctype, `${doctype} form open`).to.eq(doctype);
    expect(Boolean(win.cur_frm.is_new()), `new ${doctype} mapped from the previous document`).to.eq(true);
  });
});

// The open form's document name, after save/submit — for later assertions.
Cypress.Commands.add("currentDocName", () => cy.window().its("cur_frm.doc.name"));
