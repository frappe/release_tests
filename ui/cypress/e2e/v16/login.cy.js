// v16 · login page smoke test
describe("v16 · Login", () => {
  it("logs in through the login page and lands on the Desk", () => {
    cy.visit("/login");
    cy.get("#login_email", { timeout: 20000 }).should("be.visible").type(Cypress.env("admin_user"));
    cy.get("#login_password").type(Cypress.env("admin_password"), { log: false });
    cy.get(".btn-login").click();
    cy.location("pathname", { timeout: 30000 }).should("include", "/app");
    cy.screenshot("v16-login-desk");
  });
});
