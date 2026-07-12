This project uses Frappe Framework v16.

Documentation
- https://docs.frappe.io/framework/user/en/introduction

Environment:
- Python 3.14
- Node 24
- MariaDB 12.3 (or 11.8)
- Redis 6+

Rules:
- Always use bench commands compatible with version-16
- Do NOT suggest v15 or older commands
- Use modern Frappe patterns (no deprecated APIs)
- No monkey patching, use server scripts and hooks instead 
- Follow Frappe app structure (doctype, hooks.py, patches)

Project:
- Custom Frappe apps only (no ERPNext unless specified)
- Focus on financial logic (bonds, accruals, schedules)

Common issues to debug:
- MySQLdb connection errors (check MariaDB service + credentials)
- Redis connection failures
- "DocType not found" (check app installed + migrations)
- JS not updating fields (check triggers + frm.refresh_field)
- Bench build issues (node/yarn mismatch)

Always debug step-by-step, not guess.

Never:
- suggest monkey patching core Frappe
- downgrade dependencies
- mix v15 (or older versions) and v16 APIs

Check
- monkey patching core Frappe; should be removed


Frappe Python API
- avoid frappe.db.get_list and frappe.db.get_all 
- use frappe.qb.get_query instead of the 2 above
- use ignore_permissions=False for user-facing frappe.qb.get_query reads unless a documented service boundary requires otherwise

Test Code:
- suggest/update test codes for all functions, including utilities, reports, and DocType controllers
- for >, >=, <, <=; write one test for each of >, <, and =
- define the expected equality outcome from the specific business rule being tested
- add Cypress browser tests in cypress/integration for report and other client-side interactions; promise-returning JS flows are required for testability

Javascript (JS):
- Do not suggest JS calculations. call the python whitelisted function instead
- regularly check if a whitelisted function does not need to be whitelisted (not used by JS etc). remove the whitelist

Function Imports
- Doctypes files should not call other Doctype fuctions. if these fuctions are required by other Doctypes, move them to a file in utils. Therfore doctype functions inside the Doctype file are the ones needed by only the Doctype itself 
