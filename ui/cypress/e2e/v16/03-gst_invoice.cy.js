// v16 · India Compliance — create a GST Sales Invoice through the Desk UI.
// Selects the GST customer + a GST item (with an Item Tax Template); India
// Compliance applies the tax template from the company/customer GSTINs. The
// e-invoice IRN itself is validated by the API suite (needs the IC API); here we
// prove the GST invoice + tax computation build correctly from the UI.
describe("v16 · GST Sales Invoice", () => {
  beforeEach(() => {
    cy.apiLogin();
  });

  it("creates a GST invoice with a GST customer + GST item and computes tax", () => {
    cy.visit("/app/sales-invoice/new");

    cy.fillLink("customer", Cypress.env("gst_customer"));

    cy.fillGridLink("items", 1, "item_code", Cypress.env("gst_item"));

    // Save (draft) — GST taxes compute on save from the item's tax template.
    cy.get("body").type("{ctrl}s");
    cy.get(".title-area .title-text", { timeout: 30000 })
      .invoke("text")
      .should("not.match", /New Sales Invoice/i);

    // A GST tax row should have been added (proves the template applied).
    cy.get('[data-fieldname="taxes"] .grid-body [data-fieldname="account_head"]', { timeout: 20000 })
      .should("exist");
    cy.screenshot("v16-gst-invoice");
  });
});
