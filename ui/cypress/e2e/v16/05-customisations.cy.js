// v16 · the customisation layer, as a real browser sees it.
//
// The HTTP engine can prove the Client Script *record* survived an upgrade, but
// not that it still runs — only a browser executes form scripts. This spec covers
// the gap: the custom field renders, the property setter's relabel is visible, and
// the client script's button and indicator actually appear and work.
//
// Requires the customisation pack on the target (release_tests.customisations),
// which the `customisations` API suite provisions.
describe("v16 · customisation layer", () => {
  beforeEach(() => {
    cy.apiLogin();
  });

  it("renders the custom field and the property setter's relabelled field", () => {
    cy.visit("/app/sales-invoice/new");

    // Custom Field from the pack.
    cy.get('[data-fieldname="rt_release_ref"]', { timeout: 30000 }).should("exist");

    // Property Setter: po_no is relabelled "RT PO Ref".
    cy.get('[data-fieldname="po_no"]')
      .find(".control-label")
      .first()
      .invoke("text")
      .should("match", /RT PO Ref/i);

    cy.screenshot("v16-customisations-fields");
  });

  it("runs the client script: custom button sets the field and shows the indicator", () => {
    cy.visit("/app/sales-invoice/new");
    cy.fillLink("customer", Cypress.env("customer"));

    // The client script sets a blue "RT customised" indicator on refresh.
    cy.get(".title-area .indicator-pill, .title-area .indicator", { timeout: 30000 })
      .invoke("text")
      .should("match", /RT customised/i);

    // Its custom button writes the custom field.
    cy.contains(".btn, .dropdown-item", "RT Release Check", { timeout: 20000 }).click();

    // Assert against the form's model, not a visible input. Whether the field is
    // on screen depends on which tab and section it was anchored into, and that is
    // a property of the fixture, not of the client script under test. Reading
    // cur_frm.doc proves the script ran regardless of where the field was placed.
    cy.window()
      .its("cur_frm.doc.rt_release_ref", { timeout: 20000 })
      .should("match", /^RT-CLIENT-/);

    cy.screenshot("v16-customisations-client-script");
  });

  it("opens the custom DocType and accepts a child row", () => {
    cy.visit("/app/rt-release-note/new");

    cy.get('[data-fieldname="title"] input:visible', { timeout: 30000 }).type(
      "Cypress customisation check"
    );

    // Child table on a wholly custom DocType.
    cy.get('[data-fieldname="notes"] .grid-add-row', { timeout: 20000 }).click();
    cy.get('[data-fieldname="notes"] .grid-body [data-fieldname="item_code"] input:visible')
      .first()
      .type(Cypress.env("item"));

    cy.get("body").type("{ctrl}s");
    cy.get(".title-area .title-text", { timeout: 30000 })
      .invoke("text")
      .should("not.match", /New RT Release Note/i);

    cy.screenshot("v16-customisations-custom-doctype");
  });
});
