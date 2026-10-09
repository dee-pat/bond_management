# Review fix 3: strict investor sharing boundary

Investors remain read-only and may read only assigned portfolios, including
when another role or a Frappe DocShare grants broader rights. Administrator and
users without the investor role retain the standard permission model.

## Implementation and compatibility

Frappe applies its share fallback after permission hooks and includes shares in
list queries. Supported document mixins enforce direct-document permissions;
financial mutation hooks independently reject investor actors. Always-run
DocShare hooks reject incompatible recipients and investor actors, including
combined investor/manager roles and supported server callers using internal
validation flags. HTTP dispatch strips those flags; no remote flag-injection
exploit is claimed.

Portfolio data cannot be shared with everyone. Global app documents may have
read shares, but investor/everyone recipients cannot receive mutating rights.
The registered cleanup patch and after-install hook remove inaccessible app
shares, downgrade compatible shares to read-only, and preserve manager and
other-app shares. Orphans use the supported delete API without target comments.
Narrow repairs invalidate cached DocShare objects.

Share saves lock the target first, then the actor and recipients in sorted
User-primary-key order. Role, assignment, bulk-clear, and repair paths pre-lock
the targets of affected shares in stable order before locking recipients, so a
compatible grant cannot form a target/User lock cycle with cleanup. Current
locking reads and persisted Has Role lookups prevent stale snapshots or caches
from restoring authorization. Assignment-recipient changes clear both
permission caches. A supported whitelist override preserves core bulk
clear-user-permissions validation, System Manager access and deleted-row count,
and repairs shares within the same request transaction.

Hooks never commit or roll back. Frappe rolls conflicts back; callers may retry
in a fresh request, where authorization is checked again. Administrative direct
DB writes must invoke invariant cleanup. No schema or response contract changes.
The domain graph was reviewed and the bulk-clear service flow documented.

## Verification evidence

- Risk classification: permission/lifecycle boundary and registered legacy repair.
- Required gates: targeted and complete permission/share modules, full server,
  pre-push-ui, fresh install, registered migration/reruns and concurrency.
- Commands executed: `bench --site test_site run-tests --app bond_management
  --module bond_management.bond_management.utils.test_investor_shares` and the
  corresponding `utils.test_investor_permissions` command;
  `scripts/verify.sh pre-push-ui`; `scripts/verify.sh pre-push`.
- Exit statuses: both modules and completed gates exited 0.
- Tests passed: 23 share tests, 16 permission tests, 346 full-suite server tests
  and 49 browser tests. Final current-tree `pre-push-ui` exited 0 again on 8 October.
- Fresh commands: new-site and install-app in an independent temporary bench;
  fresh-index assertions before migrate; representative legacy PDFs, schedules,
  FX data and incompatible shares; ordinary migrate running every registered
  patch; business/share assertions; forced full patch re-execution; normal
  skipped rerun. Completed checks exited 0. Unassigned shares were deleted and
  global shares retained as read-only. Migration helpers belong to the separate
  cleanup slice and ran only in the opted-in temporary database.
- Concurrent commands: separate `bench execute` calls to
  `bond_management.bond_management.tests.investor_share_concurrency.seed` and
  `.run`, with the exact disposable bench and observer login supplied privately
  through environment variables. Both exited 0. Actual User-primary-lock waits
  were observed. Assignment revocation denied the grant; role addition caused a
  framework conflict, then a fresh caller retry was denied. Both left zero
  conflicting shares. The opt-in test harness has narrow Semgrep transaction
  annotations and cannot run against the canonical bench.
- Preparation failures: one removal fixture needed permission-bypass flags to
  reach the app hook; Ruff reformatted a line; temporary migration fixtures
  needed File.update's dict argument, File.reload and the nine-place stored
  years value. Concurrency observation now handles MariaDB optimizer waits
  omitted from lock views using InnoDB's transaction/primary-lock evidence;
  its conflict path explicitly asserts fresh retry denial.
- Tests not run: Linux CI has not been executed locally.
- Blockers: none in the completed focused, UI, fresh, migration and race checks.
- Local/CI differences: macOS/MariaDB 12.3.2/socket administrator versus Linux
  CI. Independent fresh sites reuse the existing source/Python environment via
  symlinks. Initial install logged a nonfatal icon warning before asset links
  were configured. No existing site was recreated, restored or dropped.
- Local evidence: the earlier focused/fresh checks were observed on 7 October;
  their temporary logs were cleared during interruption. On 8 October,
  `fix3-final.log` records the repeated full UI gate, and
  `fix3-oct8-fresh.log` records a new disposable install, all 26 registered
  patches on legacy shares, forced and skipped reruns, index assertions, and
  both observed concurrency races. Persistent logs are kept outside the repo.
  Bootstrap recovery needed `config/pids`; the external check harness needed
  the sites working directory and direct module import. These failures were
  corrected; completed checks exited 0.

## PR #18 review follow-up: share locking and legacy-share bypass

The follow-up fixes the inversion between target and recipient locks, handles
compatible shares committed after cleanup's target discovery, and rejects
legacy DocShare grants before Frappe's share fallback can widen direct, list, or
report access. The domain graph was reviewed; no mapped relationships changed.

- Risk classification: permission boundary and transaction concurrency; app
  lifecycle hook coverage also changed.
- Required gates: focused share/permission modules, complete server suite,
  `pre-push-ui`, and a fresh MariaDB install because `hooks.py` changed.
- Commands and results: both focused modules passed (26 share tests and 17
  permission tests); `BASE_URL=http://localhost:8001 scripts/verify.sh
  pre-push-ui` passed, including 350 server tests, frontend lint/typecheck/build,
  and 49 Playwright tests. Browser credentials were one-run environment values
  and were not persisted.
- Fresh MariaDB install: `bench new-site --admin-password admin
  codex_pr18_fresh_20261009c` and `bench --site
  codex_pr18_fresh_20261009c install-app bond_management` both succeeded after
  entering the local root credential at the secure prompt. `list-apps` showed
  the app from `codex/enforce-investor-share-boundary`; `frappe.get_hooks` on
  the fresh site confirmed the updated mutation hook on the financial DocTypes.
  No existing site was recreated, dropped, or restored.
- Tests failed: the first UI-gate attempt targeted the default port's wrong
  site and both login setups failed. The documented explicit `test_site`
  server on port 8001 corrected this; the complete rerun passed.
- Tests not run: Linux CI.
- Blockers: none.
- Unverified local/CI differences: the fresh database used the existing local
  bench/Python environment on macOS with MariaDB, while CI uses a newly created
  Linux bench. The complete application/browser gates passed locally.

## PR #18 merge-conflict refresh against main

The existing PR branch was behind `main` at `3acdd5d`. The merge had one
content conflict in `utils/test_investor_permissions.py`; both the legacy-share
scope regression and the exchange-rate query-hook registration test are kept.
The domain graph was reviewed after the merge; its relationship and investor
data-flow notes include the latest `main` changes, and the conflict resolution
adds no further mapped relationship.

- Risk classification: permission boundary, lifecycle hooks, and Desk behavior
  from the merged base.
- Required gates: `pre-push`, `pre-push-ui`, and fresh-site install because the
  merged tree includes hook, permission, metadata, and Desk changes.
- Commands and results: `apps/bond_management/scripts/verify.sh pre-push`
  exited 0; the server suite ran 322 integration tests and 3
  unspecified-category tests. `apps/bond_management/scripts/verify.sh
  pre-push-ui` exited 0; 48 unit tests, 322 integration tests, 3
  unspecified-category tests, and 50 Playwright tests passed. Frontend lint,
  typecheck, build, pre-commit, and blocking Semgrep checks passed.
- Fresh install: a new `codex_pr18_fresh_20261009d` site was created and the
  app installed from this branch. `bench --site codex_pr18_fresh_20261009d
  list-apps` exited 0 and reported the app on
  `codex/enforce-investor-share-boundary`. Fresh-site `frappe.get_hooks` checks
  exited 0 and confirmed the share repair after-install hook and financial
  mutation hooks.
- Tests failed: the first pre-push attempt could not initialize Semgrep under
  the restricted cache/network environment; the required rerun with temporary
  Semgrep paths and network access passed.
- Tests not run: Linux CI.
- Blockers: none in local verification.
- Unverified local/CI differences: local macOS/MariaDB and browser environment
  versus the Linux CI runner.

## PR #18 review: stale target snapshot during share repair

When cleanup cannot take a nonblocking target lock, a regular fallback read can
use an older repeatable-read snapshot. Its missing-target result is not proof
that a DocShare is orphaned. Keep the share and enqueue a target-scoped repair
after commit so it retries in a fresh transaction. The regression inserts a
target and compatible share after cleanup's discovery read, simulates the lock
timeout and stale fallback, and verifies the share survives and a retry is
scheduled. The domain graph was reviewed; this repair changes no mapped
relationships or data flow.

- Risk classification: investor share integrity and transaction concurrency.
- Required gates: focused share module, full server suite, and `pre-push`.
- Commands and exit statuses: `bench --site test_site set-config allow_tests
  true` (0); `bench --site test_site migrate` (0); focused share module (0);
  `apps/bond_management/scripts/verify.sh pre-push` first stopped at Ruff
  formatting (1), then passed after formatting (0).
- Tests passed: 27 focused share tests; full gate ran 48 unit, 323 integration,
  and 3 unspecified-category tests; all passed. Pre-commit, blocking and
  advisory Semgrep scans, and Semgrep rule tests passed.
- Tests failed: none after formatting.
- Tests not run: UI and fresh-site gates were not applicable; Linux CI was not
  run locally.
- Blockers: none.
- Unverified local/CI differences: Linux CI remains unverified; this change
  affects server-side locking and cleanup only.

## PR #18 review: mutual manager share locks

Two managers can save different documents shared to each other at the same
time. The mutation hook previously locked only its actor before document-share
cleanup locked the recipient, allowing opposite User lock orders and a
deadlock. The hook now locks the document target, reads current share recipients,
and locks the actor and recipients together in sorted order. A focused test
checks the order for both save directions. This changes no DocType, mapped
relationship, or report/API flow; the domain graph was reviewed while merging
the latest interest-difference report documentation from `main`.

The merge preserves both the investor share boundary and interest-difference
notes in `docs/domain-model.md`, and both regression rows in
`docs/testing-matrix.md`.

## PR #18 review: deadlocks abort share cleanup

The unseen-target retry handles a lock timeout by queueing cleanup after the
transaction commits. A database deadlock rolls back the whole current
transaction, so it must propagate instead of being treated as a target-local
timeout. The handler now defers only `QueryTimeoutError`; the new regression
asserts that `QueryDeadlockError` aborts cleanup without queueing a partial
retry. The timeout and deadlock assertions share one integration test to avoid
extra user creation and Frappe's test-suite user-creation throttle. No mapped
relationship or report/API data flow changed; the domain graph was reviewed.

### Verification evidence

- Risk classification: backend concurrency and investor authorization.
- Required gates: focused regression, complete share module, and the shared
  server gate.
- Commands executed:
  `bench --site test_site run-tests --module bond_management.bond_management.utils.test_investor_shares --test test_target_lock_timeout_defers_and_deadlock_aborts_cleanup`
  (exit 0); `bench --site test_site run-tests --module bond_management.bond_management.utils.test_investor_shares`
  (exit 0); `apps/bond_management/scripts/verify.sh pre-push` (exit 0).
- Tests passed: focused regression (1), share module (28), full server suite.
- Tests failed: none.
- Tests not run: browser and fresh-install gates; this change touches only
  server-side exception handling and tests, with no hooks, schema, or indexes.
- Blockers: none.
- Unverified local/CI differences: local verification uses macOS and
  MariaDB 12.3.2; GitHub CI remains the Linux platform check.
