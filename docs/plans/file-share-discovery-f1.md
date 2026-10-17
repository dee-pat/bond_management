# PR #59 F1: current attachment discovery

Review scope: `f78049317e44cf8df4a8dfa5e1813d32e82e4e07` to
`8b9700f636ff25a0d89cc901e88b9b6fcffda512`, followed by integration onto
`1cfd8a46d1c098cd52c8e9272cd84fdff158c395`, plus the uncommitted F1 fix.

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

Independent concurrency review found no remaining actionable defect. Existing
permission and financial conventions are unchanged. Domain-model behavior and
the testing matrix were updated; no schema, patch or hook registration changed.
Required verification: regression red/green, complete affected modules, lint,
full server, frontend/build and authenticated UI gates (permission change),
range Semgrep, and exact-revision remote CI inspection. Final local edits cannot
have CI evidence until the user authorizes committing and pushing them.


## Verification evidence

- Risk classification: permission/share cleanup concurrency.
- Commands executed and observed statuses:
  - Unfixed-head two-connection regression: exit 1 (stale share remains).
  - `bench --site bond-management-test.localhost run-tests --module bond_management.bond_management.utils.test_investor_attachment_concurrency`: exit 0, 2 tests.
  - `bench --site bond-management-test.localhost run-tests --module bond_management.bond_management.utils.test_investor_shares`: exit 0, 49 tests.
  - `scripts/semgrep-pr.sh f78049317e44cf8df4a8dfa5e1813d32e82e4e07 8b9700f636ff25a0d89cc901e88b9b6fcffda512`: exit 0, no new findings.
  - `BASE_URL=http://localhost:8001 apps/bond_management/scripts/verify.sh pre-push-ui` from the bench, using existing private browser credentials: exit 0, lint/server/frontend/build/UI; 344 integration tests, 60 Playwright tests. Additional server unit groups passed (51 and 10 tests).
  - Scoped pre-commit including new untracked files: exit 0.
- Final follow-up: `apps/bond_management/scripts/verify.sh pre-push` exited 0 after the test-only session-setting restoration and explicit harness-commit Semgrep annotations: lint/Semgrep/rule tests and all server groups passed (344 integration tests, plus 51 and 10 unit tests). No remaining actionable finding in the inspected local snapshot; merge readiness 4/5 provisional because exact-diff CI and the opt-in observer harness remain unavailable. No fix prompt needed.
- Failed attempts recovered: sandbox blocked bench log writes and Semgrep trust-store access; authorized host execution worked. Redis cache/queue were stopped and were started from this bench's configured Redis files. An initial diagnostic test run hit strict-snapshot error 1020; coverage now explicitly tests both modes. No assertions were weakened.
- Tests not run: opt-in disposable-site `tests/investor_share_concurrency.py` assignment/role races. Its private observer/administrative credentials are unavailable; local root socket access returned MariaDB 1045. The requested attachment race is covered by the normal two-connection suite above.
- Fresh install: no local schema, patches, hooks or install changes; new local fresh-site bootstrap not applicable to this fix. Original pinned head's clean-install Server/UI CI passed.
- Blockers: exact local diff has no remote CI until committing/pushing is authorized; no commit, push, merge, PR posting or review-thread resolution performed.
- Unverified local/CI differences: macOS/MariaDB 12.3 locally versus Linux/MariaDB 11.8 CI; external queue transport is substituted in the regression, while after_commit registration and retry callable execution are real. Opt-in lock-observer races remain unrun.
- Remote drift: PR #59 advanced during work to `1cfd8a46d1c098cd52c8e9272cd84fdff158c395` (financial-share lock cleanup from #60). That revision overlaps the same utility/tests and renames `_lock_file_shares` to `_lock_shares`; the first review retained the requested pinned head. The follow-up integration below supersedes that earlier limitation.

Final published CI inspection: all required checks passed at remote head
`1cfd8a46d1c098cd52c8e9272cd84fdff158c395`: [Server and UI](https://github.com/dee-pat/bond_management/actions/runs/39003283342), [Frappe Linter and Vulnerable Dependency Check](https://github.com/dee-pat/bond_management/actions/runs/39003283382). These checks do not cover the uncommitted F1 fix.


## Integration onto PR head 1cfd8a4

The user authorized integration onto `1cfd8a46d1c098cd52c8e9272cd84fdff158c395`
without committing, pushing or merging. The pre-integration local snapshot was
saved outside the repository before changing its Git baseline. The dedicated
branch `codex/pr59-f1-integration` now points at that existing commit, with F1
changes unstaged and new files untracked.

The utility uses the latest head's shared `_lock_shares` helper. Its financial
cleanup retry and `busy_share_rows` tests are retained alongside the F1 discovery
and retry coverage. The only textual conflict was adjacent testing-matrix rows;
both sets of tests remain indexed. Domain-model review confirms the existing
relationships and conventions are unchanged; the F1 behavior documentation stays
applicable.

Required reruns: two-connection regression and complete share module, full
`pre-push-ui` gate (lint/server/frontend/build/authenticated UI), and scoped
pre-commit including new files. Published-head CI is green but does not cover the
uncommitted integration. The prior opt-in observer credential limitation remains.
Progress: integrated content and independent concurrency review found no lost
upstream changes or new lock-order defect. The financial retry retains its whole
scope (including the deferred attachment pass); both File and financial callers
use `_lock_shares`. Both original contention tests remain effective.

Integrated verification evidence:
- Targeted two-connection module: exit 0, 2 tests.
- Complete share module: exit 0, 50 tests, including the latest head's financial-share contention regression.
- Scoped pre-commit (including untracked tests/docs): exit 0.
- `scripts/semgrep-pr.sh f78049317e44cf8df4a8dfa5e1813d32e82e4e07 1cfd8a46d1c098cd52c8e9272cd84fdff158c395`: exit 0, no new findings.
- `BASE_URL=http://localhost:8001 apps/bond_management/scripts/verify.sh pre-push-ui` from the bench, with existing private credentials: exit 0. Lint/Semgrep/rule tests, all server groups (345 integration tests plus 51 and 10 unit tests), frontend lint/typecheck/build, and all 60 authenticated Playwright tests passed. No tests failed in the integration reruns. The temporary test web server was stopped after verification.
- No extra commits exist above the requested base; the index is empty and all local edits remain unstaged/untracked.
- No new schema, hooks or installation change, so another local fresh-site bootstrap is not required. Published CI already confirms clean installation of the integration base.
- Remaining verification: exact uncommitted integration cannot have remote CI; opt-in observer races remain blocked by unavailable private credentials, as recorded above.


## Authorized commit and push

The user authorized committing this integrated snapshot and pushing it to PR #59,
without merging. Confirmed destination: `origin` at
`git@github.com:dee-pat/bond_management.git`, PR branch
`fix/codex-review-file-scope-withholding-coupon-day`, base `main` at
`f78049317e44cf8df4a8dfa5e1813d32e82e4e07`. Published branch head is still
`1cfd8a46d1c098cd52c8e9272cd84fdff158c395`. The final integrated local gates
above passed before staging; no implementation changed afterward. Push will use
an explicit destination ref without force. Exact pushed-revision CI is pending
and will be reported after it finishes. The opt-in observer credential limitation
remains; it does not invalidate the passing attachment regression.
