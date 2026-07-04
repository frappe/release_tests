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
Cypress.Commands.add("fillLink", (fieldname, value) => {
  const input = `[data-fieldname="${fieldname}"] input:visible`;
  cy.get(input).first().scrollIntoView().click();
  cy.wait(300); // let the control open before typing, else the first keystrokes get dropped
  cy.get(input).first().clear().type(value, { delay: 100 });
  // Match by text + force-click. Do NOT filter by :visible — Cypress mis-flags
  // awesomplete's absolutely-positioned <ul> as hidden, so :visible matches nothing.
  cy.get(".awesomplete li", { timeout: 20000 }).contains(value).click({ force: true });
});
