// v16-polished · the redesigned Text Editor field (frappe#41505). Confirmed
// live: it's Quill-based (.ql-toolbar / .ql-editor), with a much richer
// toolbar than the old field — paragraph style, font size, bold/italic/
// underline/strike, highlight, blockquote, code, link, image, lists,
// alignment, indent, and a table picker.
describe("v16-polished · redesigned Text Editor field [admin]", () => {
  before(function () {
    cy.skipUnlessPolished(this);
  });

  it("renders the new toolbar and accepts typed text", () => {
    cy.asAdmin();
    cy.visit("/desk/todo/new");
    const field = '[data-fieldname="description"][data-fieldtype="Text Editor"]';
    cy.get(field, { timeout: 20000 }).should("be.visible");
    cy.get(`${field} .ql-toolbar`).should("be.visible");
    // Quill renders more than one .ql-editor-classed node (its hidden clipboard
    // handler among them) — scope to the first, the actual visible editable area.
    cy.get(`${field} .ql-editor`).first().click().type("Release test note");
    cy.get(`${field} .ql-editor`).first().should("contain", "Release test note");
    cy.screenshot("v16p-text-editor-field");
  });
});
