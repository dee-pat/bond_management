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
4. Done (merged in #65 as `54c3011`): rollout step 1. See _Step 1_ below.
5. Done (uncommitted, branch `claude/affectionate-franklin-509d8d`, base
   `54c3011`): rollout step 2. See _Step 2_ below.
6. Next: rollout step 3 (Claude `Read` deny rules, then the sandbox tracer).

## Step 2: verify.sh owns credentials and site checks

- `verify.sh ui|playwright|pre-push-ui` call `prepare_browser_credentials`,
  which pauses xtrace, runs `load_browser_credentials` and then the existing
  required-variable checks. The loader sources
  `$HOME/.config/bond_management/test-browser.env` only when one of the four
  `FRAPPE_*` variables is unset and the file exists, with `set -a`, errexit
  and nounset paused and the file's stdout/stderr discarded; values the caller
  already set are restored afterwards, so they win. A non-zero status from the
  file fails closed with a message that names only the path. The CI UI job
  exports all four, so it never reads a file.
- Extra arguments after `ui`/`playwright` go to `yarn test:e2e`, so the single
  spec flow in `e2e/AGENTS.md` runs through the gate instead of sourcing.
- `agent_policy.py` gained `main(argv)`: run as a script
  (`python3 -I bond_management/agent_policy.py SITE`) it exits 0 only for
  exactly one temporary site and prints a fixed message otherwise.
  `verify.sh`'s `require_temporary_site` calls it in `create_temporary_site`
  (before `bench new-site`) and `drop_temporary_site` (before
  `bench drop-site`).
- Hook: `CREDENTIAL_FILE`, `HOME_CREDENTIAL_PATHS` and `credential_source` are
  gone. Every variable expansion is now unsupported, every `source`/`.` is
  blocked, and a protected basename is blocked in every command. Matrix:
  `source-home`, `source-braced-home`, `source-literal` now expect a block;
  new `source-set-a`, `source-literal-dot` (blocked) and `verify-ui` (allowed);
  `set-setup`, `xtrace` and the two nameref cases no longer mix in a source.
- Docs: `verification.md` (credentials, temporary-site check, hook summary),
  `e2e/AGENTS.md` (single spec via `verify.sh ui`), `claude-guard-shell-policy.md`
  (sourcing row, compatibility note), the safety spec's status and
  inventory row, `testing-matrix.md`. Historical plan notes are left as written.
- Bash 3.2 (macOS `/usr/bin/env bash`) exits inside a sourced file on a failing
  command even under `if !`, so the loader turns errexit off around the
  `source` and checks its status explicitly.
- `docs/domain-model.md` reviewed: no DocType, link, attachment or data-flow
  change.

## Step 1: policy core (no behaviour change)

- `bond_management/agent_policy.py` (stdlib only: `re`, `pathlib`) holds
  `PERSISTENT_SITES`, `TEMPORARY_SITE_SUFFIX`/`TEMPORARY_SITE`,
  `DESTRUCTIVE_VERBS`, `POSITIONAL_SITE_VERBS`, `PROTECTED_FILES`,
  `SECRET_NAME`, `SECRET_ENV_VARS` (the `BOND_SHARE_LOCK_*` names listed
  explicitly), `classify_site(name)` and `destructive_site_violation(argv)`.
  Sets are now `frozenset`s.
- `scripts/claude_guard.py` loads the core by file path (`load_policy`, no
  package init) and takes `PROTECTED_FILES`, `SECRET_NAME` and
  `destructive_violation` from it; its own `destructive_violation` and
  `site_argument` moved into the core unchanged apart from going through
  `classify_site`. `claude_guard_shell.py`, the stdin/exit-code contract, the
  diagnostic and file names are unchanged.
- `temporary_site_guard.py` imports `PERSISTENT_SITES` and
  `TEMPORARY_SITE_SUFFIX` from `bond_management.agent_policy`.
- `scripts/test_agent_policy.py` runs in `verify.sh lint` after the guard
  suite; `opt-in.yml` also triggers on `bond_management/agent_policy.py`;
  `testing-matrix.md` points to the new suite.
- Equivalence: the old `destructive_violation` (from the `main` checkout) and
  `destructive_site_violation` returned the same result for all 1,118,480
  argv lists of length 1–5 over 16 tokens (bench spellings, every verb class,
  `--site` forms, persistent, temporary, 31-hex and empty sites, `--force`).
- Left as is: a missing or broken core file makes the hook exit 1 (an
  import error), the same as a missing `claude_guard_shell.py` today; Claude
  Code treats exit 1 as non-blocking. Making load failures exit 2 changes the
  hook contract, so it is a follow-up, not part of step 1.

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

## Verification evidence (step 2)

- Risk classification: verification tooling and agent hook; no application,
  schema, permission or financial-rule change. Browser credentials are handled
  by a project script, so the UI gate was also run.
- Required gates: `verify.sh pre-push` (lint + server), plus `verify.sh ui`.
- Commands executed:
  - `verify.sh lint` from this worktree with the bench `env/bin` on `PATH` and
    `scripts/test_verify_helpers.py` marked intent-to-add. Exit 0 on the second
    run; the first run's ruff-format reformatted the new test file.
  - `PYTHONPATH=<worktree> apps/bond_management/scripts/verify.sh server`
    (the main checkout's script, importing `bond_management` from this
    worktree, as in step 1). Exit 0.
  - UI: `bench --site bond-management-test.localhost serve --port 8001
    --noreload` in the background, then a scratch driver that unsets the four
    `FRAPPE_*` variables, sources this worktree's `verify.sh`, points
    `BENCH_ROOT` at the bench and calls `run_playwright_tests` with
    `BASE_URL=http://localhost:8001` and `PYTHONPATH=<worktree>`. Exit 0. With
    nothing exported, the investor and Desk logins could only succeed if the
    loader read the local file.
- Tests passed: pre-commit, skills.lock check, Semgrep and rule tests, guard
  suite (24), `test_agent_policy.py` (13), `test_verify_helpers.py` (12),
  server suite (345 + 51 + 10), Playwright (60).
- Mutation check: removing the loader's output redirect, or its xtrace pause,
  makes the no-echo tests fail.
- Tests failed: none.
- Tests not run: frontend gate (no client change); opt-in `lifecycle` and
  `share-race` (they create real temporary sites; the _Opt-in suites_
  workflow runs them on the PR because `verify.sh` and `agent_policy.py`
  change). The stubbed-bench tests cover the new site check.
- Blockers: none.
- Unverified local/CI differences: CI has not run; CI Linux bash 5 runs the
  helper tests that were checked here on macOS bash 3.2.

## Verification evidence (step 1)

- Risk classification: agent tooling and test-helper refactor, no behaviour
  change; no application, schema, permission or financial-rule change.
- Required gates: `verify.sh pre-push` (lint + server).
- Commands executed, from the bench root:
  - `PATH=<bench>/env/bin:... apps/bond_management/.claude/worktrees/optimistic-booth-775d4e/scripts/verify.sh lint`.
    From a worktree the script's `BENCH_ROOT` resolves to `.claude/`, so the
    bench `env/bin` goes on `PATH`. The new files were marked intent-to-add so
    pre-commit and Semgrep (git-tracked files only) cover them.
  - `PYTHONPATH=<worktree> apps/bond_management/scripts/verify.sh server`: the
    main checkout's script migrates `bond-management-test.localhost` and runs
    the full suite, with `PYTHONPATH` making `bond_management` import from this
    worktree (checked: `bond_management.agent_policy.__file__` and
    `temporary_site_guard.__file__` resolve to the worktree).
- Exit statuses: lint 0 (after one run where ruff-format reformatted
  `scripts/test_agent_policy.py`); server 0.
- Tests passed: pre-commit, skills.lock check, Semgrep and rule tests, guard
  suite (24), `test_agent_policy.py` (12), server suite (345 + 51 + 10),
  including `TestMigrationLifecycleGuard`.
- Tests failed: none.
- Tests not run: frontend and UI gates (no client change); opt-in `lifecycle`
  and `share-race` (they create temporary sites; the _Opt-in suites_ workflow
  runs them on the PR because it touches `temporary_site_guard.py`).
- Blockers: none.
- Unverified local/CI differences: CI has not run on this change.
- `docs/domain-model.md` reviewed: no DocType, link, attachment or data-flow
  change.

## Verification evidence (spec)

- Risk classification: documentation only.
- Required gates: bench-root `apps/bond_management/scripts/verify.sh lint`.
- Commands executed: bench-root `verify.sh lint` from this worktree, with the
  bench `env/bin` on `PATH` (the worktree's `BENCH_ROOT` fallback does not
  reach the bench). Exit 0: pre-commit, skills.lock check, Semgrep with rule
  tests, and the guard suite all passed.
- Tests not run: server, frontend and UI gates (no code changes).
- `docs/domain-model.md` reviewed: no change.
