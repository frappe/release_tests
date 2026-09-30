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

  // The UI workflow can be launched on its own, against any site. This spec only
  // means anything where the pack has been provisioned (by the `customisations`
  // API suite, which itself requires the site to opt in). Without this check the
  // spec fails on missing fields and DocTypes, which reads as a product
  // regression rather than "the prerequisite was never run here".
  before(function () {
    cy.apiLogin();
    cy.request({
      url: "/api/resource/Custom Field/Sales Invoice-rt_release_ref",
      failOnStatusCode: false,
    }).then((res) => {
      if (res.status !== 200) {
        cy.log("Customisation pack not present on this site — skipping.");
        this.skip();
      }
    });
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
    //
    // Whether a grid shows an empty row 1 up front is not universal: ERPNext's own
    // controllers add item rows to transaction grids (transaction.js), which is why
    // .grid-add-row on Sales Invoice appends a *second* row — but core grid.js has
    // no such path, so a plain custom DocType starts with none. Rather than bet on
    // either, add a row only when row 1 isn't already there, then fill row 1.
    const grid = '[data-fieldname="notes"]';
    const row1 = `${grid} .grid-body .grid-row[data-idx="1"]`;

    cy.get(grid, { timeout: 30000 }).should("exist");
    cy.get("body").then(($body) => {
      if ($body.find(row1).length === 0) {
        cy.get(`${grid} .grid-add-row`).click();
      }
    });

    // The cell renders as a static div until clicked into edit mode.
    const cell = `${row1} [data-fieldname="item_code"]`;
    cy.get(cell, { timeout: 20000 }).scrollIntoView({ block: "center" }).should("be.visible").click();
    cy.get(`${cell} input:visible`).type(Cypress.env("item"));

    cy.get("body").type("{ctrl}s");
    cy.get(".title-area .title-text", { timeout: 30000 })
      .invoke("text")
      .should("not.match", /New RT Release Note/i);

    cy.screenshot("v16-customisations-custom-doctype");
  });
});
