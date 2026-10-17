# Agent-neutral safety policy

Status: design accepted with the decisions below (2026-10-17); rollout steps 1
and 2 implemented.
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
- Unverified here: that `allowUnsandboxedCommands: false` and
  `failIfUnavailable` are honoured from project `.claude/settings.json` (the docs
  describe the admin-required case for managed settings and `--settings`), and
  how pre-commit/Semgrep caches outside the worktree behave in the sandbox.

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
  `filters`; default excludes names containing `KEY`, `SECRET`, `TOKEN` — not
  `PASSWORD`.
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
- Unverified here: whether a project `.codex/config.toml` may define
  permission profiles; whether `tool_input.command` for `Bash`/`exec_command`
  is a string (as the current hook requires) or an argv list; macOS glob
  deny-read behaviour.

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
  - `.codex/rules/bond_management.rules`: `forbidden` `prefix_rule`s for each
    destructive verb against each persistent site in the canonical
    `bench --site SITE VERB` and `bench drop-site SITE` spellings, with
    `match`/`not_match` examples.
  - `.codex/hooks.json`: `PreToolUse` on `Bash` running the same guard, once
    the payload shape is confirmed.
  - `docs/agents/codex-user-config.md` (or a section in verification.md): the
    user-level snippet for permission profile and `shell_environment_policy`
    if a project file cannot carry them.

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

- Claude, after the tracer run (decision 3): enable the sandbox with `denyRead` on the bench's `sites/**/site_config.json`,
  `sites/common_site_config.json` and `~/.config/bond_management/test-browser.env`,
  `credentials.envVars` deny for the secret variables, `allowUnsandboxedCommands:
  false`, `failIfUnavailable: true`; matching `Read(...)` deny rules.
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
- Existing guard matrix unchanged and still green; it now imports constants
  from the core.
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

- Confirm the Codex hook payload shape and project-level profile support.
- Decide whether the persistent dev site's `site_config.json` should move to a
  path the sandbox denies by directory rather than by basename.
- Consider `CLAUDE_CODE_SUBPROCESS_ENV_SCRUB` for hooks and MCP servers.

`docs/domain-model.md` reviewed: no DocType, link, attachment or data flow
changes.
