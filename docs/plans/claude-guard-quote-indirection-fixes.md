# Claude guard: ANSI-C quoting and indirection (PR #61)

Codex's review of `ad5d61c` found two P1 bypasses. ANSI-C quoting retains an
extra dollar sign in scanner words, hiding programs, verbs and protected
filenames. Indirect parameter expansion can read a secret through a variable
whose name is not secret-named.

Fix: remove the ANSI-C quote introducer and preserve literal contents when
there are no escapes, including empty quoted fragments in a word. Fail closed
on escaped ANSI-C strings instead of implementing Bash's entire escape
language. Block locale-dependent quoted words too: their translated value
cannot be known statically, and their dollar introducer has the same bypass.
Conservatively reject every real indirect expansion before removing
assignments or redirection targets. Single-quoted and escaped references remain
literal. Keep the standard-library scanner, existing hook payload/exit-status
contract, temporary-site rules and private-file/source rules.

Acceptance: quoted command/verb/site/file bypasses and indirect credential
references are blocked; literal references, non-secret assignments, ordinary
ANSI-C literals and valid temporary-site reinstalls remain allowed. Update the
verification paragraph and cover each finding with failing-first regressions.
No dependencies, schema or application behavior changes; recovery is a code
revert. `docs/domain-model.md` reviewed; no mapped relationships or flows change.

Progress: regressions reproduced both findings (14 initial failures), plus
two analogous locale-quote bypasses. The quote and indirection checks and
verification paragraph are updated. All 18 guard tests now pass. The first
pre-push attempt applied Ruff formatting, so the complete gate must be rerun.
Next: run the bench-root pre-push gate on the final snapshot, inspect the scoped diff,
then commit/push and reply on both threads. Resolve only after CI passes on
the fixing commit; record final verification evidence in those replies.

Local verification evidence:

- Risk: local safety-hook correctness and secret protection.
- Required gates: guard suite and `verify.sh pre-push` (lint and server);
  all CI checks on the fixing commit before resolving threads.
- Commands: app-root `python3 scripts/test_claude_guard.py`; bench-root
  `apps/bond_management/scripts/verify.sh pre-push` before commit/push.
- Exit statuses: initial regression proof 1; fixed guard suite 0; first
  pre-push attempt 1 because Ruff reformatted a changed file. The final
  pre-push result will be recorded on the PR before resolving threads.
- Tests passed/failed: 18 guard tests passed; expected regression failures
  were observed before the fixes, with none remaining.
- Tests not run locally: frontend, UI and opt-in suites; no application
  runtime, permissions, schema, install-hook or browser changes.
- Blockers: none.
- Local/CI differences: macOS locally versus Linux CI, which also runs UI and
  opt-in suites. Final results will be recorded on PR #61.
