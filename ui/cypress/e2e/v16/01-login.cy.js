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
    // left /login is necessary but not sufficient: a failed login could just as
    // well redirect to some other public, unauthenticated page. Frappe sets the
    // `user_id` cookie to the logged-in user (and to "Guest" otherwise), so check
    // that too — that's what actually proves the session is authenticated.
    cy.location("pathname", { timeout: 30000 }).should("not.match", /^\/login/);
    cy.getCookie("user_id").its("value").should("not.eq", "Guest");
    cy.screenshot("v16-login-desk");
  });
});
