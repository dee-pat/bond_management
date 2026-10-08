# Registered migration lifecycle regression

## Goal and boundary

Exercise fresh installation and the complete registered Bond Management patch
sequence against representative legacy data, then verify both a forced patch
rerun and the ordinary skip path. This is an opt-in administrative CLI helper;
it never creates, drops, restores, or migrates a site itself. Canonical bench
sites are outside its allowed scope, including canonical `test_site`.

The helper resolves the bench and active site paths and requires a bench under
the system temporary directory, its own `test_site`, Administrator,
`allow_tests=true`, and `bond_migration_lifecycle_test=true`. Flags are parsed as
booleans; strings such as `false` cannot enable mutation. A symlink under the
temporary directory cannot disguise a bench elsewhere. Guard unit tests run in
the normal app suite without enabling this fixture helper.

## Contract and representative data

The public phases are in
`bond_management.bond_management.tests.migration_lifecycle`. `fresh()` checks
all seven manual indexes, their ordered columns and uniqueness, permissions,
and every registered Patch Log immediately after `install-app`, before any
migration. `prepare()` creates synthetic legacy rows and removes only Patch
Logs returned by Frappe's `get_patches_from_app("bond_management")`.

Fixtures include a USD purchase with stale principal and net consideration;
a Kenya quantity-change bond with stale coupon cadence, flag, and market
values; encrypted private legacy confirmation and nominal-face-value statement
PDFs; a duplicate statement sharing a private File; and a statement-derived FX
rate with the obsolete portfolio column/scoped index and stale reverse rate.
They use synthetic identities rather than impersonating the known correction
patch's real records. Direct database/schema writes reproduce legacy states
only after the helper has enforced its disposable administrative boundary.

`verify()` asserts financial values, statement quantity/nominal conversion,
private attachment ownership and canonical filenames, v8 reconciliation,
Kenya schedule/market values, global FX scope/reverse rate/provenance,
permissions, and manual indexes. It persists a business snapshot beside the
bench, outside the repository and site configuration. Snapshots omit generated
child names and timestamps while retaining financial fields, child ordering,
current private File references, and FX provenance. Obsolete reconciliation
reports queued for asynchronous deletion are excluded. `requeue()` removes only
the registered app Patch Logs for a forced rerun. The next `verify()` compares
business results with the first migrated snapshot. A subsequent ordinary
migration must preserve both the snapshot and Patch Log identities/timestamps.

## Execution and recovery

Create an explicitly authorized fresh disposable bench/site following the CI
bootstrap in [verification.md](../verification.md). Set both test flags before
installing the app. In that bench, execute these phases in order:

```sh
bench --site test_site install-app bond_management
bench --site test_site execute bond_management.bond_management.tests.migration_lifecycle.fresh
bench --site test_site execute bond_management.bond_management.tests.migration_lifecycle.prepare
bench --site test_site migrate
bench --site test_site execute bond_management.bond_management.tests.migration_lifecycle.verify
bench --site test_site execute bond_management.bond_management.tests.migration_lifecycle.requeue
bench --site test_site migrate
bench --site test_site execute bond_management.bond_management.tests.migration_lifecycle.verify
bench --site test_site migrate
bench --site test_site execute bond_management.bond_management.tests.migration_lifecycle.verify
```

A failed migration leaves its exact traceback and external evidence available
for inspection. Resolve the failure and rerun the real migrate command before
verification. Do not re-run `prepare()` or delete fixture evidence to hide a
failure. Start another authorized disposable bench for a new complete run.
Frappe manages each CLI transaction; the helper does not commit independently.

## Acceptance and progress

Acceptance requires observed zero exits for formatting/lint, the five guard
tests, the shared server gate, and every disposable lifecycle command above.
No browser test is needed because this change adds server verification only.
The domain model was reviewed: no production relationship or data flow changes.
The helper and five guard tests passed locally on 2026-10-08. Fresh installation,
all 25 registered patches on representative legacy data, forced rerun, and
ordinary skipped rerun each exited 0. All seven manual indexes, permissions,
financial values, private attachments and FX provenance were verified. The
shared `pre-push-ui` gate exited 0 with 328 server and 49 browser tests.
See [cleanup evidence](../plans/review-cleanup.md#completion-evidence) for
fixture failures, recovery and platform differences. CI automation of this
opt-in sequence is follow-up work; the current helper is invoked explicitly.
