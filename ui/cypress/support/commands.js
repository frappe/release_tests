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
  cy.get(`[data-fieldname="${fieldname}"] input:visible`).first().clear().type(value);
  cy.get(".awesomplete li", { timeout: 15000 }).contains(value).click();
});
