// v16-polished · documentation links on DocTypes and Reports (frappe#43092).
// The list view's "···" menu now carries a "Documentation" entry (external
// link icon) alongside the existing Customize/Settings/List Settings items —
// checked for presence rather than clicked, since following it opens a new
// tab Cypress doesn't drive.
describe("v16-polished · documentation link [admin]", () => {
  before(function () {
    cy.skipUnlessPolished(this);
  });

  it("the list view's menu links out to the DocType's documentation", () => {
    cy.asAdmin();
    cy.visit("/desk/todo/view/list");
    cy.get(".page-head", { timeout: 20000 }).should("exist");
    cy.get('[aria-label="Menu"][data-icon-button="true"]', { timeout: 20000 }).first().should("be.visible").click({ force: true });
    cy.contains("[role='menuitem']", "Documentation", { timeout: 10000 })
      .should("be.visible")
      .find("use")
      .should("have.attr", "href", "#icon-external-link");
    cy.screenshot("v16p-documentation-link");
  });
});
