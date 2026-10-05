// v16-polished · the dock preference feature (backport #43545, "pin the dock
// by default"): "Manage Dock" from the avatar menu opens an arrangement editor
// for the module dock, with a live preview of the resulting order.
describe("v16-polished · manage dock [admin]", () => {
  before(function () {
    cy.skipUnlessPolished(this);
  });

  it("opens from the avatar menu and lists the standard module entries", () => {
    cy.asAdmin();
    cy.visit("/desk/todo");
    cy.get(".page-head", { timeout: 20000 }).should("exist");
    cy.contains(Cypress.env("admin_user"), { timeout: 10000 }).click({ force: true });
    cy.contains("[role='menuitem']", "Manage Dock", { timeout: 10000 }).click();
    cy.get(".modal-title", { timeout: 20000 }).should("contain", "Manage Framework Dock");
    cy.get(".arrangement-editor").should("contain", "Build").and("contain", "Users").and("contain", "Website");
    cy.screenshot("v16p-manage-dock");
  });
});
