// v16-polished · logged-out handling (frappe#37412) and Impersonate itself.
describe("v16-polished · logged out", () => {
  before(function () {
    cy.skipUnlessPolished(this);
  });

  it("[guest] a desk URL sends a logged-out visitor to login", () => {
    cy.clearCookies();
    cy.visit("/desk/todo", { failOnStatusCode: false });
    cy.location("pathname", { timeout: 20000 }).should("eq", "/login");
  });

  it("[sales] an open desk tab whose session ended asks the user to log in again", () => {
    cy.impersonate("sales");
    cy.visit("/desk/todo");
    cy.get(".frappe-list", { timeout: 20000 }).should("exist");
    // End the session behind the open tab, the way a logout elsewhere or an expiry does.
    cy.clearCookie("sid");
    cy.setCookie("user_id", "Guest");
    cy.window().then((win) => {
      win.frappe.call({ method: "frappe.client.get_list", args: { doctype: "ToDo" } });
    });
    cy.contains(".modal:visible", "Session Expired", { timeout: 20000 }).should("be.visible");
    cy.screenshot("v16p-session-expired");
  });
});

describe("v16-polished · impersonation [admin → sales]", () => {
  before(function () {
    cy.skipUnlessPolished(this);
  });

  it("acts as the user, shows the banner, and leaves an audit trail", () => {
    const user = Cypress.env("personas").sales;
    cy.impersonate("sales");
    cy.visit("/desk/todo");
    cy.window().its("frappe.session.user").should("eq", user);
    cy.get(".site-banners").should("contain", "You are impersonating");
    // Back to the admin: the Activity Log must record who impersonated whom.
    cy.asAdmin();
    cy.request(
      "/api/resource/Activity Log?fields=" +
        encodeURIComponent(JSON.stringify(["subject"])) +
        "&filters=" +
        encodeURIComponent(JSON.stringify([["operation", "=", "Impersonate"], ["user", "=", user]])) +
        "&order_by=creation%20desc&limit_page_length=1"
    )
      .its("body.data.0.subject")
      .should("contain", "impersonated as");
  });
});
