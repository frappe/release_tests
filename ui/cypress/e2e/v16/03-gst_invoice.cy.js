// v16 · India Compliance — create a GST Sales Invoice through the Desk UI.
// Selects the GST customer + a GST item (with an Item Tax Template); India
// Compliance applies the tax template from the company/customer GSTINs. The
// e-invoice IRN itself is validated by the API suite (needs the IC API); here we
// prove the GST invoice + tax computation build correctly from the UI.
//
// KNOWN DATA ISSUE, not a test bug: on the target site this currently fails at
// the final "a tax row was added" assertion, not because of anything in this
// spec or in selectLink. Checked directly against the site's REST API: the
// "Release GST Customer" fixture has gst_category "Unregistered" and no GSTIN
// at all. India Compliance's real tax-template auto-apply logic correctly
// declines to add GST for an unregistered customer — that's correct app
// behavior given the fixture's current data, not something any UI interaction
// can or should work around. Rate/amount DO populate correctly (see
// waitForItemRate below), proving item selection itself works; the fixture
// needs a valid GSTIN + a registered gst_category (e.g. "Registered Regular")
// for this assertion to ever pass. That's the API suite's fixture setup to
// fix, not this file.
describe("v16 · GST Sales Invoice", () => {
  beforeEach(() => {
    cy.apiLogin();
  });

  it("creates a GST invoice with a GST customer + GST item and computes tax", () => {
    cy.visit("/app/sales-invoice/new");

    cy.fillLink("customer", Cypress.env("gst_customer"));

    cy.fillGridLink("items", 1, "item_code", Cypress.env("gst_item"));
    cy.waitForItemRate("items", 1);

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
