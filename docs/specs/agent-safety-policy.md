# Agent-neutral safety policy

Status: design accepted with the decisions below (2026-10-17); rollout steps 1
to 4 implemented. Step 3's Claude sandbox is enabled in `.claude/settings.json`
after the tracer and the interactive checks passed.
Progress:
[agent-safety-policy-progress.md](../plans/agent-safety-policy-progress.md).
The current hook's grammar and guarantee stay as defined in
[claude-guard-shell-policy.md](claude-guard-shell-policy.md).

## Goal and user outcome

The working rules in `AGENTS.md` and [verification.md](../verification.md)
(keep secrets out of commands and output, never destroy or overwrite the
persistent sites, use uniquely named temporary sites, no environment dumps)
hold the same way whether Claude Code, Codex, or a person at a shell runs the
work. Each rule is enforced by the cheapest layer that holds for every caller
it can reach, and every remaining gap is written down rather than assumed.

## Non-goals

- No new shell grammar. The bounded grammar is frozen; supporting more Bash
  forms is never a reason to change it.
- No complete sandbox for people at a shell. A human with bench access owns
  the bench and can read its config; for them the rules stay instructions plus
  the guards inside project scripts.
- No changes to Frappe or bench (no monkey-patching), no application schema,
  API, permission or financial-rule changes.
- No protection against a deliberately hostile agent; the threat model is an
  agent that makes a mistake or follows injected instructions.

## Decisions (user, 2026-10-17)

1. **Bench boundary:** `bench` and `scripts/verify.sh` run outside the agent
   sandbox. The gap that `bench execute`/`console` or an edited `verify.sh` can
   still read config is accepted and stays instruction-only plus review.
2. **Codex config:** `.codex/rules/` and `.codex/hooks.json` are committed in
   the repo. The permission profile and environment filter are documented as a
   user-level snippet if a project file cannot carry them.
3. **Claude rollout:** staged. `Read(...)` deny rules first; the sandbox
   (`allowUnsandboxedCommands: false`, `failIfUnavailable: true`) is enabled
   only after a tracer run of `verify.sh lint` inside it succeeds.
4. **Credentials:** `verify.sh ui` loads `test-browser.env` itself when the
   variables are unset; the hook's `source` exception is then retired.
5. **Names:** the `claude_guard*` files keep their names; only the new core
   gets a neutral name.

## Current problem

Only Claude Code is guarded, by one PreToolUse hook (`.claude/settings.json` →
`scripts/claude_guard.py` for `Bash|Read`). The repo has no Codex config. The
hook is the main secret control, but a syntax check cannot be complete: PR #61
needed many review rounds, and its own spec leaves recursive reads, interpreter
one-liners, symlinks and program behaviour outside the guarantee
([code-review.md](../code-review.md#when-a-finding-blocks-merge)). The
persistent-site set is also defined twice: `scripts/claude_guard.py` and
`bond_management/bond_management/tests/temporary_site_guard.py`.

## Inventory and classification

Layers: **(a)** project scripts and bench helpers, holds for every caller that
uses them; **(b)** pre-execution agent hook or command rule; **(c)** OS sandbox
or tool permission layer; **(d)** instruction only.

| Rule today (where) | Target layer | Notes |
| --- | --- | --- |
| Read tool path whose basename is `site_config.json`, `common_site_config.json` or `test-browser.env` (`violation`, Read branch) | (c) Claude `Read` deny rules; (b) hook stays as backstop | Codex has no separate Read tool; its reads go through the shell, so its control is the sandbox row below. |
| Protected basenames or matching globs in Bash words, `=` values, short-option tails and redirection targets (`protected_names`) | (c) sandbox read deny for agent shells; (b) hook backstop | The OS layer also closes `grep -r`, `tar -c .`, `python -c`, symlinks. **Conflict:** bench reads both config files in-process (`frappe/config.py:get_site_config`), so bench cannot run inside a sandbox that denies them. See _Design_, "bench boundary". |
| Only exact `source`/`.` of `test-browser.env` (`credential_source`) | (a) `verify.sh ui` loads the file itself; (c) agent shells cannot read it | Done in step 2: `credential_source` is removed and the hook blocks every `source`. |
| No expansion of variables named with `PASSWORD`, `SECRET`, `TOKEN` or `API_KEY` (`SECRET_NAME`) | (c) scrub those variables from agent shells; (b) backstop | Claude `sandbox.credentials.envVars` `deny`; Codex `shell_environment_policy`. |
| `printenv`, bare `env`, bare `set`, xtrace (`command_violation`, `validate_set`) | (c) scrubbed environment makes a dump harmless; (b) backstop | |
| Destructive verbs `drop-site`, `trim-database`, `trim-tables`, `restore`, `partial-restore`, `reinstall`, forced `new-site` need one literal temporary site; persistent sites always blocked (`destructive_violation`) | (a) in project helpers that drop sites; (b) hook and Codex `prefix_rule` for direct agent calls; (d) for people | Frappe's site commands (`commands/site.py`) call no app hook, so there is no app-level interception point without editing core. |
| Temporary-site name `bond-management-<name>-<32 hex>.localhost` (`TEMPORARY_SITE`) | (a) `verify.sh` naming and `temporary_site_guard.validate_temporary_site`; (b) hook | Already enforced in (a) for the lifecycle and share-race helpers. |
| Bounded grammar: unsupported syntax fails closed (`claude_guard_shell.py`) | (b), frozen | Purpose narrows to "keep the hook's literal checks sound"; not the main secret control. |
| Bounded Read path text (length, controls) | (b) | Payload validation for the hook only. |
| Approval before recreating, dropping or restoring the persistent pair; no credentials in repo files or logs; no bypass through exclusions | (d) | Also covered by review ([security-review.md](../security-review.md)) and the existing "Clean diff" rule. |

## Tool capabilities (checked 2026-10-17)

Installed: Claude Code 2.1.296, Codex CLI 0.163.0, Frappe v16.51.0.

**Claude Code** — checked against the official
[sandboxing](https://code.claude.com/docs/en/sandboxing) and
[permissions](https://code.claude.com/docs/en/permissions) pages.

- `permissions.deny` `Read(...)` rules use gitignore patterns (`Read(**/site_config.json)`;
  `//` absolute, `~/` home). They cover Read, Grep, Glob, `cat`/`head`/`tail`/`sed`/`tee`
  and redirect targets, and follow symlinks, but per the docs do not cover
  "a command that reads files without naming them" or "arbitrary subprocesses".
- `sandbox.enabled` gives OS enforcement (Seatbelt on macOS, bubblewrap on
  Linux/WSL2) for Bash and its children. `sandbox.filesystem.denyRead`,
  `denyWrite`, `allowRead`, `allowWrite`; `sandbox.credentials.files` and
  `envVars` with `"mode": "deny"` (env vars are unset for sandboxed commands).
  Deny entries merge across scopes and cannot be removed by another scope.
- The sandbox does not cover Read/Edit tools, hooks or MCP servers;
  `excludedCommands` and unsandboxed retries run with full access.
  `allowUnsandboxedCommands: false` disables the retry; `failIfUnavailable`
  makes startup fail instead of running unsandboxed. The docs warn that
  excluding an interpreter or a script inside the working directory gives up
  the boundary.
- Rechecked for step 3 (2026-10-17, same version, the permissions, sandboxing
  and settings-reference pages):
  - `Read` path patterns: `//path` absolute, `~/path` home, `/path` relative
    to the settings source (the primary working directory for project
    settings, so a worktree's own tree), `path` relative to the current
    directory. A bare name matches at any depth under its anchor only, so
    `Read(site_config.json)` would not reach the bench's `sites/`, which sits
    above an app checkout. `Read(//**/NAME)` matches the name anywhere, the
    same as the hook's basename rule; the committed rules use it for the two
    site-config names. `test-browser.env` is denied at its one home path
    instead, because `scripts/test_verify_helpers.py` writes a synthetic file
    of that name under a temporary HOME and the sandbox would block it (see the
    tracer).
  - Sandbox paths use other prefixes: `/` and `//` absolute, `~/` home,
    `./` or none relative to the project root. `denyRead` wildcards work on
    every platform; on Linux/WSL2 a read entry is expanded to the concrete
    paths it matches. `denyRead` also takes in every `Read(...)` deny rule, so
    the committed rules already feed the sandbox once it is on.
  - `sandbox.enabled`, `failIfUnavailable`, `allowUnsandboxedCommands`,
    `excludedCommands`, `filesystem.denyRead` and `credentials.envVars` are
    read from any settings file, project included. Only the loosening keys are
    limited: under an admin-required sandbox (`allowUnsandboxedCommands: false`
    from managed settings or `--settings`) a repository's `excludedCommands`
    and `allowWrite` are ignored, and a repository's `false` for `enabled` or
    `failIfUnavailable` loses to a user `true`. A user-level
    `allowUnsandboxedCommands: false` beats a project `true`; nothing says a
    project `false` is ignored. `envVars` `mask` entries are dropped from
    project settings; `deny` entries are kept.
  - `excludedCommands` uses `Bash(...)` rule syntax and matches the text of
    the call, so `bench *` does not match `/path/to/bench`, and every command
    in a chained call must match. A call with `cd`, a redirect to a file, a
    command substitution, a subshell or control flow, or a leading
    `sudo`/`eval`/`xargs` stays sandboxed. Excluded commands go through the
    normal permission flow.
  - Results of the tracer that exercised these settings are in the progress
    note's _Step 3_ section.

**Codex CLI** — checked against `codex --help`, `codex sandbox --help`,
`codex execpolicy check --help`, `codex features list` (`hooks` stable/true),
and the official [hooks](https://learn.chatgpt.com/docs/hooks),
[rules](https://learn.chatgpt.com/docs/agent-configuration/rules),
[permissions](https://learn.chatgpt.com/docs/permissions) and
[config reference](https://learn.chatgpt.com/docs/config-file/config-reference)
pages.

- Sandbox modes `read-only`, `workspace-write`, `danger-full-access`;
  `sandbox_workspace_write.writable_roots`, `network_access`.
- Permission profiles (Beta): `default_permissions` plus
  `[permissions.<name>.filesystem]` with `"read" | "write" | "deny"`; `deny`
  blocks reads and writes, globs allowed under `":workspace_roots"`. macOS uses
  Seatbelt and refuses to run a command it cannot enforce. Profiles do not
  combine with `sandbox_mode`.
- `shell_environment_policy`: `inherit`, `exclude`/`include_only` (legacy) or
  `filters` (case-insensitive). The automatic exclusion of names containing
  `KEY`, `SECRET`, `TOKEN` applies only with `ignore_default_excludes = false`
  (the documented default is `true`), and never covers `PASSWORD`.
- Exec policy rules (experimental): Starlark `prefix_rule(pattern, decision,
  justification, match, not_match)` in `.codex/rules/*.rules`; `forbidden`
  wins; plain `bash -lc` chains are split, but anything with redirection,
  variables, globs or substitutions is matched as one opaque invocation.
- Hooks: `PreToolUse` covers shell (`Bash`), `exec_command`, `apply_patch` and
  MCP tools; blocks with exit 2 or `permissionDecision: "deny"`; payload has
  `tool_name` and `tool_input.command`. The docs call hooks "a useful
  guardrail, not a complete enforcement boundary". Each hook definition needs
  per-user trust by hash.
- Project `.codex/config.toml`, `hooks.json` and `rules/` load only when the
  user trusts the project.

Verified for step 4 (2026-10-17, Codex CLI 0.163.0 on macOS; probes used a
scratch `CODEX_HOME`, decoy files and dummy variables, never the protected
files):

- **Hook payload.** From the source at tag `rust-v0.163.0`
  (`129b8ec`): `exec_command`'s `pre_tool_use_payload` sends
  `tool_name: "Bash"` and `tool_input: {"command": args.cmd}`, where `cmd` is a
  `String` (`ExecCommandArgs`). `shell_spec.rs` defines `exec_command` as the
  only shell tool; there is no argv-list shell tool in that tree. The payload also carries `session_id`, `turn_id`, `cwd`,
  `hook_event_name`, `model`, `permission_mode` and `tool_use_id`, which the
  guard ignores. Exit 2 blocks only with a non-empty stderr reason; any other
  non-zero exit marks the hook failed and does not block. `write_stdin` (input
  to a running exec session) emits no `PreToolUse`. The hook command runs with
  the session cwd and no project-directory variable. Not exercised in a live
  model session.
- **Project permission profiles.** Yes, when the project is trusted:
  `codex sandbox -C <project> -P <name>` applied a profile defined only in the
  project's `.codex/config.toml`. Untrusted, the project `[permissions]` table
  was dropped and the command refused to run
  (`default_permissions requires a [permissions] table`).
  A project `shell_environment_policy.filters` table also applied, with globs
  and exact names.
- **macOS glob deny-read.** Under Seatbelt, `"**/*.x" = "deny"` in
  `":workspace_roots"` and absolute keys such as `"/abs/sites/**/x" = "deny"`
  blocked `cat`, `grep -r` and `python3 -c open()` with "Operation not
  permitted", matched files at any depth including directly under the glob's
  base, and blocked creating a new matching file. `"~/..." = "deny"` resolved
  against `HOME`. Deny wins over `":root" = "read"`.
- **Rules.** `codex execpolicy check` loads `.codex/rules/bond_management.rules`
  and returns `forbidden` for each prefix; a `not_match` example that the rule
  matches makes loading fail. `execpolicy check` does not split `bash -lc`
  scripts, and matches `bench` only as a literal first word: `--site=SITE`,
  an absolute bench path and redirected scripts are not matched.

## Design

### One policy core, thin adapters

- New stdlib-only module `bond_management/agent_policy.py` holds the policy
  data and pure checks: `PERSISTENT_SITES`, the temporary-site pattern,
  `DESTRUCTIVE_VERBS`, `PROTECTED_FILES`, the secret-name pattern and the list
  of secret environment variables (`FRAPPE_PASSWORD`, `FRAPPE_ADMIN_PASSWORD`,
  `DB_ROOT_PASSWORD`, `BOND_SHARE_LOCK_*`), plus `classify_site(name)` and
  `destructive_site_violation(argv)`. It imports nothing from Frappe, so the
  hook can load it by file path (no package init) and bench code can import it.
- `temporary_site_guard.py` and `scripts/claude_guard.py` import their
  constants from the core; the shell scanner stays in `claude_guard_shell.py`
  unchanged.
- Generated adapter config, checked in and kept in sync by a lint test
  (`scripts/test_agent_policy.py` regenerates in memory and diffs):
  - `.claude/settings.json`: `Read(...)` deny rules, sandbox `denyRead`,
    `credentials.envVars` deny entries, the existing hook.
  - `.codex/rules/bond_management.rules` (`agent_policy.py --codex-rules`):
    `forbidden` `prefix_rule`s for each destructive verb against each
    persistent site in the canonical `bench --site SITE VERB` spelling, and
    `bench drop-site SITE` / `bench new-site SITE` for the positional verbs
    (`POSITIONAL_SITE_VERBS`; `new-site` on a persistent site is forbidden in
    any form, since recreating one needs approval anyway), with
    `match`/`not_match` examples.
  - `.codex/hooks.json`: `PreToolUse` on `Bash` running the same guard, resolved
    from `git rev-parse --show-toplevel` because Codex has no project-directory
    variable. The payload matches the guard's contract, so there is no adapter.
  - `.codex/config.toml` (`agent_policy.py --codex-config`):
    `shell_environment_policy.filters` excluding `*PASSWORD*` and the other
    `SECRET_ENV_VARS`. A trusted project file carries it, so it is not in the
    user snippet.
  - [docs/agents/codex-user-config.md](../agents/codex-user-config.md): the
    trust steps and the user-level permission profile. A project file could
    carry a profile, but the denied paths (the bench's `sites/`) are outside
    the workspace and differ per machine, and a project `default_permissions`
    would override each user's sandbox choice.

### Rules that move into project scripts (a)

- `verify.sh ui|playwright` loads `$HOME/.config/bond_management/test-browser.env`
  itself when the `FRAPPE_*` variables are unset, so no agent command sources
  it. Existing callers that export the variables keep working, and exported
  values win over the file. Extra arguments go to Playwright, so a single spec
  runs through the same gate.
- `drop_temporary_site` and `create_temporary_site` call the core's site check
  (`python3 -I bond_management/agent_policy.py SITE`, exit 0 only for one
  temporary site) before any bench call, so a corrupted `TEMPORARY_SITE` can
  never name a persistent site.
- Optional `scripts/temp-site.sh create|drop PREFIX` helper wrapping the same
  functions, so ad-hoc local fresh-install checks have one reviewed path. People
  can still call bench directly; that stays (d).

### Rules that move to sandbox and permission settings (c)

- Claude, after the tracer run (decision 3): enable the sandbox with `denyRead` on
  `//**/site_config.json`, `//**/common_site_config.json` and
  `~/.config/bond_management/test-browser.env` (the same paths as the `Read`
  deny rules, which the sandbox also takes in), `credentials.envVars` deny for
  `SECRET_ENV_VARS`, `allowUnsandboxedCommands: false`, `failIfUnavailable:
  true`, `excludedCommands` for `bench *` and the two `verify.sh` spellings
  (decision 1), and `filesystem.allowWrite: ["~/.semgrep"]`, the one extra
  write path the lint gate needs (Semgrep opens its log there at startup).
  `agent_policy.claude_sandbox_settings()` generates the block; the interactive
  checks that preceded it are in the progress note. Claude sessions run the
  excluded gates as `scripts/verify.sh <stage>` from the app checkout, because
  Claude Code resets a `cd` outside the project and a `cd ... &&` call stays
  sandboxed; worktree sessions cannot run the server, UI or opt-in gates
  (documented in verification.md).
- Codex: a permission profile with `deny` on the same paths, writes limited to
  the workspace, and a `shell_environment_policy` filter excluding
  `*PASSWORD*` and the `BOND_SHARE_LOCK_*` names.

### The bench boundary

Bench must read the protected config to work, so it cannot run inside a sandbox
that denies it. Decided (decision 1): `bench` and `scripts/verify.sh` run
outside the sandbox (Claude `excludedCommands`; Codex escalation/approval), and
the hook and Codex rules stay the literal check on those calls. This is an
accepted trade-off, not a guarantee: an unsandboxed bench can still run code
that reads config (`bench execute`, `console`), and an agent can edit
`verify.sh` before running it. Those stay (d) plus review. Everything else the agent runs is
sandboxed, which is where the hook's known gaps were.

### Names

Decided (decision 5): **no rename**. `claude_guard.py` stays the Claude
adapter and the Codex hook calls the same script; only the new core gets the
neutral name. Renaming would touch `.claude/settings.json`, `verify.sh`,
`verification.md`, `testing-matrix.md`, `code-review.md`, the cases file, both
test files, the `Blocked by scripts/claude_guard.py` diagnostic the tests
assert, and three historical plan notes, for no behaviour change.

## Contract

- Bench disclosure commands (`show-config`, `mariadb`, `db-console`, `postgres`)
  are denied for every site, including temporary sites. They are independent of
  the destructive-site classification. `uninstall-app` and
  `remove-from-installed-apps` require one literal temporary site, like restore.
- `set-config` accepts only a boolean (`true`, `false`, `1`, `0`) for
  `allow_tests`, `bond_investor_spa_enabled`, or `bond_migration_lifecycle_test`,
  on the persistent test site or one temporary site. Global, parse and unknown
  options/keys are denied. `set-admin-password` is allowed only on those sites
  to preserve documented test recovery. Other bench setup and verification
  commands retain their existing policy. The hook handles argument-sensitive
  exceptions; generated Codex rules forbid canonical unsafe prefixes.
- Hook contract unchanged: JSON on stdin, exit 0 allows, exit 2 blocks,
  diagnostics never echo input. A Codex adapter must keep the same contract.
- The core's checks are pure functions over literal strings; same input, same
  answer, for every adapter and helper.
- Generated adapter files are derived from the core only; hand edits fail lint.

## Failure and recovery

- Sandbox unavailable: Claude fails at startup (`failIfUnavailable`); Codex on
  macOS refuses unenforceable commands. Recovery is to fix the sandbox, not to
  disable it in project settings.
- A gate breaks under the sandbox (cache dirs, bench writes outside the
  worktree): add the narrowest `allowWrite`/exclusion and record it here.
- Codex project layer untrusted: rules and hooks do not load; verification.md
  says so and Codex users fall back to the user-level snippet.
- Rollback: revert the settings and config files; no data, schema or site
  state is involved.

## Tests

- `scripts/test_agent_policy.py` (lint): core checks for persistent, temporary
  and foreign sites across every destructive verb; generated-file sync for
  `.claude/settings.json` and `.codex/` files.
- The guard matrix includes disclosure, app removal and supported test setup
  cases; it imports policy checks from the core.
- `temporary_site_guard` tests keep passing with the shared constants.
- Codex rules: `codex execpolicy check --rules ...` cases when `codex` is
  installed; the inline `match`/`not_match` examples are validated by Codex at
  load. CI does not have Codex, so the Python sync test is the required gate.
- Manual tracer per tool, recorded in the progress note: from a sandboxed
  agent, `cat`, `grep -r`, `python3 -c` on a protected file are denied;
  `printenv` shows no secret variables; `verify.sh lint` passes.

## Rollout and compatibility

1. Core module and shared constants (no behaviour change).
2. `verify.sh` loads credentials and checks sites through the core. Once that
   lands, retire the hook's `source` exception and the documented `source`
   command in verification.md (decision 4).
3. Claude `Read` deny rules. Then a tracer run of `verify.sh lint` inside the
   sandbox; enable the sandbox block only after it succeeds (decision 3).
4. Codex rules and hooks committed under `.codex/`, loaded behind project
   trust; user-level snippet documented (decision 2).

Each step is its own PR. Existing commands, the hook payload contract and file
names keep working; the `source` exception is the only planned removal, and
only after step 2 gives callers a replacement.

## Acceptance criteria

- One definition of persistent sites, temporary-site pattern, destructive verbs,
  protected files and secret names, used by the hook, helpers and generated
  config.
- With Claude's sandbox on, a protected file cannot be read by any sandboxed
  command, including spellings outside the hook's guarantee.
- Codex blocks destructive bench verbs on persistent sites in canonical form
  and cannot read the protected files from its sandbox (if profiles allow).
- No agent command sources `test-browser.env`; the hook no longer allows it.
- `verify.sh lint` runs the new tests; all gates pass; verification.md
  describes each layer and what it does not cover.

## Follow-ups

- Run a live Codex session tracer once a user has trusted the project and
  hook: a blocked `cat` of a protected file through the hook, a `forbidden`
  rule decision, and the profile denying `grep -r` from the sandbox.
- Decide whether the persistent dev site's `site_config.json` should move to a
  path the sandbox denies by directory rather than by basename.
- Consider `CLAUDE_CODE_SUBPROCESS_ENV_SCRUB` for hooks and MCP servers.
- Decide whether to allow writes to `~/.cache/semgrep_version` (silences a
  harmless Semgrep warning; untested whether `allowWrite` accepts a file path).
- Find out why the Claude desktop app's `/sandbox` panel showed the sandbox
  off while the session's commands ran under the project's sandbox paths.
- `~/.config/bond_management/` also holds a `test-site-ui.env` that is not in
  `PROTECTED_FILES` (its contents were not read). Decide whether it holds
  credentials and should be protected or removed.

`docs/domain-model.md` reviewed: no DocType, link, attachment or data flow
changes.
