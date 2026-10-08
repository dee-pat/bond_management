# Market yield availability

Persist a hidden, read-only `Bond Market Prices.future_xirr_available` Check
(default 0) because Frappe stores an unavailable Percent result as zero. The
server derives the flag from solver success, including a genuine zero result.
The investor market-detail API and yield-comparison report expose `None` when
the flag is false. Desk displays Unavailable and omits that curve point.

Historical guesses filter available rows before ranking, preserving zero and
falling back to an older available yield. Performance keeps the latest market
quote regardless of its yield availability and uses only an available yield
from that quote as the batched guess. Existing permissions, cash-flow signs,
solver behavior and price conventions remain unchanged.

The registered post-model-sync migration recalculates legacy yields with
`DEFAULT_XIRR_GUESS` and updates only yield and availability, preserving row
metadata and unrelated derived values. It is safe to rerun; fresh installations
have no legacy rows and normal controller validation derives the flag.

Acceptance covers real persisted zero, positive, negative and matured results;
stale numeric values masked by the flag; recalculation responses; historical
fallback; latest performance quotes; registered migration ordering and rerun;
and one Desk rendering smoke for unavailable versus zero.

The market-detail response adds availability; the yield-comparison report keeps
its existing five-field projection and expresses unavailable yield as null.

## Verification evidence

- Risk classification: persisted financial availability, data backfill, API/report
  projection and shared Desk behavior.
- Required gates: targeted and complete affected modules, full server/frontend/UI
  gate, fresh install and actual registered migration sequence with legacy data.
- Commands executed: `bench --site test_site migrate`; `bench --site test_site
  run-tests --app bond_management --module` for
  `doctype.bond_market_date.test_market_xirr_availability`,
  `patches.test_backfill_market_xirr_availability`,
  `doctype.bond_market_date.test_bond_market_date`,
  `api.test_investor_market_dates`, `api.test_investor_yield_comparison`,
  `utils.test_xirr`, `report.portfolio_performance.test_portfolio_performance`
  and `report.bond_yield_comparison.test_bond_yield_comparison`; full module
  prefixes use `bond_management.bond_management`, except app-level patches.
  Also `scripts/verify.sh pre-push-ui` and final `scripts/verify.sh lint`.
- Exit statuses: all eight completed module checks and full UI gate exited 0;
  final lint runs after the evidence update before committing.
- Tests passed: 86 tests across affected modules, 332 full-suite server tests,
  and 50 authenticated browser tests, including Desk/investor null-versus-zero.
- Fresh commands: independent new-site/install-app; index/Patch Log assertions
  before first migrate; four ambiguous legacy yields plus childless snapshot;
  all 26 registered patches through actual migrate; value/flag, unrelated-column
  and timestamp assertions; forced full patch rerun and ordinary skipped rerun
  with the same assertions. All completed commands exited 0.
- Preparation failures: the report API regression caught an unnecessary extra
  report field, which was removed to preserve the fixed projection; a new
  zero-yield fixture collided with an existing fixed date and now uses the
  collision-safe factory. Complete affected modules and full gate passed after
  both corrections.
- Tests failed: none remaining. Tests not run: Linux CI. Blockers: none.
- Domain model: availability and report/API data flows documented.
- Local/CI differences: macOS/MariaDB 12.3.2/socket administrator; new disposable
  benches reuse source/runtime via symlinks and log a nonfatal icon warning.
  Existing sites/databases were preserved.
- Persistent local evidence outside repo: `fix6-module-*.log`, `fix6-gate.log`
  and `fix6-oct8-fresh.log`.
