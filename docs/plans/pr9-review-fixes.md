# PR #9 review fixes

## Scope and acceptance

- Keep historical cash-flow copying available in Desk and the investor app
  when XIRR has no solution. Undefined yields remain blank; mixed-currency
  native totals remain unavailable. Use existing server permission checks.
- Compare statement exchange rates at the existing 12-decimal persistence
  boundary so identical PDF inputs share provenance. Preserve real conflict
  detection and manual fallback behavior without changing the schema.
- Select the latest non-null historical XIRR, including a genuine zero yield.
  Preserve query permissions and date ordering.

Regression scenarios reproduce the reviewed failures. Existing financial
signs, cash-flow calculation, access control, and database ownership remain
unchanged.

## Verification plan

Run targeted regressions and complete affected server modules serially on
`test_site`, then run `scripts/verify.sh pre-push` and
`scripts/verify.sh pre-push-ui` from the bench using the app-relative path.
Use focused Cypress and Playwright flows for cash-flow copying. No fresh-site
check is required unless implementation changes schema, patches, hooks,
dependencies, installation, or indexes.

## Progress

All three fixes are implemented and verified. The cash-flow availability fields
are additive API fields documented in the investor UI specification and domain
model. Rate normalization uses half-up rounding only at the existing exchange
rate storage boundary; the cash-flow half-even convention remains unchanged.

## Verification evidence — 2026-09-18

- Risk classification: medium; financial rate comparison, historical solver
  inputs, and report clipboard availability.
- Required gates: targeted regressions, affected server modules, focused
  Cypress/Playwright, `pre-push`, and `pre-push-ui`.
- Commands executed: the commands below all completed with exit status `0`.
- Tests passed: 8 targeted server regressions; 96 tests across the five affected
  server modules; all 321 server tests in each complete gate; all 14 Cypress
  tests across 8 specs; all 34 Playwright tests. The focused browser runs passed
  2 Cypress tests and the Playwright authentication setup plus performance test.
  Pre-commit, Semgrep scans/rule tests, frontend lint/typecheck/build, Markdown
  formatting, and `git diff --check` passed.
- Tests failed: initial fixtures exposed two test issues: a NULL write to the
  non-nullable `future_xirr` column and a duplicate fixed market date under full
  module ordering. The corrected tests exercise supported schema values and a
  collision-safe quote date; their financial assertions were retained. The
  initial pre-commit pass formatted two Python files, then the rerun passed.
- Tests not run: GitHub Actions for these fixes; local fresh-site installation.
  These follow-up fixes change no schema, patches, hooks, dependencies,
  installation behavior, or indexes. The original PR's broader fresh-install
  scope remains owned by its CI jobs.
- Blockers: none for these fixes.
- Domain model: graph and notes updated for report cash-flow availability;
  DocTypes, links, and service ownership remain unchanged.
- Unverified local/CI differences: local macOS/arm64, existing `test_site`,
  Redis 8.8, Chrome 152 and Playwright Chromium at `http://localhost:8001`;
  CI uses Ubuntu, MariaDB 11.8 and its own fresh-site/browser setup.
- Test limitation: current `Bond Market Prices.future_xirr` is non-nullable,
  so the history regressions cover zero, positive, negative and date boundaries.
  The query now uses an explicit non-null predicate that also supports nullable
  historical data without excluding zero.

### Executed commands

Commands run from the bench unless otherwise stated. Browser credentials came
from the existing test-site configuration and were never written to the repo.

```sh
bench --site test_site set-config allow_tests true
bench --site test_site migrate
bench --site test_site run-tests --module bond_management.bond_management.utils.test_xirr --test test_last_guess_keeps_zero_yield_and_respects_market_date --test test_last_guess_retains_negative_yield_at_date_boundary
bench --site test_site run-tests --module bond_management.bond_management.doctype.bond_exchange_rate.test_bond_exchange_rate --test test_identical_high_precision_statement_rates_share_the_stored_rate --test test_high_precision_statement_rates_conflict_at_stored_precision --test test_high_precision_statement_rate_matches_stored_manual_fallback --test test_statement_rate_rounds_half_up_at_storage_precision --test test_statement_rate_below_storage_precision_is_rejected
bench --site test_site run-tests --module bond_management.bond_management.report.portfolio_performance.test_portfolio_performance --test test_same_day_purchase_keeps_cashflow_exports_without_xirr
bench --site test_site run-tests --module bond_management.bond_management.utils.test_xirr
bench --site test_site run-tests --module bond_management.bond_management.doctype.bond_exchange_rate.test_bond_exchange_rate
bench --site test_site run-tests --module bond_management.bond_management.doctype.bond_statement.test_bond_statement
bench --site test_site run-tests --module bond_management.bond_management.report.portfolio_performance.test_portfolio_performance
bench --site test_site run-tests --module bond_management.bond_management.api.test_investor_performance
apps/bond_management/scripts/verify.sh pre-push
apps/bond_management/scripts/verify.sh pre-push-ui
CYPRESS_SPEC=cypress/integration/portfolio_performance.js apps/bond_management/scripts/verify.sh ui
```

From the app root, the focused Playwright command was
`yarn test:e2e e2e/tests/investor-performance.spec.ts --project=chromium`.
The browser commands used `BASE_URL` and `CYPRESS_baseUrl` set to
`http://localhost:8001`, and `CHROME_BIN` set to the installed macOS Chrome.

Detailed local logs are retained at `/tmp/pr9-fixes-*.log`.
