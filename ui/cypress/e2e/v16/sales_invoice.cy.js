// v16 · create a Sales Invoice through the Desk UI using existing master data
describe("v16 · Sales Invoice", () => {
  beforeEach(() => {
    cy.apiLogin();
  });

  it("creates + saves a Sales Invoice with an existing customer and item", () => {
    cy.visit("/app/sales-invoice/new");

    // Customer (existing).
    cy.fillLink("customer", Cypress.env("customer"));

    // Add an item row and pick an existing item.
    cy.get('[data-fieldname="items"] .grid-add-row', { timeout: 20000 }).click();
    cy.get('[data-fieldname="items"] .grid-body [data-fieldname="item_code"] input:visible')
      .first()
      .click()
      .type(Cypress.env("item"), { delay: 80 });
    cy.get(".awesomplete li:visible", { timeout: 20000 })
      .contains(Cypress.env("item"))
      .click({ force: true });

    // Save (Ctrl/Cmd+S) and confirm it left the "New" state (got a name).
    cy.get("body").type("{ctrl}s");
    cy.get(".title-area .title-text", { timeout: 30000 })
      .invoke("text")
      .should("match", /ACC-SINV|SINV|Sales Invoice/i)
      .and("not.match", /New Sales Invoice/i);
    cy.screenshot("v16-sales-invoice-created");
  });
});
