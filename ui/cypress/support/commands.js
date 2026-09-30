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
