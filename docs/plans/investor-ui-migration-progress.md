# Investor UI Migration Progress

Last updated: 2026-10-19
Specification: [investor-ui-migration.md](../specs/investor-ui-migration.md)
Current phase: Phase 7 — Pilot
Overall status: Phase 7 in progress; pilot acceptance pending

This file records execution state. Product, architecture and acceptance
decisions belong in the specification. Per-slice plans, parity inventories and
verification logs for Phases 0–7 were retired on 2026-10-15; they remain in git
history (`git log -- docs/plans/investor-ui-migration-progress.md`) and in the
pull requests that delivered each slice.

## Status legend

- `Pending`: no implementation started.
- `In progress`: current implementation slice.
- `Blocked`: cannot proceed; the blocker and required decision are recorded below.
- `Complete`: every completion criterion and required gate passed for the current change.
- `Verified locally; CI follow-up pending`: local gates pass, but a required
  CI-shaped fresh-site or GitHub observation remains unverified.

## Phase summary

| Phase | Slice                                | Status                                 |
| ----- | ------------------------------------ | -------------------------------------- |
| 0     | Decision record and baseline         | Complete                               |
| 1     | Compatibility and toolchain          | Complete                               |
| 2     | Coexistence shell                    | Complete                               |
| 3     | Transaction tracer bullet            | Complete                               |
| 4     | Remaining read-only records          | Complete                               |
| 5     | Reports                              | Complete                               |
| 6     | Parity and hardening                 | Complete                               |
| 6a    | Desk-aligned investor presentation   | Complete                               |
| 7     | Pilot                                | In progress                            |
| 8     | Cutover                              | Pending                                |
| 9     | Legacy investor workspace retirement | Pending                                |

Phases 1 and 6a closed on 2026-10-15 with GitHub Actions
[CI run 38785330040](https://github.com/dee-pat/bond_management/actions/runs/38785330040)
on `69271da`: both jobs ran a fresh `bench new-site`, `install-app` and
`bench build` on Ubuntu with MariaDB 11.8; the server job passed the full
server suite, and the Playwright job passed 56 tests across the
`investor-desktop`, `investor-mobile` and `desk` projects.

## In progress: Phase 7 — Pilot

### Shared report request lifecycle

Completed in [PR #89](https://github.com/dee-pat/bond_management/pull/89), merged
2026-10-18 as `f232f23a3c1d25b34527d2be77ff720f95be4c02`. Portfolio Performance,
Bond Yield Comparison and Interest Difference share the
[report lifecycle contract](../specs/investor-ui-migration.md#reports).
All checks passed on final PR head `52cbf104201a1486e2ab3c21c0eda5e0380f1b1d`:
[Server and Playwright](https://github.com/dee-pat/bond_management/actions/runs/39141064433),
[Frappe Linter and dependency audit](https://github.com/dee-pat/bond_management/actions/runs/39141064419).
Original local `pre-push-ui` also passed: 423 server, 80 Vitest and 61 Playwright tests.

Cleanup verified locally (2026-10-18): consolidated repeated test setup, retained
all 17 scenarios, and folded the standalone spec into the main specification.
Both test versions detected the same eight injected lifecycle faults. Runtime,
APIs, permissions and browser coverage are unchanged; domain model reviewed.
`verify.sh lint`, `yarn lint`, `yarn typecheck`, `yarn test:unit` (80 tests),
documentation-link tests and final diff checks passed (exit 0). Server, browser
and build reruns are unnecessary for these test/doc-only edits; CI links above
cover the original PR. Cleanup CI is recorded on its PR; runtime and total
line deltas are reported separately in the handoff.

Shared composable test harness (2026-10-18): detail/list tests now share Vue
mount/cleanup and async-settling helpers in a test-only module.
Every test and assertion is unchanged; detached mounting, per-test unmounting
and timer/nextTick ordering are preserved. Runtime/data contracts are unchanged.
Domain model reviewed; no update needed. Verified locally: `verify.sh lint`,
frontend lint/typecheck and all 80 unit tests passed (exit 0), as did doc links
and diff checks. Runtime and total line deltas are reported in the handoff.

### Investor API request plumbing

Verified locally (2026-10-19): replaced 16 stateless per-endpoint request objects
with one typed request function. All public methods, response types, GET URLs,
encoding, omitted parameters, headers and error/session handling are unchanged;
each call owns its fetch. No server, dependency or permission changes; domain
model reviewed, with no mapped flow changes. The 36-test API suite passes before
and after refactoring, including 23 endpoint/omission cases. TypeScript confirms
all 16 public signatures match. `pre-push-ui` exited 0: lint/Semgrep, 424 server
tests, frontend lint/typecheck, 100 unit tests, build and 61 Playwright tests.
Doc links and diff checks pass; fresh-install/opt-in checks do not apply.
Runtime and total line deltas are reported in the handoff.

### Shared investor page registry

Consolidate the shell's page components, titles, parent sections and bootstrap
flags with the five detail route paths in `frontend/src/page-registry.ts`.
Keep eager imports, navigation order, route names/parameters, history base,
home and not-found handling, breadcrumbs and bootstrap delivery unchanged.
No API or permission changes; the domain model was reviewed and needs no update.
Acceptance: all five existing detail browser flows check their parent link,
leaf breadcrumb and active navigation before and after refresh; the complete
`pre-push-ui` gate passes.
Verified locally on 2026-10-19: the five detail flows passed against the existing
build before refactoring (6 tests including setup); all 13 page definitions and
15 ordered routes matched the baseline. `pre-push-ui` exited zero: lint, 424
server tests, frontend lint/typecheck, 100 unit tests, build and 61 browser tests.
Doc links and diff checks pass. Fresh-install and opt-in gates do not apply.
Remote CI evidence is recorded in the pull request. Runtime is 8 net lines smaller;
tests add 67 lines. Total, including this note, is 77 net lines larger.

### Investor request isolation

A review on 2026-10-16 found that each investor endpoint shared one frappe-ui
`useCall`. A request that failed before any response (dropped connection,
server restart) resolved with that call's previous response, so a rerun or
filter change could show another portfolio's or date's values with no error.
`frontend/src/lib/api.ts` now sends every request through its own call, so the
failed state from the specification shows instead. No API, data, permission or
financial rule changes; the domain model was reviewed and is unchanged.
The new focused specs failed before the fix (the transaction list showed
Portfolio A rows under a Portfolio B filter) and pass after it. The
`pre-push-ui` gate passed on 2026-10-16: lint, 383 server tests, frontend
lint/typecheck/build, and 60 Playwright tests.

### Investor API status mapping and formatter edge cases

While adding Vitest unit tests for `frontend/src/lib` on 2026-10-18, we found
that Frappe v1 `/api/method` errors carry `exc_type`, not frappe-ui's
`errors[]`, and `useCall` drops the HTTP status. The SPA recognised a 403 only
through the HTTP/1.1 status text `FORBIDDEN`. A 401 showed the generic error,
and over HTTP/2 (no status text) every expired session did too, instead of
redirecting to login. On the user's decision, `frontend/src/lib/api.ts` now
sends each request with its own `fetch` and the same headers. It maps the
HTTP status first and `exc_type` second, and keeps the Guest-cookie rule for
session expiry. The user also accepted these formatter changes:
`formatDate` returns the dash for invalid or impossible dates and formats the
date part of a datetime; `formatNumber`, `formatMoney` and `formatPercent`
drop the sign of zero and return the dash for non-finite values;
`toFilterValue` ignores plain objects. No API, data, permission or financial
rule changes; the domain model was reviewed and is unchanged.
`e2e/investor/hardening.spec.ts` gains a focused 401-redirect spec. It failed
before the change (the page stayed on `/bond-investor/transactions`) and
passes after it.

### Frappe-ui control prototype

Follow-up trial accepted by the user on 2026-10-16: replace five detail back
links with frappe-ui route Buttons, use Button variants and semantic utilities
for active filter chips, and reuse the existing frappe-ui-backed `DataList` for
Interest Difference. Link destinations, clear-filter actions, report labels,
row markers, values, and total-row styling remain intact.
The domain model was reviewed; this slice changes no data, permissions, or API.
Frontend source is 53 net lines smaller. Back Buttons add markup overall; filter
chips and the reused report list supply the reduction. The focused desktop and
mobile browser run passed 8 tests. The final `pre-push-ui` gate passed lint,
331 server tests, frontend lint/typecheck/build, and 58 Playwright tests after
the filter-chip spacing adjustment. This visual acceptance applies to the
follow-up trial; the broader Phase 7 pilot acceptance remains pending.

Trial a small reduction in custom Investor SPA styling: use frappe-ui badges
for read-only labels, frappe-ui link buttons for private PDF actions, and a
themed frappe-ui button for the reconciliation status filter. Preserve the
read-only API contract, filter action, attachment URLs, accessible names, and
separate View and Download behavior. No data, permission, or financial rule
changes are in scope. If the components fail visual or browser verification,
revert this isolated UI slice. Acceptance requires frontend lint, typecheck,
build, and browser coverage of statement list/detail and attachments. The
domain model was reviewed; no data relationship or service flow changes.

Verified locally on 2026-10-16: frontend ESLint, `vue-tsc`, and `yarn build`
passed; the complete Playwright UI gate passed (57 tests); and the
focused statement browser spec passed after adding checks for the status
filter button and separate PDF link attributes (2 tests including setup).
The `verify.sh frontend` wrapper reached its `bench build` step but bench
could not write `logs/bench.log` inside the sandbox, so the direct Vite build
supplies the build evidence. Pilot acceptance remains pending.

After visual review, the PDF actions needed clearer separation from the old
link styling. View now uses a blue solid button with an eye icon; Download
uses a gray outline button with a download icon. Both retain their link and
accessible-name behavior. The revised controls passed frontend lint,
typecheck, Vite build, and the focused desktop and mobile statement browser
specs (3 tests including setup) on 2026-10-16.
The user reviewed the statement and transaction controls and accepted this
UI slice on 2026-10-16. This does not close the separate Phase 7 pilot
acceptance items below.

Validate the read-only SPA with real pilot workflows while keeping the legacy
investor Workspace as the Apps fallback. Investor login targets the Vue
homepage when the site flag is enabled. Pilot feedback on Yield Comparison
(line-only chart, yearly labels, permission-scoped default dates) is done, and
rollback by disabling `bond_investor_spa_enabled` was rehearsed locally on
2026-08-26.

Pilot evidence names who accepted the release, when, which of the eight
surfaces they exercised, and any defect or follow-up created. The
statement/reporting cycle uses a real pilot investor's assigned portfolio and
covers a statement plus both reports, without recording financial values,
credentials or private attachment metadata in this repository.

Open:

- [ ] Record internal-team acceptance: participants, date and reviewed surfaces.
- [ ] Complete one full statement/reporting cycle with pilot investors; record
      the date, participants and defects found.
- [ ] Resolve every high-severity pilot defect and link its verification.
- [ ] Record the final pilot-site flag state and who approved it.

## Cutover and retirement gates

- [ ] Phase 7 items above complete.
- [ ] Cutover observation period completed without a rollback condition.
- [ ] Legacy workspace removal approved as a separate release.
- [ ] Internal Desk behaviours and their Playwright ownership confirmed before
      removing any Desk spec.
