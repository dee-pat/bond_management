# Registered migration lifecycle regression

## Goal and boundary

Exercise fresh installation and the complete registered Bond Management patch
sequence against representative legacy data, then verify both a forced patch
rerun and the ordinary skip path. This is an opt-in administrative CLI helper;
it never creates, drops, restores, or migrates a site itself. The persistent
Bond Management sites are outside its allowed scope.

The helper resolves the configured bench and active site paths and requires a
uniquely named `bond-management-lifecycle-<32-hex-id>.localhost` site directly
under that bench, Administrator, `allow_tests=true`, and
`bond_migration_lifecycle_test=true`. Flags are parsed as booleans; strings such
as `false` cannot enable mutation. A symlinked `sites` directory cannot move the
test site outside the configured bench. Guard unit tests run in the normal app
suite without enabling this fixture helper.

## Contract and representative data

The public phases are in
`bond_management.bond_management.tests.migration_lifecycle`. `fresh()` checks
all seven manual indexes, their ordered columns and uniqueness, permissions,
and every registered Patch Log immediately after `install-app`, before any
migration. `prepare()` creates synthetic legacy rows and removes only Patch
Logs returned by Frappe's `get_patches_from_app("bond_management")`.

One-time data backfills were retired on 2026-10-13 after every deployed site
had run them; a fresh install marks registered patches complete without running
them. The remaining registered patches bootstrap permissions and indexes and
backfill exchange-rate provenance. Fixtures therefore include a USD purchase, a
statement, a statement-derived FX rate without its provenance row, and a manual
FX rate without its manual-fallback flag. Direct database writes reproduce these
legacy states only after the helper has enforced its temporary-site
administrative boundary. Add representative rows here whenever a new data
patch is registered.

`verify()` asserts transaction financial values, FX provenance and
manual-fallback flags, permissions, and manual indexes. It persists a business
snapshot beside the bench, outside the repository and site configuration.
Snapshots omit generated child names and timestamps while retaining financial
fields, child ordering, and FX provenance. `requeue()` removes
only the registered app Patch Logs for a forced rerun. The next `verify()`
compares business results with the first migrated snapshot. A subsequent
ordinary migration must preserve both the snapshot and Patch Log
identities/timestamps.

## Execution and recovery

Create a uniquely named temporary site under the configured bench and follow
the fresh-site bootstrap in [verification.md](../verification.md). Set
`allow_tests` and `bond_migration_lifecycle_test` to true before installing the
app. Use the same `$TEMP_SITE` for every phase below:

```sh
TEMP_SITE="bond-management-lifecycle-$(python3 -c 'import uuid; print(uuid.uuid4().hex)').localhost"
bench new-site "$TEMP_SITE"
bench --site "$TEMP_SITE" set-config allow_tests true
bench --site "$TEMP_SITE" set-config bond_migration_lifecycle_test true
bench --site "$TEMP_SITE" install-app bond_management
bench --site "$TEMP_SITE" execute bond_management.bond_management.tests.migration_lifecycle.fresh
bench --site "$TEMP_SITE" execute bond_management.bond_management.tests.migration_lifecycle.prepare
bench --site "$TEMP_SITE" migrate
bench --site "$TEMP_SITE" execute bond_management.bond_management.tests.migration_lifecycle.verify
bench --site "$TEMP_SITE" execute bond_management.bond_management.tests.migration_lifecycle.requeue
bench --site "$TEMP_SITE" migrate
bench --site "$TEMP_SITE" execute bond_management.bond_management.tests.migration_lifecycle.verify
bench --site "$TEMP_SITE" migrate
bench --site "$TEMP_SITE" execute bond_management.bond_management.tests.migration_lifecycle.verify
# Capture required logs/results before cleanup, including after a failed phase.
bench drop-site "$TEMP_SITE" --no-backup
```

A failed migration leaves its exact traceback and external evidence available
for inspection. Resolve the failure and rerun the real migrate command before
verification. Do not re-run `prepare()` or delete fixture evidence to hide a
failure. After capturing logs and results, drop the temporary site whether the
run passed or failed. Use a new temporary site for a new complete run. Frappe
manages each CLI transaction; the helper does not commit independently.

## Acceptance and progress

Acceptance requires observed zero exits for formatting/lint, the eight guard
tests, the shared server gate, and every temporary-site lifecycle command above.
No browser test is needed because this change adds server verification only.
The domain model was reviewed: no production relationship or data flow changes.
The initial helper and five guard tests passed locally on 2026-10-08. The
current guard suite has eight cases for the temporary-site policy. Fresh
installation, all 25 then-registered patches on representative legacy data, forced rerun, and
ordinary skipped rerun each exited 0. All seven manual indexes, permissions,
financial values, private attachments and FX provenance were verified. The
shared `pre-push-ui` gate exited 0 with 328 server and 49 browser tests.
See [cleanup evidence](../plans/review-cleanup.md#completion-evidence) for
fixture failures, recovery and platform differences. CI automation of this
opt-in sequence is follow-up work; the current helper is invoked explicitly.
