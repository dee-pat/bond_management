# Agent-neutral safety policy, progress

Design, contract and acceptance: [agent-safety-policy.md](../specs/agent-safety-policy.md).

Baseline: `35a42cf` on `main`, branch `claude/agent-guard-spec-4b22e7`. Working
tree clean at start. Spec and this note only; no code or config changes.

## Status

1. Done: inventory of `scripts/claude_guard.py` and `claude_guard_shell.py`,
   sorted into script, hook, sandbox and instruction layers.
2. Done: capabilities checked against Claude Code 2.1.296 and Codex CLI
   0.163.0 help output and the official docs cited in the spec. Unverified items
   are listed there.
3. Done: design proposed. On 2026-10-17 the user chose the recommended option
   for all five open decisions; they are recorded below and in the spec's
   _Decisions_ section.
4. Next: rollout step 1 (core module and shared constants), on its own branch
   and PR once the user approves committing this spec.

While writing this, the current hook blocked two of the session's own
read-only commands (`git grep --include=*` matched a bare `*`; `~` tilde
expansion). That is the hook working as specified, and an example of why it
should not be the main control.

## Decisions (user, 2026-10-17)

1. **Bench boundary:** `bench` and `scripts/verify.sh` run outside the agent
   sandbox. The gap that `bench execute`/`console` or an edited `verify.sh` can
   still read config is accepted; it stays instruction-only plus review.
2. **Codex config:** commit `.codex/rules/` and `.codex/hooks.json`; document
   the permission profile and environment filter as a user-level snippet if a
   project file cannot carry them.
3. **Claude rollout:** staged. `Read(...)` deny rules first; enable the
   sandbox (`allowUnsandboxedCommands: false`, `failIfUnavailable`) only after a
   tracer run of `verify.sh lint` inside it succeeds.
4. **Credentials:** `verify.sh ui` loads `test-browser.env` itself when the
   variables are unset; then retire the hook's `source` exception.
5. **Names:** keep the `claude_guard*` names; only the new core gets the
   neutral name.

No open decisions remain. The unverified tool behaviours listed in the spec
are checked during the matching rollout step.

## Verification evidence

- Risk classification: documentation only.
- Required gates: bench-root `apps/bond_management/scripts/verify.sh lint`.
- Commands executed: bench-root `verify.sh lint` from this worktree, with the
  bench `env/bin` on `PATH` (the worktree's `BENCH_ROOT` fallback does not
  reach the bench). Exit 0: pre-commit, skills.lock check, Semgrep with rule
  tests, and the guard suite all passed.
- Tests not run: server, frontend and UI gates (no code changes).
- `docs/domain-model.md` reviewed: no change.
