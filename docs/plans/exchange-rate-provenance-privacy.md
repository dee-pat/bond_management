# Exchange-rate statement privacy

The representative statement link can reveal another portfolio's source
statement. This note records the protection added by PR #19 and the follow-up
that closes generic-list filter probes while keeping shared exchange rates
available to investors.

`Bond Exchange Rate.statement` uses permission level 1. Only Bond Management
Manager and System Manager receive the app-owned level-1 read permission; the
existing idempotent install and migration bootstrap maintains those rows.
The investor detail API first authorizes the exchange-rate row through a
permission-scoped query, then reads its private representative name and returns
it only when the caller can read the linked statement. Its response shape and
readable-statement navigation remain compatible. Generic document APIs omit
provenance, and generic list APIs also hide a rate row when its representative
statement is unreadable. The query condition closes filter side channels on
generic list paths that accept protected-field filters, while Frappe versions
that reject those filters deny the probe directly. Fixed investor and
performance projections retain shared rate history without selecting the private
link.

No financial values, provenance ownership, or stored links change. Desk keeps
the manager's representative statement field visible and read-only. The
permission bootstrap updates only its owned role/permission-level rows.

## Acceptance and verification

- Real `frappe.client.get` and `frappe.api.v1.read_doc` regressions omit
  investor provenance and retain manager provenance.
- Generic list results retain readable or null provenance, hide rows with
  unreadable provenance, and reject or return no match for a protected-link probe.
- Investor detail retains readable references and masks unreadable ones.
- Bootstrap repairs missing or changed owned level-1 rows, reruns safely, and
  preserves unrelated permission rows. Existing fresh-install/migrate hooks
  continue to invoke it.
- A representative Desk smoke assertion checks the protected read-only field
  metadata; Frappe hides empty read-only values on a new form.
- Run targeted tests and complete affected API/permission modules, then
  `apps/bond_management/scripts/verify.sh pre-push-ui` from the bench. Validate
  hook registration and permissions on a freshly installed site.

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

## Filter side-channel follow-up evidence

- Risk classification: investor row privacy and permission-query hook behavior.
- Required gates: focused regression, complete affected API and permission
  modules, full server/frontend/Playwright gate, and fresh-site installation.
- Commands executed from the temporary bench using the PR checkout first on
  `PYTHONPATH`:
  - `bench --site test_site run-tests --app bond_management --module bond_management.bond_management.api.test_investor_exchange_rates --test test_detail_masks_an_unreadable_cross_portfolio_statement_reference`
  - `bench --site test_site run-tests --app bond_management --module bond_management.bond_management.api.test_investor_exchange_rates`
  - `bench --site test_site run-tests --app bond_management --module bond_management.bond_management.utils.test_investor_permissions`
  - `apps/bond_management/scripts/verify.sh pre-push-ui`
  - Fresh MariaDB site creation, app install, `set-config allow_tests true`,
    then the complete `utils.test_investor_permissions` module.
- Exit statuses: all final commands exited 0. The focused test ran 1 case; the
  API and permission modules ran 13 and 19 tests; the full gate ran 290 server
  tests and 49 authenticated browser tests. Pre-commit, Semgrep, frontend lint,
  typecheck, and production build passed.
- Final `apps/bond_management/scripts/verify.sh lint` exited 0 after the
  evidence update, using the bench's Semgrep executable and cached Frappe rules.
- Fresh-site result: app installation exited 0 and all 19 permission tests
  passed, including hook registration. Temporary database and Administrator
  passwords were generated for the disposable site and are not recorded here.
- Tests failed: none remaining. Tests not run: Linux CI. Blockers: none.
- Resolved setup issues: the initial assertion now accepts Frappe's protected
  filter rejection as well as a zero-row result; the browser server was restarted
  after building the SPA route. The final full gate passed after those fixes.
- Domain model: reviewed and updated for the new list-query privacy boundary.
- Local/CI differences: macOS and MariaDB 12.3.2 (Frappe warned that this is
  newer than its tested 11.8 version); the final fresh-site install used the
  local MariaDB socket administrator. CI runs on Linux with its run-scoped
  MariaDB setup.
