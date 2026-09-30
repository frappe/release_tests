// v16-polished · new navigation, as an ordinary Sales User.
// Shell-prefixed URLs, module sidebars, the notification panel and navbar search
// are what every user meets first; a break here is a break for everyone.
describe("v16-polished · navigation [sales]", () => {
  before(function () {
    cy.skipUnlessPolished(this);
  });

  beforeEach(() => {
    cy.impersonate("sales");
  });

  it("opens a list through a shell-prefixed /desk/<module>/<doctype> URL", () => {
    cy.visit("/desk/selling/sales-order");
    cy.location("pathname", { timeout: 20000 }).should("match", /\/sales-order$/);
    cy.get(".page-head", { timeout: 20000 }).should("contain", "Sales Order");
    cy.window().its("frappe.router.current_shell").should("eq", "Selling");
    cy.screenshot("v16p-navigation-shell-url");
  });

  it("gives the Selling module its own sidebar", () => {
    cy.visit("/desk/selling/sales-order");
    cy.window()
      .its("frappe.boot.module_sidebars")
      .should((sidebars) => expect(Object.keys(sidebars)).to.include("Selling"));
    cy.get(".body-sidebar", { timeout: 20000 }).should("be.visible");
  });

  it("opens and closes the notification panel", () => {
    cy.visit("/desk/todo");
    cy.window().then((win) => win.frappe.ui.sidebar_panels.show("notifications"));
    cy.get(".sidebar-panel-notifications").should("not.have.class", "hidden");
    cy.get("body").type("{esc}");
    cy.get(".sidebar-panel-notifications").should("have.class", "hidden");
  });

  it("finds a DocType from the navbar search", () => {
    cy.visit("/desk/todo");
    cy.get("#navbar-search", { timeout: 20000 }).click().type("Sales Order", { delay: 40 });
    cy.get(".awesomplete ul li", { timeout: 20000 }).should("contain", "Sales Order");
    cy.get("#navbar-search").type("{esc}");
  });

  it("shows the impersonation banner, so testers know whose session this is", () => {
    cy.visit("/desk/todo");
    cy.get(".site-banners", { timeout: 20000 }).should("contain", "You are impersonating");
  });
});
