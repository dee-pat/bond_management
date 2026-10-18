# PR #59 F1: current attachment discovery

Status: completed and archived. [PR #59](https://github.com/dee-pat/bond_management/pull/59)
merged into `main` on 2026-10-17 at 05:08:05 UTC as
`04c03af5eb381e0deac2a1a3e57d14c3cc0829ff`. This note records that completed
work; it grants no current authorization to commit, push, merge or publish.

Review scope: `f78049317e44cf8df4a8dfa5e1813d32e82e4e07` to
`8b9700f636ff25a0d89cc901e88b9b6fcffda512`, followed by integration onto
`1cfd8a46d1c098cd52c8e9272cd84fdff158c395` and the F1 fix included in the merge.

A transaction mover can establish a repeatable-read snapshot before another
connection commits a private attachment and compatible File share. Snapshot-based
attachment discovery then skips that File when the transaction changes portfolio,
leaving a stale share that blocks the investor's File list.

Acceptance: discover committed attachments and shares with current reads, remove
the incompatible grant, and keep the investor's permission-scoped File list usable.
Acquiring File or DocShare locks before User locks must never introduce a waiting
lock-order inversion: contention retries the whole original scope after commit.
Existing private-file, permission and financial conventions remain unchanged;
there is no schema or public API change.

Regression: use two real connections, commit owned fixtures, establish the mover's
snapshot, commit a new private attachment and compatible share on the other
connection, save the portfolio move, and check share removal and investor listing
in a fresh transaction. Clean up committed fixtures even on failure. Also cover
busy discovery and recipient locks and the deferred scope retry.

Domain-model review: the existing File attachment relationships are unchanged;
document the current discovery and deferred cleanup behavior alongside share scope.

Progress: F1 reproduced against the pinned head (regression exit 1), then fixed.
Current attachment and recipient discovery use nonwaiting locks. The real
regression also exposed core `delete_doc`'s snapshot-based existence check
(`frappe/model/delete_doc.py:109`): it can return False for a share the locking
query found. That result now schedules normal API deletion after commit. The
regression uses real enqueue/after_commit behavior and executes the captured job
on the other connection; only external queue transport is substituted.

MariaDB 12.3 strict snapshots reject newly committed rows with error 1020, mapped
to QueryDeadlockError by installed Frappe. The strict regression verifies rollback
and a fresh retry, preserving transaction-conflict semantics. Both the isolation
level and strict-snapshot setting are restored after the test. See MariaDB's
[consistent snapshot documentation](https://mariadb.com/docs/server/ha-and-performance/standard-replication/enhancements-for-start-transaction-with-consistent-snapshot).

## Verified outcome

On 2026-10-18, GitHub PR metadata confirmed the merged state, merge commit above,
and final PR head `858ce9987c99278e39f204cda92ef6ed463b7093`. All reported checks
on that head succeeded: [Server and UI](https://github.com/dee-pat/bond_management/actions/runs/39003958810),
[Frappe Linter and Vulnerable Dependency Check](https://github.com/dee-pat/bond_management/actions/runs/39003958968),
and Greptile Review. These are final PR-head results, not checks on today's
working tree or separate runs on the squash commit.

Local history independently confirms that the squash merge includes the
snapshot-based attachment discovery fix and its two-connection regression, and
that it is an ancestor of the whole-repository review revision
`4621566aba99b84a1f90d8b638d9c53ddc798309`. The integration retained the shared
`_lock_shares` helper, financial cleanup retry and contention coverage.
Domain-model behavior and the testing matrix were updated; the attachment
discovery fix added no schema, patch or hook registration.

## Historical local verification

The following results were recorded during the original integration; they were
not rerun for the documentation correction:

- Two-connection attachment module: exit 0, 2 tests; the original unfixed-head
  regression had exited 1 with a stale share.
- Complete share module: exit 0, 50 tests, including financial-share contention.
- Scoped pre-commit and range Semgrep: exit 0, no new findings.
- `BASE_URL=http://localhost:8001 apps/bond_management/scripts/verify.sh pre-push-ui`
  from the bench: exit 0; lint, server (345 integration tests plus groups of 51
  and 10 unit tests), frontend lint/typecheck/build and all 60 authenticated
  Playwright tests passed.

The opt-in disposable-site assignment/role observer races were not run locally:
private observer/administrative credentials were unavailable. The two-connection
regression substitutes external queue transport while exercising real
`after_commit` registration and retry execution. Local macOS/MariaDB 12.3 and CI
Linux/MariaDB 11.8 remain different environments. These are historical coverage
limits, not pending commit, push or CI work for PR #59.
