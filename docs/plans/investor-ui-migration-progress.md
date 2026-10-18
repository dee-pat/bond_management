# Investor UI Migration Progress

Last updated: 2026-10-18
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

Verified locally (2026-10-18): Portfolio Performance, Bond Yield Comparison and
Interest Difference now share `useReportRequest`, preserving page validation,
stale-response protection, session-expiry redirects and clipboard invalidation.
The [focused spec](../specs/report-request-lifecycle.md) defines the contract and
gates. No API, financial or permission changes; `docs/domain-model.md` reviewed
and unchanged. Implementation branch: `codex/frontend-report-lifecycle`.

- Risk: shared frontend report state; required gate is `pre-push-ui` plus
  scoped pre-commit including new files.
- `BASE_URL=http://localhost:8001 apps/bond_management/scripts/verify.sh pre-push-ui`
  from the bench: exit 0. Lint/Semgrep/rule checks, 423 server tests (56 unit,
  357 integration and 10 unspecified-category), frontend lint/typecheck,
  80 Vitest tests, production build and all 61 authenticated Playwright tests
  passed. The extended Performance failure flow now verifies a successful Retry.
- The new helper has 17 deferred-promise regression cases. Removing its stale
  guards temporarily produced 10 failures (exit 1); restoring them passed all
  17 (exit 0). The initial test run before adding the helper failed to import
  the not-yet-created module; it was not a product regression.
- Scoped pre-commit initially formatted the three Vue files; its final rerun
  and `git diff --check` passed. No unresolved test failure or blocker remains.
- No separate fresh-install or opt-in migration/share-race run is needed:
  schema, hooks, dependencies and permission logic are unchanged. Remote CI
  evidence belongs to the PR checks for the published revision; the results
  above are local evidence. Local macOS and its existing test site do not
  reproduce CI's fresh Ubuntu/MariaDB 11.8 setup.

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
