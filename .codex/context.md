This project uses Frappe Framework v16.

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

Frappe Python API
- avoid frappe.db.get_list and frappe.db.get_all 
- use frappe.qb.get_query instead 

