// v16-polished · list view: the single view-switcher and saved layouts, as a Sales User.
describe("v16-polished · list view [sales]", () => {
  before(function () {
    cy.skipUnlessPolished(this);
  });

  beforeEach(() => {
    cy.impersonate("sales");
    cy.visit("/desk/todo");
    cy.get(".frappe-list", { timeout: 20000 }).should("exist");
  });

  it("switches views from one dropdown", () => {
    cy.openViewSwitcher().should("contain", "List View").and("contain", "Kanban");
    cy.closeMenu();
  });

  it("offers saved layouts from the List View entry", () => {
    cy.openViewSwitcher();
    cy.contains(".es-menu__item", "List View").trigger("pointerenter");
    cy.contains(".es-menu__item", "Create Layout", { timeout: 20000 }).should("be.visible");
    cy.screenshot("v16p-list-saved-layouts");
    cy.closeMenu();
  });

  it("keeps the header in view while the list scrolls", () => {
    cy.get(".list-row-head, .list-header-subject", { timeout: 20000 })
      .first()
      .should("have.css", "position")
      .and("match", /sticky|fixed/);
  });
});
