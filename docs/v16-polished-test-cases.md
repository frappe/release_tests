# version-16-polished: test cases

What the release suites check, as whom, and which change each check guards. The API
suites run with `release-tests run --suite 'v16p_*'` and the browser specs run with
`cd ui && npm run test:v16p`. Every suite skips on a site that isn't running polished.

**Reading the results.** A run is judged first by its **run rate**: the share of
checks that reached a verdict. After that comes the list of **issues found**. A failed
check that exposes a real problem means the suite did its job. A skip or a broken test
means that area went unchecked. Each failure names the check, the user and roles it ran
as, what was expected and what happened, the endpoint, and the upstream change.

## Test users (personas)

Each run creates or reuses these users and gives them a new random password. The API
suites log in as them for real. The browser specs reach them through Frappe's
Impersonate, starting from the admin login.

| Persona | User | Roles |
|---|---|---|
| sales | rt.sales@example.com | Sales User |
| sales_mgr | rt.salesmgr@example.com | Sales Manager |
| purchase | rt.purchase@example.com | Purchase User |
| stock | rt.stock@example.com | Stock User |
| item_mgr | rt.itemmgr@example.com | Item Manager, Stock Manager |
| accounts | rt.accounts@example.com | Accounts User |
| hr | rt.hr@example.com | HR User |
| hr_scoped | rt.hrscoped@example.com | HR User, limited to one employee by a User Permission |
| employee | rt.employee@example.com | Employee, linked to an Employee record |
| reader | rt.reader@example.com | RT Reader: read only on the probe DocType |
| exporter | rt.exporter@example.com | RT Exporter: read, report, export, print on the probe |
| owner_exporter | rt.ownerexporter@example.com | RT Owner Exporter: export only rows they own |
| website | rt.website@example.com | none (Website User) |
| guest | (not logged in) | none |

The permission checks for export, report view, kanban and print run against
**RT Perm Probe**, a custom DocType used only for testing, so no real DocType's
permissions change. It needs `allow_customisations = true` on the target.

## API: `v16p_security` (Frappe)

| # | Check | As | Expected | Guards |
|---|---|---|---|---|
| S1 | Export the probe DocType without Export permission | reader | refused (403) | frappe#42577 |
| S2 | Export with Export permission | exporter | CSV with the row | frappe#42577 |
| S3 | Owner-only export: own row, then another user's row | owner_exporter | own row allowed, other refused | frappe#42577 |
| S4 | Boot data the UI uses to show or hide Export and Report View | reader, exporter, owner_exporter | probe excluded or included as permitted | frappe#42577, #43044 |
| S5 | Link validation with a link filter, for values inside and outside it | sales | inside accepted, outside rejected | frappe#37608 |
| S6 | Save a document with a Link value outside its filter | exporter | *informational*: records whether saving enforces the filter | frappe#37608 |
| S7 | Workflow with a Submitted state on a non-submittable DocType | admin | rejected | frappe#37179 |
| S8 | Read or add role permissions | sales_mgr | refused | frappe#41005, #41832 |
| S9 | Change Print Settings | sales | refused | frappe@0b49110db2 |
| S10 | Move a Kanban card: read-only user vs writer; board accepts a JSON payload | reader, exporter | refused, then allowed | frappe@24a6500282 |
| S11 | PDF or bulk print of a document the user can't read; print view with access | sales, exporter | refused; renders | frappe@fd76f9ab72 |
| S12 | Bulk print over the configured limit | exporter | rejected with the limit message | print settings limits |
| S13 | Password reset for a disabled user (enabled user as control) | guest | no email queued | auth emails fix |
| S14 | Open a desk URL while logged out | guest | lands on login | frappe#37412 |
| S15 | Portal /addresses with HTML stored in an address | sales | page loads, HTML escaped | frappe#40180 |
| S16 | Own ToDo: create, set_value, save, attach | sales, purchase, accounts, hr | allowed | permission-hardening regressions |

## API: `v16p_hrms_security`

| # | Check | As | Expected | Guards |
|---|---|---|---|---|
| H1 | Bulk attendance with a list as the employee, or a string as the dates | hr | rejected with the new messages | hrms@5b71c3da71 |
| H2 | Bulk and half-day attendance for an employee outside the user's scope | hr_scoped | refused | hrms@00e9f9d674, @054dffef4d |
| H3 | Mark attendance for the employee in scope | hr_scoped | allowed, record exists | same |
| H4 | Quick Check In for self; check in or mark attendance for someone else | employee | self allowed, others refused | hrms#5089 |

## API: `v16p_frappe_features`

| # | Check | As | Expected |
|---|---|---|---|
| F1 | Per-module Sidebars exist; desk loads | sales | Sidebar records exist; desk returns 200 |
| F2 | Saved list layout gets a route signature; private to its owner | sales vs purchase | saved; hidden from and refused to others |
| F3 | Data import, Insert-or-Update (Print Heading) | admin | one row updated, one inserted |
| F4 | Chunked upload (3 chunks) attached to own ToDo | sales | whole file stored |
| F5 | Email Template scoped to a DocType | admin | saved with reference DocType |
| F6 | New fields `DocType.deprecated` and `Report.documentation_url` | admin | queryable |
| F7 | Typst PDF renderer | admin | returns a PDF |

## API: `v16p_erpnext`

| # | Check | As | Expected |
|---|---|---|---|
| E1 | The 32 new print formats (Bordered, Classic, Modern, Modern with Images × 8 DocTypes) | admin | installed and enabled |
| E2 | Default print formats | admin | point at existing, enabled formats |
| E3 | Each of the 32 formats renders a draft document | sales (Quotation, SO, DN), accounts (SI, PI, POS), purchase (PO, RFQ) | HTML for every format |
| E4 | Sales Invoice Modern with Images as a PDF | accounts | returns a PDF |
| E5 | Opening stock dialog on Item | stock vs item_mgr | refused, then a submitted Opening Stock reconciliation |
| E6 | Opening stock on new serial and batch items | item_mgr | stock booked |
| E7 | Party import: a customer with 2 contacts and an address from one file | admin (Data Import is System Manager-only) | all created and linked |
| E8 | Settings map for Sales Invoice | accounts vs reader | groups returned; refused without access |

## API: `v16p_hrms`

| # | Check | As | Expected |
|---|---|---|---|
| R1 | Job Offer without a Job Applicant; Job Offer without an email | hr | first saves, second rejected |
| R2 | Employee has Job Applicant and Job Offer fields | admin | both present |
| R3 | Close and reopen a Job Opening | hr | status follows |

## API: `v16p_upgrade_checks` (read-only)

| # | Check | Patch |
|---|---|---|
| U1 | Every Workspace has a module; standard ones are flagged; three icons renamed to Lucide | backfill_workspace_module, set_standard_flag, rename_lucide_workspace_icons |
| U2 | Sidebars converted, and old Workspace Sidebar records kept | convert_sidebars |
| U3 | Bulk print limits set | backfill_print_settings_bulk_export_limits |
| U4 | Every print format has `print_format_for`; custom builder formats use WeasyPrint or Typst | set_print_format_for_doctype, set_weasyprint_generator_for_beta_formats |
| U5 | No saved list layout is missing its route signature | backfill_list_layout_route_signature |
| U6 | The icon grid isn't empty. *Known issue*: reported as an issue labelled KNOWN ISSUE until fixed | keep_existing_sites_on_desktop_icons |
| U7 | Employees hired through an applicant have their Job Offer set | hrms set_job_offer_in_employee |

## Browser (Cypress): `ui/cypress/e2e/v16-polished`

| Spec | As | Checks |
|---|---|---|
| 01-navigation | sales | `/desk/<module>/<doctype>` URL, module sidebar, notification panel, navbar search, impersonation banner |
| 02-list-view | sales | view-switcher dropdown, saved-layout menu, sticky list header |
| 03-role-visibility | reader, exporter | no Report View for reader, and its URL falls back to the list; Export shown only with export permission |
| 04-settings-dialog | admin vs sales_mgr | Roles and User Permissions tabs only for System Manager |
| 05-print-and-attachments | accounts, sales | draft Sales Invoice in the new format; attachment preview pane |
| 06-session-and-impersonation | guest, sales, admin | logged-out redirect; "Session Expired" in an open tab; Impersonate banner and Activity Log entry |

## Not covered here

These are covered by Frappe's own polished Cypress suite (`frappe/cypress/integration`),
or are purely visual: Espresso component styling, grid column widths and bulk edit,
tree hover cards, Kanban virtual scrolling, address/contact card layout, calendar and
Gantt, dark mode and RTL styling, and the full data import wizard walkthrough.
