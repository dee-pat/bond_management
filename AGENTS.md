# Bond Management agent guidance

## External skill precedence

- The upstream `frappe-app-dev` skill provides generic Frappe guidance and is
  intentionally kept unmodified so it can be updated from its maintainer.
- Its canonical source is `netchampfaris/frappe-agent-skills`, under
  `skills/frappe-app-dev`.
- Apply that skill only where its instructions are consistent with this file.
- If the skill conflicts with this `AGENTS.md`, this `AGENTS.md` governs.
- In particular, the project requirements for Frappe v16, Query Builder reads,
  permissions, financial precision, migrations, testing, and application
  structure supersede generic examples in the skill.
- Do not copy a conflicting upstream example merely because it appears in the
  skill; adapt it to comply with this project's rules.

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
- Treat values populated by client scripts, including values derived from an
  attachment, as untrusted input. Recompute or validate them on the server
  before saving; the client may improve the form experience but must not be
  the authority for a business rule.
- JavaScript form flows that perform asynchronous work must return their
  Promise. Send intentional empty arguments explicitly when Frappe would omit
  `undefined`, and prevent an older response from overwriting newer form
  state when requests can overlap.

## Attachment rules

- Keep uploaded financial documents private. Read them through Frappe's File
  APIs and storage abstraction rather than assuming a filesystem path.
- Validate the actual file content and expected document structure; do not
  trust the extension, MIME type, filename, or client-extracted values alone.
- Never return, log, persist in plain text, or include configured PDF passwords
  in exceptions. Standardize attachment filenames only after the document has
  been identified, and preserve Frappe's private-file semantics.
- Parsers must reject missing or conflicting identity fields instead of
  guessing. A documented legacy fallback may be used only when the primary
  source is absent, and the primary source takes precedence when both exist.

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
- Enforce business uniqueness at both boundaries when concurrency is possible:
  use controller validation for a useful error and a database unique index as
  the final integrity guarantee. Install manual indexes with an idempotent
  patch, ensure they are also created on a fresh app installation, and test
  both paths.
- Permission patches should update or create only the `DocPerm` rows they own.
  Do not save a parent `DocType` merely to change permissions, because doing so
  can validate or rewrite unrelated metadata during migration.

## Test site conventions

- `test_site` is the canonical site for automated server and UI tests. Use
  `dev.local` for interactive development; never run destructive tests against
  `dev.local` or any other non-test site.
- Before testing, ensure `bond_management` is installed on `test_site`, migrate
  that site, and enable tests with
  `bench --site test_site set-config allow_tests true`.
- Reuse an existing local `test_site`. Do not recreate, drop, or restore it
  without explicit user approval.
- Do not record site credentials or machine-specific database configuration in
  repository files.

## Quality expectations

- Debug step by step and verify the actual failure; do not guess.
- Add or update tests for changed functions, utilities, reports, and DocType
  controllers.
- For business rules involving `>`, `>=`, `<`, or `<=`, test greater-than,
  less-than, and equality cases, and state the expected equality behavior.
- Add Cypress tests under `cypress/integration` for reports and other
  client-side interactions. Promise-returning JavaScript flows are required
  for testability.
- Test attachment parsers with current and supported legacy formats, malformed
  and non-PDF input, missing and conflicting identity values, and encrypted
  files with valid and invalid passwords.
- Test factories must generate collision-safe values. Tests and patches must
  tolerate reruns without depending on records left behind by an earlier run.
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
