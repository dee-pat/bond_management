# Investor detail child permissions

## Scope and acceptance

Statement and market-date detail APIs must apply ordinary Frappe document
permissions before returning child rows. A mixed document containing a Bond
Master outside the user's permissions is denied as a whole; this change does
not introduce partial holdings or market snapshots.

Add regressions for mixed readable/unreadable children and retain readable
detail projections. Investor screens continue to show their existing error
state and recovery controls. No schema, patch, or relationship changes.

## Verification and progress

Required: targeted permission regressions, both complete affected API modules,
`scripts/verify.sh pre-push-ui`, and a representative investor detail smoke.
Implementation and verification passed. Domain graph reviewed;
the existing API/service relationships remain accurate.

## Verification evidence — 2026-10-07

- Risk: permission enforcement in read-only detail APIs.
- Required gates: targeted regression, both affected API modules, pre-push-ui.
- Original market-date regression: exit 1 (PermissionError was not raised).
- Affected modules: market dates 10/10 and statements 11/11, each exit 0.
- Complete `apps/bond_management/scripts/verify.sh pre-push-ui`: exit 0;
  pre-commit, Semgrep, full server suite, frontend lint/typecheck/build, and
  all 49 authenticated Playwright tests passed.
- Earlier gate attempts stopped at missing Redis, missing Chromium, and stale
  test Administrator credentials; these runtime conditions were recovered.
- Tests failed/not run: no remaining required tests. Fresh installation is not
  required for this API-only change. GitHub CI remains pending publication.
- Blockers: none. Domain model reviewed; no mapped relationship changes.
- Local/CI differences: macOS/arm64 and existing test_site with other apps
  installed; CI uses Ubuntu, MariaDB 11.8 and a fresh Frappe/Bond site.
- Commands/logs: `bench --site test_site run-tests --module
  bond_management.bond_management.api.test_investor_market_dates`, same command
  for `test_investor_statements`, and the shared pre-push-ui command above.
  Local logs: `/private/tmp/bond-review-fixes-20261007/fix4-*.log`.
