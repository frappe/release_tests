// v16 · create a Sales Invoice through the Desk UI using existing master data
describe("v16 · Sales Invoice", () => {
  beforeEach(() => {
    cy.apiLogin();
  });

  it("creates + saves a Sales Invoice with an existing customer and item", () => {
    cy.visit("/app/sales-invoice/new");

    // Customer (existing).
    cy.fillLink("customer", Cypress.env("customer"));

    // Fill the item into row 1, which the grid already renders empty by default —
    // clicking `.grid-add-row` here would append an unwanted row 2 instead.
    cy.fillGridLink("items", 1, "item_code", Cypress.env("item"));

    // Save (Ctrl/Cmd+S) and confirm it left the "New" state (got a name).
    cy.get("body").type("{ctrl}s");
    cy.get(".title-area .title-text", { timeout: 30000 })
      .invoke("text")
      .should("match", /ACC-SINV|SINV|Sales Invoice/i)
      .and("not.match", /New Sales Invoice/i);
    cy.screenshot("v16-sales-invoice-created");
  });
});
