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
6. Done (uncommitted, branch `claude/quirky-herschel-3556b4`, base
   `1a9f369`): rollout step 3 `Read` deny rules and the sandbox tracer. See
   _Step 3_ below. The sandbox block is not committed.
7. Done (uncommitted, branch `claude/ecstatic-babbage-a92288`, base
   `14d8b3d`): rollout step 4, the Codex project layer. See _Step 4_ below.
8. Open: the user decides on enabling the Claude sandbox (see
   _Recommendation_). The live Codex check below verified the hook and
   environment filter, and the user confirmed the persistent-site exec-policy
   decision outside any agent.

## Live Codex check — 2026-10-17

Codex CLI `0.163.0`, macOS, baseline `dbc02cdf2418ed622b1ca18bdcafc344d3c0f1bc`
on `main` in `dee-pat/bond_management`; initially clean. Results recorded on
`codex/live-safety-check-2026-10-17`. Read `AGENTS.md`, `docs/verification.md`
and `docs/agents/codex-user-config.md` first. No protected-file contents were
read, printed or copied, and neither bench help probe reached execution.

| Check | Expected | Observed | Layer |
| --- | --- | --- | --- |
| Rules: dev reinstall | `forbidden` | In Codex: check command refused by the hook. Run by the user in a plain terminal: `forbidden` (see below) | Hook; rule checker |
| Rules: test drop-site | `forbidden` | In Codex: check command refused by the hook; not rerun outside Codex | Hook |
| Rules: lifecycle temporary-site reinstall | Not forbidden | Exit 0, `{"matchedRules":[]}` | Rule checker |
| Live canonical dev reinstall, `--help` | Refused before execution | Refused before execution | Hook |
| Live `--site=...` dev reinstall, `--help` | Hook refusal | Refused before execution | Hook |
| `cat /nonexistent-dir/site_config.json` | Protected-file refusal | Refused before execution; no missing-file error | Hook |
| `FAKE_PASSWORD` membership only | `False` | Exit 0, `False` | Environment filter |
| `git status` | Allowed | Exit 0, clean `main` | Allowed control |
| Optional dev config `grep -c x` | Sandbox denial, if user profile added | Not run: supplied session profile has no protected-file deny entries | Sandbox unverified |

Exact tool refusal for both rule checks and both bench help probes (followed
by the tool's command echo):

```text
Command blocked by PreToolUse hook: Blocked by scripts/claude_guard.py: Never destroy or overwrite the persistent Bond Management sites. See docs/verification.md..
```

Exact protected-file refusal (followed by the tool's command echo):

```text
Command blocked by PreToolUse hook: Blocked by scripts/claude_guard.py: Protected credential/configuration file. See docs/verification.md..
```

Rule decision confirmed by the user in a plain terminal, outside any agent (so
no hook applied), on the same day:

```text
$ codex execpolicy check --rules .codex/rules/bond_management.rules bench --site bond-management-dev.localhost reinstall
{"matchedRules":[{"prefixRuleMatch":{"matchedPrefix":["bench","--site","bond-management-dev.localhost","reinstall"],"decision":"forbidden","justification":"Never destroy or overwrite the persistent Bond Management sites. See docs/verification.md."}}],"decision":"forbidden"}
```

The other persistent-site rules come from the same generator and are covered
by the sync test in `scripts/test_agent_policy.py`.

Surprises: the hook recognises literal `bench` anywhere in the arguments,
including inside the read-only `codex execpolicy check` command. No variations
were tried to bypass it. Codex version and the allowed rule check also warned:
`WARNING: proceeding, even though we could not create PATH aliases: Operation not permitted (os error 1)`.
Branch creation initially exited 128 because the sandbox could not write the
Git ref; the approved escalated retry exited 0.

Verification evidence:

- Risk classification: documentation-only live-session evidence; no policy or
  application change.
- Required gate: bench-root `apps/bond_management/scripts/verify.sh lint`.
- Commands executed: the requested three rule checks, two bench help probes,
  nonexistent protected-file probe, boolean environment probe and `git status`.
  Ran `apps/bond_management/scripts/verify.sh lint` from the bench root.
- Exit statuses: blocked commands had no process exit status; allowed rule
  check, environment probe and control exited 0. Sandboxed lint exited 1 at
  Semgrep startup (`ca-certs: empty trust anchors`); the approved escalated
  retry exited 0.
- Tests passed: hook probes, environment presence check and allowed control;
  temporary-site rule check returned no matches. Lint: pre-commit, skills.lock,
  Semgrep (0 findings), rule tests (4), guard (24), policy (25) and helpers (12).
- Tests failed: none executed failed. Inside Codex, the hook kept the two
  persistent-site rule checks from running; the user then confirmed the dev
  reinstall decision outside any agent.
- Tests not run: optional sandbox read; server, frontend, UI and lifecycle
  gates (documentation only).
- Blockers: none. Agents cannot run persistent-site `codex execpolicy check`
  commands, because the hook blocks them; run those checks from a plain terminal.
- Unverified local/CI differences: live macOS session only; no CI run requested.
- `docs/domain-model.md` reviewed: no data-model or data-flow change.

## Step 4: Codex project layer

- Unverified spec items checked first; results are in the spec's _Tool
  capabilities_ section. In short: `tool_input.command` is a string with
  `tool_name: "Bash"` (Codex 0.163.0 source), a trusted project
  `.codex/config.toml` can define permission profiles and
  `shell_environment_policy`, and macOS deny globs block reads at any depth.
  The spec's note on default environment excludes was corrected: they apply
  only with `ignore_default_excludes = false`.
- `.codex/rules/bond_management.rules`: 14 `forbidden` `prefix_rule`s from
  `agent_policy.codex_rules()`, one per persistent site and verb:
  `bench --site SITE VERB` for the five option verbs, `bench drop-site SITE` and
  `bench new-site SITE`. Each has a `match` example and a `not_match` example
  on a temporary site.
- `.codex/hooks.json`: `PreToolUse`, matcher `Bash`, runs
  `python3 "$(git rev-parse --show-toplevel)/scripts/claude_guard.py"`. No
  adapter: the payload matches the guard's contract. Outside a checkout Python
  exits 2 with a stderr reason, so the hook blocks rather than passes.
- `.codex/config.toml`: `shell_environment_policy.filters` excluding
  `*PASSWORD*`, `BOND_SHARE_LOCK_SOCKET` and `BOND_SHARE_LOCK_USER`, from
  `agent_policy.codex_config()`. Decision 2 asked for a user-level snippet only
  where a project file cannot carry the setting; this one can.
- The permission profile is a user-level snippet in
  [docs/agents/codex-user-config.md](../agents/codex-user-config.md), with the
  trust steps: its deny paths sit outside the workspace and differ per
  machine, and a project `default_permissions` would override each user's
  sandbox choice.
- `python3 -I bond_management/agent_policy.py --codex-rules|--codex-config`
  prints each generated file; `GENERATED_FILES` maps the flag to its path.
- `scripts/test_agent_policy.py` `CodexConfigSyncTests`: both files equal the
  generated text; the prefix list equals an independently written list and
  the core blocks every prefix; `.codex/` holds only the three reviewed files
  and `config.toml` only the environment table; every `SECRET_ENV_VARS` name
  is filtered and ordinary names are not; `hooks.json` is exact; the hook
  command blocks a protected read and a persistent-site reinstall with
  Codex's full payload shape and allows `git status`; it blocks outside a
  checkout. With `codex` installed, `codex execpolicy check` returns
  `forbidden` for every prefix, nothing for its temporary-site twin, and fails
  to load a file whose `not_match` the rule matches. CI has no Codex and skips
  that case.

### Probes (Codex CLI 0.163.0, macOS)

All under a scratch `CODEX_HOME` with decoy files and dummy variable values;
no protected file was read and no value printed.

- Profile in a trusted project `config.toml`: denied `*.decoy` at the top
  level, two levels deep and at an absolute path outside the workspace;
  `grep -r` saw "Operation not permitted"; a new matching file could not be
  created. Untrusted: the command refused to run.
- User-level profile in the documented shape (`extends = ":workspace"`,
  `":root" = "read"`, absolute `sites/**` globs, a `~/` path): `cat` and
  `python3 -I -c open()` denied, an unrelated file under `sites/` readable.
- The generated `.codex/` copied into a trusted scratch project: the five
  secret names were unset in the sandboxed command, an unrelated variable kept.
- Not exercised: a live model session (hook trust by hash, `/hooks`, escalation
  of `bench`).

### Verification evidence (step 4)

- Risk classification: agent configuration, policy core and lint test; no
  application, schema, permission or financial-rule change.
- Required gates: `verify.sh pre-push` (lint + server).
- Commands executed:
  - `env PATH=<bench>/env/bin:... bash scripts/verify.sh lint` from this
    worktree, after the last code change, with the new files marked
    intent-to-add so pre-commit sees them. Exit 0.
  - `PYTHONPATH=<worktree> apps/bond_management/scripts/verify.sh server` from
    the bench root after the last `agent_policy.py` change. Exit 0.
- Tests passed: pre-commit, skills.lock check, Semgrep (0 findings) and rule
  tests (4), guard suite (24), `test_agent_policy.py` (25, including the
  `codex execpolicy` case), `test_verify_helpers.py` (12), server suite
  (345 + 51 + 10).
- Mutation check: changing one verb in the rules file fails
  `test_generated_files_match_the_core`.
- Tests failed: the first lint run (two ruff `RUF005` findings in the new
  tests, fixed).
- Tests not run: frontend and UI gates (no client change); opt-in `lifecycle`
  and `share-race` (no site-handling change).
- Unverified local/CI differences: CI has not run; CI skips the Codex CLI case.
- `docs/domain-model.md` reviewed: no DocType, link, attachment or data-flow
  change.

## Step 3: Claude Read deny rules and sandbox tracer

### Deny rules

- `agent_policy.claude_read_deny_rules()` generates
  `Read(//**/common_site_config.json)`, `Read(//**/site_config.json)` and
  `Read(~/.config/bond_management/test-browser.env)` from `PROTECTED_FILES`
  and the new `BROWSER_CREDENTIALS` (home-relative path). `.claude/settings.json`
  carries them under `permissions.deny`; the PreToolUse hook entry is unchanged.
- `scripts/test_agent_policy.py` `ClaudeSettingsSyncTests`: the deny list equals
  the generated list (and the literal expected rules), every protected name has
  exactly one rule, `BROWSER_CREDENTIALS` is the path `verify.sh` loads, the
  hook entry is byte-for-byte the old one, and the file has no other keys (so
  a sandbox block cannot land without updating the test).
- Why `//**/`: project-relative patterns anchor at the session's working
  directory (an app checkout or worktree), and the bench's `sites/` is above
  it. A committed absolute bench path would not be portable.
- Why the credential rule is not `//**/test-browser.env`: the sandbox adds every
  `Read` deny rule to its `denyRead`, and `test_verify_helpers.py` writes, sources
  and deletes a synthetic `test-browser.env` under a temporary HOME. With the
  basename rule the sandboxed lint gate failed (tracer run 3). The hook still
  blocks the basename everywhere.

### Tracer

Setup: the draft block in a scratch settings file outside the repo (enabled,
`failIfUnavailable`, `allowUnsandboxedCommands: false`, `excludedCommands`
`bench *`, `scripts/verify.sh *`, `apps/bond_management/scripts/verify.sh *`,
`denyRead` on the three paths, `credentials.envVars` deny for every
`SECRET_ENV_VARS` name). Each run was a nested headless session
(`claude -p --settings <file>`, Claude Code 2.1.296, macOS Seatbelt) allowed
one Bash command. A scratch probe printed only labels and exit statuses, never
file contents; the driver exported dummy values (`tracer-dummy`) for
`FRAPPE_PASSWORD`, `DB_ROOT_PASSWORD` and `BOND_SHARE_LOCK_USER`.

| Run | Scope | Result |
| --- | --- | --- |
| 1 | `--settings`, user settings only | Probe: home write denied; `cat`, `head -c1`, `python3 open()` and `cat` through a symlink denied for all three files; `grep -r` over the dev site dir and over `sites/` from inside it exit 2; control `cat sites/apps.txt` 0; dummy secrets absent from `printenv`. |
| 2 | Project `.claude/settings.json` in a scratch project | Same probe, identical results: the block is honoured from project settings. |
| 3 | `--settings` + repo project settings, `bash scripts/verify.sh lint` | Exit 1: Semgrep could not open `~/.semgrep/semgrep.log`. Pre-commit and the `skills.lock` check passed. |
| 4 | As 3, plus `allowWrite: ["~/.semgrep"]` | Exit 1: `test_verify_helpers.py` could not delete its synthetic `test-browser.env` (basename deny). Semgrep scans passed. |
| 5 | As 4, credential rule anchored at its home path | Exit 1, but invalid: pre-commit reported eslint "files were modified" while this session was editing docs during the run; no tracked file changed. |
| 6 | As 5, no concurrent edits | **Exit 0.** Pre-commit, `skills.lock`, Semgrep (0 findings), rule tests 4, guard 24, policy 17, helpers 12. |
| 7 | As 6, probe again (symlinks created in the worktree) | All protected reads denied as in run 1, including symlinks to the home-anchored credential file. |

Notes:

- Non-fatal in run 6: Semgrep cannot write `~/.cache/semgrep_version`; the
  scans and tests still pass. `allowWrite` for it is optional.
- `printenv` inside the sandbox still shows two secret-like names that Claude
  Code itself injects (`CLAUDE_CODE_MESSAGING_TOKEN`,
  `CLOUDSDK_PROXY_PASSWORD`), not project secrets.
- An earlier probe attempt ran **unsandboxed** by mistake (the scratch project
  directory had not been created and the driver did not stop on a failed
  `cd`). It printed statuses only, no contents, and showed every probe
  succeeding. That confirms the `Read` deny rules alone do not stop a script
  that opens the files itself.
- The auto-mode classifier refused two nested runs that asked Claude to retry
  with `dangerouslyDisableSandbox`. The tracer therefore did not check
  `allowUnsandboxedCommands: false` or `failIfUnavailable` directly; the docs
  say both are read from project settings.
- Not exercised: the `excludedCommands` path (a bench or `verify.sh server`
  call from the sandboxed session). Exclusions match the call text, and a
  `cd`, a redirect or a command substitution keeps the call sandboxed, so the
  bench-root form used for gates from a worktree
  (`cd <bench> && ... verify.sh server`) would stay sandboxed and fail
  closed, since bench reads the denied config.
- Linux/WSL2 expand `denyRead` globs to concrete paths; the cost of
  `//**/site_config.json` there is unmeasured.

### Recommendation

The tracer passed, so per decision 3 the sandbox can be enabled. Commit the
block (generated from the core, with the sync test extended) only after the
user approves, and first:

1. Run one manual check in an interactive session with the block in
   `.claude/settings.local.json`: `/sandbox` shows strict mode, a
   `dangerouslyDisableSandbox` retry is refused, and an excluded
   `scripts/verify.sh server` run from the app checkout (not a worktree) works.
2. Document in `verification.md` that worktree sessions cannot run the
   server/UI gates through the `cd <bench> && ...` form under the sandbox; the
   person runs them, or the session uses the app checkout.

Narrowest additions the block needs: `filesystem.allowWrite: ["~/.semgrep"]`
(required), `~/.cache/semgrep_version` (optional, silences a warning).

### Verification evidence (step 3)

- Risk classification: agent permission settings, policy core and lint test;
  no application, schema, permission or financial-rule change.
- Required gates: `verify.sh pre-push` (lint + server).
- Commands executed:
  - `verify.sh lint` from this worktree with the bench `env/bin` on `PATH`
    (unsandboxed, this session). Exit 0.
  - `PYTHONPATH=<worktree> apps/bond_management/scripts/verify.sh server`
    from the bench root, after the last code change. Exit 0.
  - Sandboxed `bash scripts/verify.sh lint` (tracer run 6). Exit 0.
- Tests passed: pre-commit, skills.lock check, Semgrep (0 findings) and rule
  tests (4), guard suite (24), `test_agent_policy.py` (17), `test_verify_helpers.py`
  (12), server suite (345 + 51 + 10).
- Mutation check: dropping one rule from `.claude/settings.json` fails
  `test_read_deny_rules_match_the_core`.
- Tests failed: none on the final tree.
- Tests not run: frontend and UI gates (no client or credential-loading
  change); opt-in `lifecycle` and `share-race` (no site-handling change).
- Blockers: none for the deny rules. Sandbox open checks are listed under
  _Recommendation_.
- Unverified local/CI differences: CI has not run.
- `docs/domain-model.md` reviewed: no DocType, link, attachment or data-flow
  change.

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
