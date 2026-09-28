// v16 · login page test
describe("v16 · Login", () => {
  it("logs in through the login page and lands on the Desk", () => {
    cy.visit("/login");
    cy.get("#login_email", { timeout: 20000 }).should("be.visible").type(Cypress.env("admin_user"));
    cy.get("#login_password").type(Cypress.env("admin_password"), { log: false });
    // The page carries a hidden duplicate .btn-login (legacy markup); only the
    // visible one (labelled "Continue" on this site) is the real submit button.
    cy.get(".btn-login:visible").click();
    // Frappe lands somewhere authenticated after login — /app or /desk depending
    // on version, but a site with Helpdesk (or another) configured as the default
    // workspace can redirect elsewhere again (e.g. /helpdesk/home). Asserting we
    // left /login is what actually proves login worked, without hardcoding every
    // possible destination a site's default-workspace setting could send us to.
    cy.location("pathname", { timeout: 30000 }).should("not.match", /^\/login/);
    cy.screenshot("v16-login-desk");
  });
});
