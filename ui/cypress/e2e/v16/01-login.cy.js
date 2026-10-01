// v16 · login page test
describe("v16 · Login", () => {
  it("logs in through the login page and lands on the Desk", () => {
    cy.visit("/login");
    cy.get("#login_email", { timeout: 20000 }).should("be.visible").type(Cypress.env("admin_user"));
    cy.get("#login_password").type(Cypress.env("admin_password"), { log: false });
    // The submit control's markup isn't stable across sites. It used to carry
    // a .btn-login class (sometimes duplicated, with a hidden legacy copy —
    // see git history), which this site's newer login page doesn't have at
    // all. Nor is it necessarily a real <button> tag — `cy.contains("button",
    // ...)` still found nothing even though "Continue" is clearly visible on
    // screen, meaning this frontend renders it as some other element styled to
    // look like a button. Match the visible text directly, with no tag
    // constraint, covering the common wordings across sites/versions.
    cy.contains(/^(continue|log\s*in|sign\s*in)$/i).click();
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
