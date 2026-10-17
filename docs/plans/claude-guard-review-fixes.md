# Claude guard review fixes (PR #61)

Goal: close the two P1 Codex findings on `5c543cd` while retaining the
standard-library scanner and existing temporary-site and literal-quote rules.

The guard currently loses wrapper context when an option precedes the actual
program, and checks secret references only for two output programs. Recognise
each `bench` and `printenv` basename anywhere in a segment; use only words
after each `bench` for its verb and site. Check `env` behind wrapper commands
and their options. Reject real secret-variable expansions in every scanned
word, including assignments and redirection targets, before filtering words.
Single-quoted and escaped references remain literal.

Acceptance: the requested wrapped commands and here-string secret expansions
are blocked; literal secret references, non-secret assignments, temporary-site
reinstalls and Git restores remain allowed. No dependencies, scanner rewrite,
financial behavior or stored data changes are needed. Existing hook exit
statuses and payloads remain compatible. Recovery is a normal code revert.

Progress: regression cases added first and reproduced both findings (22
failures on the old guard). The checks and verification paragraph are updated;
the full lint gate passed, including the final guard regressions. Local fixes
were committed and pushed as `c481cc4`. All six CI checks passed and both
threads were replied to and resolved. A subsequent Codex review found the
brace-expanded protected-path bypass below.

Domain-model review: `docs/domain-model.md` reviewed; no mapped relationship,
attachment, derived data or application API/service flow changes.

Local verification evidence:

- Risk classification: local safety-hook correctness and secret protection.
- Required gates: guard regression suite and `verify.sh lint`; remote CI on
  the fixing commit before thread resolution.
- Commands executed: `python3 scripts/test_claude_guard.py` from the app root;
  `apps/bond_management/scripts/verify.sh lint` from the bench root.
- Exit statuses: regression proof 1 on the old guard; guard suite 0 after the
  fix; full lint gate 0. Earlier lint attempts exited 1 for Ruff autoformatting
  and sandbox certificate-store access; rerunning with system access passed.
- Tests passed: all 15 guard tests, four Semgrep harness tests and two rule
  tests in the full lint gate. Pre-commit and skills-lock checks passed;
  blocking and advisory Semgrep scans reported no findings.
- Tests failed: 22 expected regression failures on the old guard; none in the
  first fixed guard run.
- Tests not run: server, frontend, UI and lifecycle locally; no application
  runtime, schema, permissions, hooks or browser behavior changes.
- Blockers: none.
- Unverified local/CI differences: remote CI runs the broader application
  suites; local verification covers the standard-library hook and lint.

## Follow-up: brace-expanded protected paths

Codex's review of `c481cc4` found one P1: the scanner retains brace patterns,
but protected-file matching treats braces literally, so Bash can expand an
allowed word into a protected filename. Conservatively replace comma/range
brace groups with wildcard patterns before checking protected basenames;
check nested groups and groups containing path separators without enumerating
their expansions. Mixed brace/bracket globs fail closed because alternatives
can change character-class boundaries. Parameter references such as `${PUBLIC_PATH}` must retain
their existing behavior. Keep the scanner, standard library and source-only
credential exception, and continue allowing unrelated brace paths.

Progress: regression cases reproduced the finding (10 initial failures).
The pattern check and guard paragraph are updated; further regression cases
also proved and closed nested-literal-brace, basename-changing-slash and
brace/bracket-glob gaps. All 16 guard tests and the final pre-push gate passed.
Committed and pushed as `ad5d61c`; all six CI checks passed, and the new thread
was replied to and resolved. The next review's ANSI-C quote and indirect
expansion fixes are tracked in `claude-guard-quote-indirection-fixes.md`.

Local verification evidence for this follow-up:

- Risk classification: local safety-hook correctness and secret protection.
- Required gates: guard suite and bench-root `verify.sh pre-push` (lint and
  full server suite); CI on the fixing commit before resolving the thread.
- Commands executed: `python3 scripts/test_claude_guard.py` from the app root;
  `apps/bond_management/scripts/verify.sh pre-push` from the bench root.
- Exit statuses: initial regression proof 1; final guard suite 0; final
  pre-push gate 0. CI and thread-resolution evidence is recorded on PR #61.
- Tests passed: 16 guard tests, four Semgrep harness tests, two rule tests;
  all server test categories passed (including 345 integration tests and
  10 unspecified-category tests). Pre-commit and skills-lock checks passed;
  blocking and advisory Semgrep scans had no findings.
- Tests failed: expected regression failures before the fix; none remain.
- Tests not run locally: frontend, UI, lifecycle and share-race; no changes
  to application runtime, schemas, permissions, install hooks or UI behavior.
- Blockers: none.
- Unverified local/CI differences: macOS locally versus Linux in CI; remote
  CI also runs UI and opt-in suites. Final CI evidence will be in the PR thread.

No application data, API, schema or relationship changes; the domain-model
review above still applies. No dependencies or migrations; recovery is a normal
code revert.
