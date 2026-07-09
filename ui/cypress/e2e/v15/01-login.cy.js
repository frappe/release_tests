// v15 · login page test.
// Structure mirrors v16; selectors are the same for the login page across v15/v16,
// but keep this file separate so version-specific tweaks stay isolated.
describe("v15 · Login", () => {
  it("logs in through the login page and lands on the Desk", () => {
    cy.visit("/login");
    cy.get("#login_email", { timeout: 20000 }).should("be.visible").type(Cypress.env("admin_user"));
    cy.get("#login_password").type(Cypress.env("admin_password"), { log: false });
    cy.get(".btn-login").click();
    // Frappe lands on the Desk after login — /app or /desk depending on version.
    cy.location("pathname", { timeout: 30000 }).should("match", /\/(app|desk)/);
    cy.screenshot("v15-login-desk");
  });
});
