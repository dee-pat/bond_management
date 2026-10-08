# Exchange-rate statement privacy

Generic Frappe document and list APIs currently expose the canonical exchange
rate's representative statement name to investors even when they cannot read
that statement. Shared rates must remain readable without exposing another
portfolio's provenance.

Move `Bond Exchange Rate.statement` to permission level 1. Only Bond Management
Manager and System Manager receive the app-owned level-1 read permission;
the existing idempotent install and migration bootstrap maintains those rows.
The investor detail API first authorizes the exchange-rate row through a
permission-scoped query, then reads its private representative name and returns
it only when the caller can read the linked statement. Its response shape and
readable-statement navigation remain compatible. Generic APIs omit provenance
for all investors, including investors who can read the source statement.

No financial values, provenance ownership, or stored links change. Desk keeps
the manager's representative statement field visible and read-only. The
permission bootstrap updates only its owned role/permission-level rows.

## Acceptance and verification

- Real `frappe.client.get`, `frappe.client.get_list`, and `frappe.api.v1.read_doc`
  regressions omit investor provenance and retain manager provenance.
- Investor detail retains readable references and masks unreadable ones.
- Bootstrap repairs missing or changed owned level-1 rows, reruns safely, and
  preserves unrelated permission rows. Existing fresh-install/migrate hooks
  continue to invoke it.
- A representative Desk smoke assertion checks the protected read-only field
  metadata; Frappe hides empty read-only values on a new form.
- Run targeted tests and complete affected API/permission modules, then
  `apps/bond_management/scripts/verify.sh pre-push-ui` from the bench. Validate
  the bootstrap on an approved fresh site.

## Verification evidence

- Risk classification: field-level provenance privacy and permission bootstrap.
- Required gates: complete API and permission modules, full server/frontend/UI
  gate, fresh install and migration bootstrap.
- Commands executed: `bench --site test_site migrate`; `bench --site test_site
  run-tests --app bond_management --module
  bond_management.bond_management.api.test_investor_exchange_rates`; the
  corresponding `utils.test_investor_permissions` command;
  `scripts/verify.sh pre-push-ui`; final `scripts/verify.sh lint`.
- Exit statuses: completed module and UI gate commands exited 0; final lint is
  run after this evidence update before committing.
- Tests passed: 12 API and 17 permission tests; 325 complete server tests and
  49 authenticated browser tests. Generic document APIs return a null protected
  value; list APIs omit it; the custom API retains readable statement links.
- Fresh commands: independent new-site/install-app; index and permission
  assertions before the first migrate; requeue all 25 registered app patches;
  actual migrate; repeat assertions; ordinary migrate rerun. All exited 0.
- Preparation failures: stale mutating rights on owned level-1 rows required
  explicit zeroing; the unrelated fixture required reload before comparing
  persisted datetime values. The new-form browser assertion was corrected
  because Frappe hides empty read-only fields. The focused Desk test and full
  UI gate then passed.
- Tests failed: none remaining. Tests not run: Linux CI. Blockers: none.
- Domain model: protected provenance and the custom read flow documented.
- Local/CI differences: macOS, MariaDB 12.3.2 and socket administrator; fresh
  bench reuses existing source/runtime via symlinks and logs a nonfatal icon
  warning. No existing site was recreated or dropped.
- Persistent local evidence outside repo: `fix5-api-final2.log`,
  `fix5-permissions-final2.log`, `fix5-browser-focus.log`,
  `fix5-gate-final.log`, `fix5-oct8-fresh.log`.
