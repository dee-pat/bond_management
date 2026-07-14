# Bond Management agent guidance

## Project baseline

- This is a custom Frappe Framework v16 app for bond portfolio management,
  including accruals and schedules. Do not assume ERPNext is installed unless
  the task explicitly says so.
- Use Python 3.14, Node 24, MariaDB 11.8 or 12.3, and Redis 6 or newer.
- Use Frappe v16-compatible bench commands and modern, non-deprecated Frappe
  APIs. Do not suggest or mix in v15-or-older patterns.
- Follow the standard Frappe app structure: DocTypes, `hooks.py`, and patches.

## Implementation rules

- Do not monkey-patch Frappe core. Use hooks or server scripts where an
  extension point is needed.
- Use four spaces for Python indentation; never use tabs.
- Do not use `frappe.db.get_list` or `frappe.db.get_all`; use
  `frappe.qb.get_query` instead. User-facing query-builder reads must use
  `ignore_permissions=False` unless a documented service boundary requires
  otherwise.
- Keep DocType controllers focused on that DocType. Move logic needed by more
  than one DocType into an appropriate module under `utils`.
- Put business calculations in Python, not JavaScript. Expose a Python method
  to the client only when needed, and remove `@frappe.whitelist()` when it is
  no longer used by a client integration.

## Financial and migration rules

- For monetary values, accrued interest, yields, and other precision-sensitive
  calculations, use `Decimal` constructed from strings, not binary floats.
  Quantize only at the business-rule boundary, with an explicit rounding mode
  and documented precision.
- Preserve the existing rounding convention when modifying a calculation;
  change it only with an explicit business rule and tests for the affected
  boundary cases.
- For changes that require transforming existing site data, add an idempotent
  patch under `bond_management/patches/`, register it in
  `bond_management/patches.txt`, and test both the migration and its resulting
  business data. Do not use a patch for schema changes that Frappe migrations
  already handle.

## Quality expectations

- Debug step by step and verify the actual failure; do not guess.
- Add or update tests for changed functions, utilities, reports, and DocType
  controllers.
- For business rules involving `>`, `>=`, `<`, or `<=`, test greater-than,
  less-than, and equality cases, and state the expected equality behavior.
- Add Cypress tests under `cypress/integration` for reports and other
  client-side interactions. Promise-returning JavaScript flows are required
  for testability.
- From the bench directory, run server tests with
  `bench --site test_site set-config allow_tests true` followed by
  `bench --site test_site run-tests --app bond_management`.
- Run UI tests with
  `bench --site test_site run-ui-tests bond_management --headless --browser "$(which chrome)"`.
- Run `pre-commit run --all-files` from the app directory before handoff when
  the environment permits.

## References

- Project-specific Codex context and troubleshooting: `.codex/context.md`
- Common local commands: `.codex/commands.md`
- Framework documentation: https://docs.frappe.io/framework/user/en/introduction
