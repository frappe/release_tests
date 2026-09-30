// v16-polished · what the UI hides by role (frappe#43044, frappe#42577).
// Runs on the RT Perm Probe DocType the API suite creates (needs
// allow_customisations on the target), so no real DocType's permissions change.
const PROBE = "rt-perm-probe";

function probeExists() {
  return cy
    .request({ url: "/api/resource/DocType/RT Perm Probe", failOnStatusCode: false })
    .its("status");
}

function actionsMenu() {
  cy.get(".list-row-container", { timeout: 20000 }).should("exist");
  cy.get(".list-header-subject .list-subject .list-check-all").click();
  cy.contains("button", "Actions").click();
  return cy.get(".es-menu[data-state='open']");
}

describe("v16-polished · role-based visibility", () => {
  before(function () {
    cy.skipUnlessPolished(this);
  });

  beforeEach(function () {
    cy.asAdmin();
    probeExists().then((status) => {
      if (status !== 200) {
        cy.log("RT Perm Probe missing: enable allow_customisations and run the API suite first");
        this.skip();
      }
    });
  });

  it("[reader] has no Report View, and its URL falls back to the list", () => {
    cy.impersonate("reader");
    cy.visit(`/desk/${PROBE}/view/list`);
    cy.openViewSwitcher().should("contain", "List View").and("not.contain", "Report View");
    cy.closeMenu();
    cy.visit(`/desk/${PROBE}/view/report`);
    cy.window().its("cur_list.view_name").should("eq", "List");
    cy.location("pathname").should("not.contain", "/view/report");
  });

  it("[reader] gets no Export action without export permission", () => {
    cy.impersonate("reader");
    cy.visit(`/desk/${PROBE}/view/list`);
    actionsMenu().should("not.contain", "Export");
    cy.screenshot("v16p-reader-no-export");
    cy.closeMenu();
  });

  it("[exporter] gets the Export action with export permission", () => {
    cy.impersonate("exporter");
    cy.visit(`/desk/${PROBE}/view/list`);
    actionsMenu().should("contain", "Export");
    cy.closeMenu();
  });
});
