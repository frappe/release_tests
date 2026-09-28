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
// 3. Selecting via ArrowDown+Enter on the focused input (the original approach,
//    chosen to avoid clicking the floating suggestion — presumably because an
//    earlier version of this file saw the same "floating dropdown hidden/covered"
//    problem as #1) turned out to not reliably commit either: debug screenshots
//    caught the dropdown still open with the raw typed text still in the input
//    after the keystrokes were sent. Now that we assert the exact suggestion is
//    on-screen *before* acting on it, clicking it directly is the unambiguous,
//    deterministic way to select it — no dependence on keyboard-driven awesomplete
//    state or focus timing. The click is a plain, unforced click: if fixed chrome
//    (or anything else) still covers the suggestion despite the centering above,
//    Cypress's own actionability check should fail loudly rather than click
//    through it silently.
Cypress.Commands.add("selectLink", (selector, value) => {
  cy.get(selector).first().scrollIntoView({ block: "center", inline: "center" }).should("be.visible").click();
  cy.wait(200); // let the control open before typing, else the first keystrokes get dropped
  cy.get(selector).first().should("be.visible").clear().type(value, { delay: 60 });
  cy.get(selector)
    .first()
    .closest(".awesomplete")
    .find('ul[role="listbox"] [role="option"]')
    .contains(value, { matchCase: false, timeout: 20000 })
    .scrollIntoView({ block: "center" })
    .should("be.visible")
    .click();
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
Cypress.Commands.add("fillGridLink", (gridFieldname, rowIdx, cellFieldname, value) => {
  const cell = `[data-fieldname="${gridFieldname}"] .grid-body .grid-row[data-idx="${rowIdx}"] [data-fieldname="${cellFieldname}"]`;
  cy.get(cell).scrollIntoView({ block: "center" }).should("be.visible").click();
  cy.selectLink(`${cell} input:visible`, value);
});
