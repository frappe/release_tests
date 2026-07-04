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

// Select a value in a Frappe Link input (works for form + grid inputs).
// Keyboard selection: type -> wait for the search to return -> ArrowDown+Enter on
// the focused input. This keeps focus on the field so the awesomplete can't close
// from a page scroll, and never depends on finding/clicking the floating <li>.
Cypress.Commands.add("selectLink", (selector, value) => {
  cy.intercept("GET", "**/frappe.desk.search.search_link*").as("searchLink");
  cy.get(selector).first().scrollIntoView().click();
  cy.wait(200); // let the control open before typing, else the first keystrokes get dropped
  cy.get(selector).first().clear().type(value, { delay: 60 });
  cy.wait("@searchLink"); // the results are back
  cy.wait(400); // awesomplete renders them
  cy.focused().type("{downarrow}{enter}");
});

// Convenience for a top-level form Link field, by fieldname.
Cypress.Commands.add("fillLink", (fieldname, value) => {
  cy.selectLink(`[data-fieldname="${fieldname}"] input:visible`, value);
});
