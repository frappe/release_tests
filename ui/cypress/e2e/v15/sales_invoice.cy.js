// v15 · create a Sales Invoice through the Desk UI using existing master data.
// NOTE: v15's form/grid DOM can differ from v16 — validate + adjust selectors
// against a real v15 site when one is available. Kept separate from v16 on purpose.
describe("v15 · Sales Invoice", () => {
  beforeEach(() => {
    cy.apiLogin();
  });

  it("creates + saves a Sales Invoice with an existing customer and item", () => {
    cy.visit("/app/sales-invoice/new");

    cy.fillLink("customer", Cypress.env("customer"));

    cy.get('[data-fieldname="items"] .grid-add-row', { timeout: 20000 }).click();
    cy.selectLink(
      '[data-fieldname="items"] .grid-body [data-fieldname="item_code"] input:visible',
      Cypress.env("item")
    );

    cy.get("body").type("{ctrl}s");
    cy.get(".title-area .title-text", { timeout: 30000 })
      .invoke("text")
      .should("not.match", /New Sales Invoice/i);
    cy.screenshot("v15-sales-invoice-created");
  });
});
