# Verified F1–F3 fixes

Starting revision: `8aa013b26ddadf8f61d874365624e6930114071e`, clean checkout.

Goal: close the bench policy gaps, verify every non-PR revision independently,
and reject GET at the overridden bulk permission-clear route.

Source recheck confirms all three findings. Frappe's default whitelist includes
GET, but normal GET requests roll database writes back in `sync_database`;
this finding does not establish durable GET deletion.

Contract: disclosure commands are blocked independently of site classification;
uninstall/remove-app operations require one temporary site. Configuration is
limited to boolean verification flags on the test site or temporary sites.
Administrator password recovery remains available only on those sites.
Existing migrate, install, run-tests and reviewed verify.sh setup remain usable.
CI and Linters supersede PR runs, while push and manual runs use unique run IDs.
Bulk clear is POST-only and retains the System Manager boundary and share repair.
No schema, financial convention, share consistency algorithm or stored-data change.
Rollback is a code revert; no data migration or recovery required.

Acceptance: regressions fail before fixes; guard matrix and generated Codex rules
agree with the core; dispatch tests prove GET rejection and unchanged rows,
authorized POST cleanup, and unauthorized POST denial. Verify both push branches,
PR supersession and manual-run independence for both workflows. Run lint,
targeted/module server tests and the full server gate. No UI change: the existing
Desk caller uses POST; no share locking/consistency change requiring race tests.
Review domain model and final diff. The initial implementation was handed off
without publication. The user subsequently authorized committing, pushing,
opening a PR and waiting for required CI, with no merge.

Progress: F1–F3 independently confirmed and fixed. Regression tests were added
before implementation. Final scoped diff inspected with the Frappe review and
security checklists; no additional actionable findings. No unrelated changes
were present initially or introduced. No disclosure/destructive bench command
was executed to reproduce F1. The original pure policy accepted all 14 reported
verb/persistent-site combinations; only policy functions received those argv.
`docs/domain-model.md` reviewed; mapped relationships and data flows are unchanged.

## Verification evidence

- Risk classification: agent security policy, CI scheduling, and HTTP mutation
  boundary. No schema, financial calculation, data migration or share-lock change.
- Required gates: affected permission module and `verify.sh pre-push-ui`
  (lint, server, frontend and full UI), plus generated-file consistency.
- Regression evidence: the original guard allowed `show-config`; the workflow
  contract test rejected the original concurrency expression; GET dispatch with
  the original decorator failed with `PermissionError not raised`. The latter
  ran only in a rolled-back integration-test transaction, proving dispatch,
  without claiming durable GET deletion.
- `bench --site bond-management-test.localhost run-tests --module
  bond_management.bond_management.utils.test_investor_shares`: exit 0,
  53 tests passed, including all three new dispatch regressions.
- `apps/bond_management/scripts/verify.sh lint`: final exit 0. Pre-commit,
  skills lock, Semgrep scans (zero findings), 2 rule tests, 4 Semgrep-helper
  tests, 25 guard tests (185 matrix cases, including 44 new bench cases),
  31 policy/config tests (including actual Codex execpolicy load/check),
  12 verification-helper tests and 1 workflow context-matrix test passed.
- `../../env/bin/pre-commit run --files scripts/test_workflow_concurrency.py`
  from the app root: exit 0; covers the new file omitted by tracked-file scans.
- First `apps/bond_management/scripts/verify.sh pre-push-ui`: exit 1 only at
  browser setup (`ECONNREFUSED 127.0.0.1:8001`, 2 setup failures, 58 not run).
  Its server suite passed 409 tests (51 unit, 348 integration, 10 uncategorized),
  and frontend lint, typecheck and build passed. Started the documented
  test-site server on port 8001, then reran `verify.sh ui` unchanged: exit 0,
  all 60 browser tests passed. Earlier missing Redis was also recovered before
  the successful baseline and module tests. Formatter-only lint failures were
  corrected by the repository hooks and rerun successfully.
- Final `apps/bond_management/scripts/verify.sh pre-push-ui`: exit 0. Lint,
  migration, all 409 server tests, frontend lint/typecheck/build, and all
  60 browser tests passed. The workflow matrix was then strengthened to
  evaluate context lookups/OR rather than assert a literal expression;
  `python3 scripts/test_workflow_concurrency.py` and explicit new-file
  pre-commit both exited 0. It also proves both original workflow expressions
  collide for repeated pushes, while both fixed expressions give independent
  groups. PR supersession, pushes and manual runs on both branches, and
  separation between workflows are covered.
- Final `git diff --check`: exit 0. Inspected all 15 tracked modified files
  plus the new workflow test and this note; no additional actionable findings.
- Initial handoff merge readiness: 4/5 (provisional), applying to the uncommitted snapshot
  on `codex/fix-verified-f1-f3` based at the starting revision above. Required
  remote CI remains outstanding; no commit, push, merge, settings change, or
  comment publication was performed.
- Tests not run: lifecycle/share-race (no schema, bootstrap, or consistency
  algorithm changes); fresh installation (no installation changes).
- Remaining verification: required remote CI on the final fixing revision.
- Unverified local/CI differences: local macOS uses the persistent test site;
  CI uses Ubuntu and a fresh bench/site with pinned Frappe. The concurrency
  expression is checked against PR, main/version-16 pushes, and manual context
  fixtures locally; actual GitHub scheduling still needs remote CI.

## Publication

Confirmed `origin` is `git@github.com:dee-pat/bond_management.git` and the base
is `main`. GitHub confirms the default branch and that the original sandbox
change was squash-merged in PR #70. Current `origin/main` is
`ce8e5113fe69ce50de98bf27af5c981a91c8de6b`, whose tree matches the reviewed
starting revision exactly. Reparent the scoped fix commit onto that base to
exclude the already-merged original commit from the new PR. Run the combined
gate on the final commit before pushing; report exact required CI results in
the PR and chat after they finish. No merge is authorized.
