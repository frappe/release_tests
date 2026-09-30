// v16-polished · DocType settings dialog: Roles / User Permissions tabs are for
// System Managers only (frappe#41005, frappe#41832).
function openSettings(doctype) {
  cy.window().then((win) => win.frappe.doctype_settings.open(doctype));
  return cy.get(".modal:visible", { timeout: 20000 });
}

describe("v16-polished · DocType settings dialog", () => {
  it("[admin] shows the permission tabs", () => {
    cy.asAdmin();
    openSettings("ToDo").should("contain", "Roles").and("contain", "User Permissions");
    cy.screenshot("v16p-settings-dialog-admin");
  });

  it("[sales_mgr] hides the permission tabs from a non-System Manager", () => {
    cy.impersonate("sales_mgr");
    cy.visit("/desk/customer");
    openSettings("Customer").should("not.contain", "User Permissions");
    cy.get(".modal:visible").find(".es-tabs__tab, [role='tab']").each(($tab) => {
      expect($tab.text().trim()).not.to.eq("Roles");
    });
  });
});
