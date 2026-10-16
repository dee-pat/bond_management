# Investor UI Migration Progress

Last updated: 2026-10-16
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
