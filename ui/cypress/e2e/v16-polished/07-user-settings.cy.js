// v16-polished · the user settings dialog (frappe#40186), opened from the
// avatar dropdown (frappe#39520 converted the avatar into one). Distinct from
// the DocType settings dialog covered in 04-settings-dialog.cy.js — this one
// is the current user's own preferences, reached the same way across every
// page: click your name in the sidebar footer.
function openUserSettings() {
  cy.get(".page-head, .list-row-container", { timeout: 20000 }).should("exist");
  cy.contains(Cypress.env("admin_user"), { timeout: 10000 }).click({ force: true });
  cy.contains("[role='menuitem']", "Settings", { timeout: 10000 }).click();
  return cy.get(".settings-dialog-wrapper", { timeout: 20000 }).should("be.visible");
}

describe("v16-polished · user settings dialog [admin]", () => {
  before(function () {
    cy.skipUnlessPolished(this);
  });

  it("opens with the expected sections and the Profile tab active", () => {
    cy.asAdmin();
    cy.visit("/desk/todo");
    openUserSettings().should("contain", "Profile");
    cy.get(".settings-dialog-sidebar").then(($sidebar) => {
      const text = $sidebar.text();
      ["Profile", "Email", "Appearance", "Preferences", "Lists", "Forms", "Reports", "Session Defaults", "Keyboard Shortcuts"].forEach(
        (section) => expect(text, section).to.include(section)
      );
    });
    cy.get(".settings-dialog-tab-item.active .settings-dialog-tab-label").should("contain", "Profile");
    cy.screenshot("v16p-user-settings-dialog");
  });

  it("switches tabs without reopening the dialog", () => {
    cy.asAdmin();
    cy.visit("/desk/todo");
    openUserSettings();
    cy.contains(".settings-dialog-tab-label", "Appearance").click();
    cy.get(".settings-dialog-tab-item.active .settings-dialog-tab-label").should("contain", "Appearance");
  });
});
