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

Phases 1 and 6a closed on 2026-10-15 in
[#50](https://github.com/dee-pat/bond_management/pull/50).

## In progress: Phase 7 — Pilot

Done during the pilot (behaviour and acceptance notes are on each PR):

| Slice | PR |
| --- | --- |
| frappe-ui badges, link buttons and status filter in investor details; accepted by the user 2026-10-16 | [#55](https://github.com/dee-pat/bond_management/pull/55) |
| frappe-ui back buttons, filter chips and the shared `DataList` for Interest Difference | [#56](https://github.com/dee-pat/bond_management/pull/56) |
| Each investor request owns its call, so a failed request never shows an earlier response | [#57](https://github.com/dee-pat/bond_management/pull/57) |
| API errors mapped by HTTP status, then `exc_type`; formatter edge cases; Vitest | [#76](https://github.com/dee-pat/bond_management/pull/76) |
| Shared report request lifecycle for the three reports ([contract](../specs/investor-ui-migration.md#reports)) | [#89](https://github.com/dee-pat/bond_management/pull/89), [#90](https://github.com/dee-pat/bond_management/pull/90) |
| Shared composable test mount and settle helpers | [#93](https://github.com/dee-pat/bond_management/pull/93) |
| One typed investor request function | [#94](https://github.com/dee-pat/bond_management/pull/94) |
| Shared page registry for shell pages and detail routes | [#96](https://github.com/dee-pat/bond_management/pull/96) |

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
