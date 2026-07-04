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

// Fill a Frappe Link field by fieldname and pick the matching awesomplete option.
// Click to focus/open the control, then type slowly so Frappe's debounced
// search_link fires, and pick from THIS field's own (visible) dropdown so we
// never match a stale/empty awesomplete list belonging to another field.
Cypress.Commands.add("fillLink", (fieldname, value) => {
  cy.get(`[data-fieldname="${fieldname}"] input:visible`).first().click().clear().type(value, { delay: 80 });
  // The open awesomplete list is the only one with visible <li>; match globally
  // (v16 can render it outside the field wrapper) and force-click past any scroll.
  cy.get(".awesomplete li:visible", { timeout: 20000 }).contains(value).click({ force: true });
});
