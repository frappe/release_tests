// v16-polished · the new print formats and the attachment preview pane.
describe("v16-polished · print [accounts]", () => {
  it("opens a draft Sales Invoice in 'Sales Invoice Modern with Images'", () => {
    cy.impersonate("accounts");
    cy.request(
      "/api/resource/Sales Invoice?filters=" +
        encodeURIComponent(JSON.stringify([["docstatus", "=", 0]])) +
        "&limit_page_length=1"
    )
      .its("body.data")
      .then((rows) => {
        expect(rows, "a draft Sales Invoice (the v16p_erpnext API suite creates one)").to.have
          .length(1);
        const name = rows[0].name;
        const format = "Sales Invoice Modern with Images";
        cy.visit(`/desk/print/Sales Invoice/${encodeURIComponent(name)}?format=${encodeURIComponent(format)}`);
        cy.get(".print-preview-wrapper", { timeout: 30000 }).should("be.visible");
        cy.window().its("cur_page.page.print_view.print_format_selector").invoke("val").should("eq", format);
        cy.get("iframe.print-format-container", { timeout: 30000 })
          .its("0.contentDocument.body")
          .should("contain", name);
        cy.screenshot("v16p-print-modern-with-images");
      });
  });
});

describe("v16-polished · attachments [sales]", () => {
  it("previews an attachment in the form sidebar", () => {
    cy.impersonate("sales");
    cy.visit("/desk/todo");
    cy.window()
      .then((win) =>
        win.frappe.xcall("frappe.client.insert", {
          doc: {
            doctype: "ToDo",
            description: "RT-V16P attachment preview",
            allocated_to: Cypress.env("personas").sales,
          },
        })
      )
      .then((todo) => {
        cy.window().then((win) =>
          win.frappe.xcall("frappe.client.insert", {
            doc: {
              doctype: "File",
              file_name: "rt-preview.txt",
              content: "release test preview",
              attached_to_doctype: "ToDo",
              attached_to_name: todo.name,
              is_private: 1,
            },
          })
        );
        cy.visit(`/desk/todo/${todo.name}`);
        cy.contains(".attachment-row .attachment-file-label", "rt-preview", { timeout: 20000 }).click();
        cy.get(".attachment-preview", { timeout: 20000 }).should("not.have.class", "hidden");
        cy.screenshot("v16p-attachment-preview");
      });
  });
});
