# Codex setup for Bond Management

The repo commits Codex's project layer, generated from the policy core
`bond_management/agent_policy.py` (see the
[agent safety policy](../specs/agent-safety-policy.md)):

- `.codex/rules/bond_management.rules`: `forbidden` exec-policy rules for each
  destructive bench verb against each persistent site, in the canonical
  `bench --site SITE VERB` and `bench drop-site|new-site SITE` spellings.
- `.codex/hooks.json`: runs `scripts/claude_guard.py` on `PreToolUse` for shell
  calls (`Bash`, which covers `exec_command`). Codex sends the same payload the
  guard expects: JSON on stdin with `tool_input.command` as a string. Exit 2
  blocks with the guard's reason.
- `.codex/config.toml`: `shell_environment_policy.filters` removes every
  `*PASSWORD*` variable and the other `BOND_SHARE_LOCK_*` names from the
  commands Codex runs.

`scripts/test_agent_policy.py` fails when any of these files drifts from the
core. Regenerate with the command in each file's header; never edit them by
hand.

## One-time trust (per user, per checkout)

Codex loads none of the project layer until you trust the project, and runs no
hook until you trust that hook:

1. Start `codex` in the checkout (each worktree path is a separate project)
   and accept the trust prompt. Untrusted, the rules, hook and environment
   filter are all skipped.
2. Run `/hooks`, review the `PreToolUse` hook, and trust it. Codex records hook
   trust by hash, so review it again whenever `.codex/hooks.json` changes.
3. Check the rules load:
   `codex execpolicy check --rules .codex/rules/bond_management.rules bench --site bond-management-dev.localhost reinstall`
   prints `"decision":"forbidden"`.

## User-level permission profile

The profile stays in your own `~/.codex/config.toml`, because the files it must
deny sit outside the workspace at paths that differ per machine (the bench's
`sites/`), and a project `default_permissions` would override each user's
sandbox choice. Replace `/ABSOLUTE/PATH/TO/frappe-bench` with your bench root.
Remove any `sandbox_mode` setting: when one is present, Codex ignores
`default_permissions`.

```toml
default_permissions = "bond-management"

[permissions.bond-management]
extends = ":workspace"

[permissions.bond-management.filesystem]
":root" = "read"
"/ABSOLUTE/PATH/TO/frappe-bench/sites/**/site_config.json" = "deny"
"/ABSOLUTE/PATH/TO/frappe-bench/sites/common_site_config.json" = "deny"
"~/.config/bond_management/test-browser.env" = "deny"
```

On macOS this stops every sandboxed command from opening those files,
including `grep -r` and `python3 -c`; a `**` glob also matches a file directly
under `sites/`.
`bench` and `scripts/verify.sh` must read the site config, so they fail inside
this sandbox; approve their escalation only for those commands (spec decision
1). Escalated commands run outside the profile; the hook and the rules still
check them.

## What stays outside Codex's guarantee

- Rules match literal argument prefixes only. `bench --site=SITE VERB`, an
  absolute path to bench, or a command with redirection, variables or
  substitutions reaches the hook, which applies the full check; the hook's own
  limits are in [claude-guard-shell-policy.md](../specs/claude-guard-shell-policy.md).
- A hook that fails to run (other than exit 2) does not block. The command
  resolves the guard from `git rev-parse --show-toplevel`; outside a checkout
  Python cannot find the script and exits 2, which blocks.
- Input written to an already running interactive shell (`write_stdin`) is not
  checked again.
- The environment filter applies to the commands Codex spawns, so expect
  `verify.sh share-race` run through Codex not to see `BOND_SHARE_LOCK_*`; run
  it from your own terminal. `verify.sh ui` loads its credentials file itself.
