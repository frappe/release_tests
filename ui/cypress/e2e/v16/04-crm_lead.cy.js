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
    });

    // The Status field is mandatory with no default in this quick-entry modal —
    // submitting without it throws "Status is required". A document-wide text
    // match for "New" isn't safe: the Leads list has its own background Status
    // *filter* dropdown in the same DOM (confirmed by watching it end up set to
    // "New" while the modal's own field stayed empty), so scope via the
    // trigger's aria-controls instead of guessing at the popover library's own
    // markup.
    //
    // Neither a synthetic Cypress .click() nor keyboard Enter on the focused,
    // correctly-scoped option actually committed the selection (confirmed via a
    // debug capture: focus does land on the right [role="option"], but <body>
    // stayed stuck at pointer-events:none afterwards, and forcing past that
    // still hit "Status is required" — the value genuinely never changed).
    // This custom dropdown reacts only to trusted, OS-level input, not
    // Cypress's default synthetic events — cypress-real-events dispatches those
    // via the browser's real input pipeline (CDP), which is what actually
    // triggers this component's selection and its own outside-click-to-close
    // handling correctly.
    let statusPopoverId = null;
    cy.get('[role="dialog"], .modal')
      .contains(/^status$/i)
      .realClick()
      .then(($el) => {
        statusPopoverId = $el.attr("aria-controls") || $el.closest("[aria-controls]").attr("aria-controls");
      });
    cy.then(() => {
      (statusPopoverId ? cy.get(`#${statusPopoverId}`) : cy.get('[data-state="open"]').last())
        .contains(/^new$/i, { timeout: 10000 })
        .should("be.visible")
        .realClick();
    });
    cy.get('[role="dialog"], .modal').within(() => {
      cy.contains("button", /create|save/i).realClick();
    });

    // The new lead's email should now appear (list row or detail).
    cy.contains(Cypress.env("crm_lead_email"), { timeout: 30000 }).should("exist");
    cy.screenshot("v16-crm-lead");
  });
});
