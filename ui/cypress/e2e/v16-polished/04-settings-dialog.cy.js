// v16-polished · DocType settings dialog: Roles / User Permissions tabs are for
// System Managers only (frappe#41005, frappe#41832).
//
// Calling `frappe.doctype_settings.open(doctype)` directly (the original
// approach) throws "Cannot read properties of undefined (reading 'open')" —
// confirmed by inspecting the live page, `frappe.doctype_settings` genuinely
// doesn't exist as a global, on this site or in the standard Frappe v16
// codebase. It isn't missing, though: it's lazily loaded, only defined once
// the real "Settings" menu action has actually been triggered through the UI
// (presumably via a dynamic import behind that menu item's click handler).
// Drive it through the real UI flow instead of assuming the internal API is
// already loaded — confirmed working: the list view's "···" menu (an icon
// button with `aria-label="Menu"`, not literal "···" text — a plain text
// match finds nothing) has a "Settings" item that opens exactly this dialog.
// This also tests the actual discoverable path a user would take, which is
// arguably better coverage than calling a private API directly.
function openSettings() {
  cy.get(".list-row-container, .page-head, .list-view-container", { timeout: 20000 }).should("exist");
  cy.get('[aria-label="Menu"][data-icon-button="true"]', { timeout: 20000 }).first().should("be.visible").click({ force: true });
  cy.contains("[role='menuitem']", "Settings", { timeout: 10000 }).should("be.visible").click();
  return cy.get(".modal:visible", { timeout: 20000 });
}

describe("v16-polished · DocType settings dialog", () => {
  before(function () {
    cy.skipUnlessPolished(this);
  });

  it("[admin] shows the permission tabs", () => {
    cy.asAdmin();
    cy.visit("/desk/todo/view/list");
    openSettings().should("contain", "Roles").and("contain", "User Permissions");
    cy.screenshot("v16p-settings-dialog-admin");
  });

  it("[sales_mgr] hides the permission tabs from a non-System Manager", () => {
    cy.impersonate("sales_mgr");
    cy.visit("/desk/customer");
    openSettings().should("not.contain", "User Permissions");
    cy.get(".modal:visible").find(".es-tabs__tab, [role='tab']").each(($tab) => {
      expect($tab.text().trim()).not.to.eq("Roles");
    });
  });
});
