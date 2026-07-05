// v16 · Frappe CRM — create a Lead through the CRM single-page app (/crm).
// NOTE: the CRM SPA is a separate frontend from the Desk; these selectors are a
// best-effort first draft (text/placeholder based) and may need tuning on the
// first real run — same approach we used to settle the Desk specs.
describe("v16 · CRM Lead", () => {
  beforeEach(() => {
    cy.apiLogin(); // sets the sid cookie; the CRM SPA reuses the Frappe session
  });

  it("creates a Lead in the Frappe CRM app", () => {
    cy.visit("/crm/leads");

    // Open the create-lead modal.
    cy.contains("button", /create|new lead|\+ *lead/i, { timeout: 30000 }).first().click();

    // Fill the lead's first name + email in the modal.
    cy.get('[role="dialog"], .modal', { timeout: 15000 }).should("be.visible");
    cy.get('[role="dialog"], .modal').within(() => {
      cy.get('input[placeholder*="First" i], input[placeholder*="Name" i]')
        .first()
        .clear()
        .type(Cypress.env("crm_lead_first"));
      cy.get('input[type="email"], input[placeholder*="mail" i]')
        .first()
        .clear()
        .type(Cypress.env("crm_lead_email"));
      cy.contains("button", /create|save/i).click();
    });

    // The new lead's email should now appear (list row or detail).
    cy.contains(Cypress.env("crm_lead_email"), { timeout: 30000 }).should("exist");
    cy.screenshot("v16-crm-lead");
  });
});
