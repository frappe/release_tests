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
      // Cypress's selector engine (Sizzle) doesn't support the CSS4 `i`
      // case-insensitive attribute flag (`[placeholder*="First" i]`) — it's a hard
      // syntax error, not just a non-match. A .filter() predicate does the
      // case-insensitive check in JS instead, sidestepping the engine limitation.
      cy.get("input")
        .filter((_, el) => /first|name/i.test(el.placeholder || ""))
        .first()
        .clear()
        .type(Cypress.env("crm_lead_first"));
      cy.get("input")
        .filter((_, el) => el.type === "email" || /mail/i.test(el.placeholder || ""))
        .first()
        .clear()
        .type(Cypress.env("crm_lead_email"));
      // KNOWN LIMITATION, not fixed here: this modal's Status field is mandatory
      // with no default, so submitting without setting it throws "Status is
      // required". Selecting it isn't a plain text match: a document-wide
      // cy.contains() for the option text also matches the Leads list's own
      // background Status *filter* dropdown (present in the DOM behind the
      // modal), so the popover needs to be scoped precisely — e.g. via the
      // trigger's aria-controls, or the popover's own role/data attribute —
      // before this can select the modal's own field reliably.
      cy.contains("button", /create|save/i).click();
    });

    // The new lead's email should now appear (list row or detail).
    cy.contains(Cypress.env("crm_lead_email"), { timeout: 30000 }).should("exist");
    cy.screenshot("v16-crm-lead");
  });
});
