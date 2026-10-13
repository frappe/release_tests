// @app erpnext
// v16 · ERPNext buying cycle through the Desk UI, the way a purchase user works it:
// Material Request → Purchase Order → Purchase Receipt → Purchase Invoice → Payment.
// Each next document is made from the previous one's "Create" menu, so the spec
// also proves the document-to-document mapping, not just data entry. Uses the
// supplier + stock item the API suites create (CYPRESS_SUPPLIER / CYPRESS_ITEM).
describe("v16 · Purchase cycle", () => {
  beforeEach(() => {
    cy.apiLogin();
  });

  it("runs Material Request → PO → Purchase Receipt → Purchase Invoice → Payment", () => {
    const docs = {};

    // 1. Material Request (type Purchase is the default).
    cy.visit("/app/material-request/new");
    cy.window({ timeout: 30000 }).its("cur_frm.doctype").should("eq", "Material Request");
    // "Required By" through the form's own setter: date pickers vary by user locale.
    cy.window().then((win) =>
      win.cur_frm.set_value("schedule_date", win.frappe.datetime.add_days(win.frappe.datetime.get_today(), 7))
    );
    cy.fillGridLink("items", 1, "item_code", Cypress.env("item"));
    cy.waitForItemRate();
    cy.window().then((win) => {
      const row = win.cur_frm.doc.items[0];
      win.frappe.model.set_value(row.doctype, row.name, "qty", 5);
    });
    cy.saveForm();
    cy.submitForm();
    cy.currentDocName().then((name) => (docs.material_request = name));
    cy.screenshot("v16-purchase-1-material-request");

    // 2. Purchase Order from the Material Request.
    cy.createFrom("Purchase Order");
    // The supplier comes over only if the item has a default supplier; else pick it.
    cy.window().then((win) => {
      if (!win.cur_frm.doc.supplier) cy.fillLink("supplier", Cypress.env("supplier"));
    });
    cy.saveForm();
    cy.submitForm();
    cy.currentDocName().then((name) => (docs.purchase_order = name));
    cy.screenshot("v16-purchase-2-purchase-order");

    // 3. Purchase Receipt from the Purchase Order (goods received).
    cy.createFrom("Purchase Receipt");
    cy.saveForm();
    cy.submitForm();
    cy.currentDocName().then((name) => (docs.purchase_receipt = name));
    cy.screenshot("v16-purchase-3-purchase-receipt");

    // 4. Purchase Invoice from the Purchase Receipt (supplier's bill).
    cy.createFrom("Purchase Invoice");
    cy.saveForm();
    cy.submitForm();
    cy.currentDocName().then((name) => (docs.purchase_invoice = name));
    cy.screenshot("v16-purchase-4-purchase-invoice");

    // 5. Payment against the invoice.
    cy.createFrom("Payment", "Payment Entry");
    // ERPNext usually fills "Paid From" from the company's default account; pick a
    // Mode of Payment only when it didn't. Not cy.fillLink: that helper searches the
    // whole page for the value, which its own notes say is safe only for distinctive
    // values — "Cash" also appears as hidden labels, so match a visible option exactly.
    cy.window().then((win) => {
      if (win.cur_frm.doc.paid_from) return;
      const mode = Cypress.env("mode_of_payment");
      const input = '[data-fieldname="mode_of_payment"] input:visible';
      cy.get(input).first().scrollIntoView({ block: "center" }).click();
      cy.get(input).first().clear().type(mode, { delay: 60 });
      cy.contains(":visible", new RegExp(`^\\s*${mode}\\s*$`), { timeout: 20000 })
        .last()
        .realClick();
    });
    cy.window({ timeout: 20000 }).its("cur_frm.doc.paid_from").should("be.ok");
    cy.saveForm();
    cy.submitForm();
    cy.screenshot("v16-purchase-5-payment");

    // The invoice is settled and every document in the chain is submitted.
    cy.then(() => {
      cy.request(`/api/resource/Purchase Invoice/${encodeURIComponent(docs.purchase_invoice)}`)
        .its("body.data")
        .should((pi) => {
          expect(pi.status, `${docs.purchase_invoice} status`).to.eq("Paid");
          expect(Number(pi.outstanding_amount), "outstanding").to.eq(0);
        });
      cy.request(`/api/resource/Material Request/${encodeURIComponent(docs.material_request)}`)
        .its("body.data.per_ordered")
        .should("eq", 100);
      cy.request(`/api/resource/Purchase Order/${encodeURIComponent(docs.purchase_order)}`)
        .its("body.data")
        .should((po) => {
          expect(po.per_received, "PO received %").to.eq(100);
          expect(po.per_billed, "PO billed %").to.eq(100);
        });
    });

    // Anything a user would have tripped over on the way, listed in one failure.
    cy.assertNoFindings();
  });
});
