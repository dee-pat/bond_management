# Bounded Claude guard hardening, PR #61

Goal, non-goals, supported syntax, compatibility, recovery and acceptance:
[shell policy](../specs/claude-guard-shell-policy.md).

Baseline: `d9d52a0`, branch `ci/review-recommendations`, base `main`. Working
tree clean. No unresolved review threads at the start; the prior unrestricted
review is still running. Keep the scanner and standard library only.

Progress:

1. Policy/spec written before implementation. Initial CLI matrix reproduced
   54 failures against the old policy. Scanner/policy/exit tracer slice passed.
2. Replaced heuristic expansion/wrapper handling with explicit tokens and the
   bounded grammar. Preserved every blocked historical regression; changed
   formerly allowed unsupported forms to reject under the approved policy.
   Added word-start comments after the prior review completed. Its three P1s
   (expanded command/verb, duplicate site selectors, namerefs) and comment P3
   are covered by exact matrix examples, each proved against the old CLI.
   Literal-provenance cases also reject globs in bench arguments, assignment
   values and wrapper operands. Assignment provenance distinguishes a raw
   `NAME=` prefix from quoted data; executable names containing `=` and
   post-wrapper assignments are rejected rather than guessed. No new review
   has been requested yet.
3. Handoff protocol: run the complete matrix and pre-push gate; inspect the
   scoped diff, commit/push, wait for CI, reconcile the four prior review
   threads and request one final design review against the contract. Final
   gate/CI/review results and completion state are recorded on
   [PR #61](https://github.com/dee-pat/bond_management/pull/61), keyed to the
   published commit rather than adding evidence-only commits after CI.

Verification evidence (in progress):

- Risk: static safety-hook correctness and secret protection.
- Required: matrix/guard suite, bench-root `verify.sh pre-push`, final CI and
  one design review. No application/UI/schema changes; local frontend, UI and
  opt-in gates are not needed for this slice.
- Commands/statuses: initial `python3 scripts/test_claude_guard_matrix.py`
  exited 1 with 54 failed cases; fixed matrix and combined
  `python3 scripts/test_claude_guard.py` now pass all 22 methods, including
  120 quote/wrapper/site combinations and all seven destructive verbs against
  temporary, persistent and foreign sites. Provenance additions failed before
  their policy checks were added (3 cases), then passed. First lint run exited
  1 for Ruff formatting and four precedence-parentheses rules, now corrected.
  Further assignment-role cases reproduced four failures before their fix.
  The final suite passes all 23 methods, including the token/descriptor
  provenance check: 126 table rows, 120 quote/wrapper/site combinations,
  28 destructive-verb/site boundaries and nine invalid/resource-bound payloads.
  Ruff formatting was applied through the existing bench pre-commit runtime.
  Final gate and CI evidence will be recorded on the PR before handoff.
- Blockers: none.
- Differences: local macOS versus Linux CI; CI also exercises clean install,
  UI and opt-in suites. Domain model reviewed; no mapped changes.
