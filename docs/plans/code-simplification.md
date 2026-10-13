# Code simplification

Reduce repeated implementation and test setup while preserving financial
results, public API contracts, permissions, and recovery behavior.

## Scope and sequence

1. Declare investor response field contracts independently in tests.
2. Share investor test user/session helpers; retain distinct permission cases.
3. Share report and cash-flow export calculations using the loaded context.
4. Share detail-page loading without changing the keyed router lifecycle.
5. Consolidate shell route selection, list parameters, and private-byte reads.
6. Trim browser repetition only where another test owns the same behavior.

The report and export retain their public signatures and permission checks.
Cash flows keep Decimal arithmetic, settlement/maturity semantics, and historical
rates for past flows versus valuation-date rates for future flows. The SPA keeps
`RouterView` keyed by `route.fullPath`, its breakpoint Teleport, and retry/request
version guards. No schema, migration, locking, uniqueness, RPC, or response
allowlist changes are planned.

## Verification

Run the affected investor API modules and full affected report module, including
report/export consistency before, on, and after maturity with changing FX rates.
Run `scripts/verify.sh pre-push-ui` from the bench root with the dedicated test
site and external browser credentials. Preserve security and recovery scenarios;
do not add a route watcher or a redundant navigation regression. Review the
domain model and record gate commands and observed results below.

## Progress

- Independent field contracts now cover all 23 projections. Endpoint tests
  retain their financial and portfolio/child/provenance assertions.
- Eight user factories and seven session helpers now use shared factories.
  The common access matrix covers 33 combinations across the same 11 endpoints.
- Report/export position and cash-flow construction are shared inside the report
  module. Exports still build only their selected series and authorize at the
  endpoint. The new consistency test covers native/reporting and bond/TOTAL
  cash flows before, on, and after maturity with changing FX rates.
- Detail loading, shell route selection, list parameters, and private-byte reads
  are consolidated. The keyed router and breakpoint Teleport are preserved.
- Mobile yield coverage drops repeated defaults and description assertions;
  short mobile journeys and stale-response/recovery regressions are retained.
- Domain graph reviewed and processing notes synchronized. No mapped
  relationships or schema changed. Independent production review found no
  concrete defects.

## Local verification evidence

- Risk classification: medium; shared financial orchestration and frontend
  lifecycle cleanup, with unchanged business rules and authorization boundaries.
- Required gates: affected server modules, focused browser coverage, lint,
  full server suite, frontend lint/typecheck/build, full investor/Desk UI suite.
- Commands executed (bench commands from the configured bench root):
  - `bench --site bond-management-test.localhost run-tests --module bond_management.bond_management.api.test_investor_response_boundary`
  - The same `run-tests --module` command for API modules `test_investor`,
    `test_investor_bonds`, `test_investor_exchange_rates`,
    `test_investor_market_dates`, `test_investor_performance`,
    `test_investor_statements`, `test_investor_transactions`, and
    `test_investor_yield_comparison`.
  - `bench --site bond-management-test.localhost run-tests --module bond_management.bond_management.report.portfolio_performance.test_portfolio_performance --test test_report_and_exports_share_cashflows_across_fx_and_maturity_boundaries`
  - The same report module command without `--test` for all 25 report tests.
  - `bench --site bond-management-test.localhost run-tests --module bond_management.bond_management.utils.test_private_attachment`
  - `BASE_URL=http://localhost:8001 yarn playwright test e2e/investor/hardening.spec.ts e2e/investor/yield-comparison.mobile.spec.ts --project=investor-desktop --project=investor-mobile` (from app root).
  - `BASE_URL=http://localhost:8001 apps/bond_management/scripts/verify.sh pre-push-ui`
  - Explicit `pre-commit run --files` and Frappe/app Semgrep scans with
    `--no-git-ignore` for the new untracked contract and detail-helper files,
    supplementing the gate's tracked-file scans.
- Exit statuses: all final commands above exited 0. An intermediate lint pass
  exited 1 after automatic formatting; the final gate passed. An intermediate
  report run found a local `_` name collision with Frappe's translator; the
  collision was corrected and the full report and app suites passed afterward.
- Tests passed: final affected API modules 70 tests (including the access
  test with 33 cases); report module 25; private attachment module 7; focused
  browser run 10 including setup. Full server gate: 52 unit, 338 integration, and 13 additional
  unittest cases (403 total). Full Playwright gate: 56 including two auth setups.
  Semgrep rule tests and verification-script tests also passed.
- Tests failed: none in final verification.
- Tests not run: remote CI and opt-in temporary-site migration/share-race
  lifecycle helpers; no schema, patch, hook, installation, or index changes
  require a fresh-install gate for this refactor.
- Blockers: none for local verification. PR publication is authorized after local verification.
- Unverified local/CI differences: local macOS configured bench and persistent
  dedicated test site versus Linux CI's fresh bench/site. Remote CI results will be recorded on the PR after publication.
