# Review cleanup

Consolidate repeated list pagination, portfolio access checks, clipboard safety,
attachment presentation, and transaction Bond Master loading while preserving
public contracts and all financial conventions. Keep the existing linear schedule
search. Add an opted-in disposable-bench lifecycle check for the whole registered
patch sequence and fresh-install indexes.

API endpoints retain explicit field projections, permission-aware queries, and
sort/filter allowlists. The shared frontend list state must preserve stale-response,
retry, pagination and failed-filter recovery. Transaction validation reads one Bond
Master for its snapshot and calculations; standalone calculation methods remain
compatible. Migration checks must reject the canonical bench, require parsed
allow_tests and opt-in configuration, and inspect persisted financial results and
private attachments through first migrate, forced rerun, and skipped rerun.

Acceptance: targeted/affected modules and the full pre-push-ui gate exit zero;
fresh install and actual registered migration lifecycle checks pass. Domain graph
review and command/exit evidence will be recorded before publishing.

Progress: implementation and local verification complete, 2026-10-08. The
linear schedule search remains unchanged. No production data patch or new
dependency was added.

## Completion evidence

- Risk classification: shared API/UI refactoring, financial calculation reuse,
  and opt-in administrative migration fixtures.
- Required gates: affected server modules, full `pre-push-ui`, fresh install,
  registered legacy migration sequence, forced rerun and ordinary skip path.
- Commands executed: `apps/bond_management/scripts/verify.sh pre-push-ui`
  from the canonical bench; exit 0, 328 server tests and 49 Playwright tests.
  This includes pre-commit, Semgrep, migration, frontend lint/typecheck/build.
- Affected modules: `bench --site test_site run-tests --app bond_management
  --module <module>` exited 0 separately for `utils.test_accrual`,
  `doctype.bond_transaction.test_bond_transaction`, and
  `api.test_investor{,_transactions,_statements,_bonds,_market_dates,
  _exchange_rates,_performance,_yield_comparison,_response_boundary}` under
  `bond_management.bond_management`; 115 tests. The complete
  `tests.test_migration_lifecycle` module exited 0 with five guard tests.
- Disposable lifecycle: fresh `bench new-site` and `install-app` exited 0;
  both flags were set with `bench --site test_site set-config <flag> True
  --parse`. Every `bench execute` and `bench migrate` command in
  [the lifecycle specification](../specs/migration-lifecycle.md#execution-and-recovery)
  exited 0. All 25 registered patches, seven manual indexes, owned permissions,
  legacy financial values, private PDFs and FX provenance were verified.
  Forced rerun preserved the business snapshot; normal migrate also preserved
  Patch Log identities and timestamps.
- Clipboard compatibility: an external Node check exited 0 for formula prefixes,
  controls, numeric negative values, SPA Unicode behavior, report serialization,
  idempotent registration and attachment CSS wiring.
- Tests failed: initial lint reformatted three files; initial fresh guard used
  the symlinked source bench instead of active site paths; initial legacy fixture
  copy omitted Draft docstatus. These were corrected and relevant gates rerun.
  The failed disposable fixture database and logs were preserved; a new site
  passed the complete lifecycle. No failures remain in the final gates.
- Tests not run: remote Linux CI and automated CI lifecycle orchestration.
- Blockers: none locally. Domain graph reviewed and notes updated; mapped
  relationships and financial conventions remain unchanged.
- Unverified local/CI differences: macOS socket-authenticated MariaDB 12.3
  and local Chromium versus Linux CI's run-scoped services/browser setup.
  CI automation for the explicitly invoked lifecycle helper is follow-up work.

## Async report cleanup follow-up (2026-10-09)

- Risk classification: queued generated-report cleanup could remove a File after
  a forced migration rerun had made it the statement's current report.
- Fix: the cleanup worker checks the statement's current report field before
  deleting. The regression test verifies that an in-use report survives and is
  deleted after its statement is removed.
- Required gates: focused Bond Statement integration module and the shared
  `pre-push` gate.
- Commands executed: `apps/bond_management/scripts/verify.sh pre-push` first
  stopped with exit 1 because Ruff formatted the changed utility; the rerun
  exited 0. `apps/bond_management/scripts/verify.sh lint` exited 0 after this
  evidence was added. `bench --site test_site run-tests --app bond_management --module
  bond_management.bond_management.doctype.bond_statement.test_bond_statement`
  exited 0.
- Tests passed: the shared gate ran 282 primary and 9 unspecified server tests;
  the focused Bond Statement module ran 35 tests.
- Tests failed: none. The initial formatting stop occurred before test setup.
- Tests not run: UI, browser, and fresh-install lifecycle gates were not
  applicable to this server utility change.
- Blockers: none. The domain graph was reviewed; no mapped relationship or
  financial convention changed.
- Unverified local/CI differences: Linux CI has not run for this new commit.
