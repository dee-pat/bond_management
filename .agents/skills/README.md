# App skills

Codex reads this folder directly; Claude Code reads it through the
`.claude/skills` symlink. Keep upstream skills unmodified and put app-specific
adaptations in the root or nested `AGENTS.md` files instead.

- **Upstream** (`frappe-app-dev`, `code-style`, `frappe-code-review`,
  `frappe-ui`): pinned in [`skills.lock`](../../skills.lock). Run
  `scripts/sync-skills.sh check` to confirm the copies match their pins. To
  upgrade, edit a revision, run `scripts/sync-skills.sh sync`, and commit the
  lock and the skill together.
- **`playwright-cli`**: symlink to `node_modules/@playwright/cli/skills/playwright-cli`,
  pinned by `package.json`; run `yarn install` in the app root to resolve it.
- **This app** (`bond-management-migration`, `grilling`): edit here.

[frappe-agent-kit.md](../../docs/plans/frappe-agent-kit.md) plans moving the
generic app-owned skills to a shared kit repo.
