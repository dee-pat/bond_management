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
are ready for commit and push. CI results and review-thread replies/resolution
will be recorded on PR #61; resolve only after CI on the fixing commit is green.

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
