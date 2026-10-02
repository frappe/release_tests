// v16 · login page test
describe("v16 · Login", () => {
  it("logs in through the login page and lands on the Desk", () => {
    cy.visit("/login");
    cy.get("#login_email", { timeout: 20000 }).should("be.visible").type(Cypress.env("admin_user"));
    cy.get("#login_password").type(Cypress.env("admin_password"), { log: false });
    // The submit button's markup isn't stable across sites (it used to carry a
    // .btn-login class, sometimes duplicated with a hidden legacy copy — see
    // git history — which a newer login page doesn't have at all), so match by
    // its visible text instead. That's trickier than it looks, confirmed by
    // inspecting this exact page's DOM directly:
    //   - The real button's text is "\n\t\tContinue" (framework-inserted
    //     whitespace) — cy.contains(/^continue$/i) anchored against that raw,
    //     untrimmed text finds nothing at all.
    //   - Dropping the anchors to work around that opens a worse hole: this
    //     page's own subtitle — "Welcome! Please sign in to continue." —
    //     contains "continue" too, and sits earlier in the DOM than the
    //     button. cy.contains() silently matched *that* paragraph instead
    //     (also previously true of a "Sign In" heading with a "sign in"
    //     alternative) — clicking it does nothing, which is exactly the
    //     symptom we saw: the form stayed fully filled in after "submitting",
    //     no error, no navigation.
    // A .filter() predicate that trims each candidate's own text before an
    // exact match avoids both problems at once, scoped to elements that are
    // actually clickable controls so a paragraph can't qualify regardless of
    // its text.
    cy.get("button, [role='button'], input[type='submit']")
      .filter((_, el) => /^(continue|log\s*in)$/i.test((el.textContent || "").trim()))
      .first()
      .click();
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
