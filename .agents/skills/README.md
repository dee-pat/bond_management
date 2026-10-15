# App skills

Codex reads this folder directly; Claude Code reads it through the
`.claude/skills` symlink. Keep upstream skills unmodified and put app-specific
adaptations in the root or nested `AGENTS.md` files instead.

- **Pinned** in [`skills.lock`](../../skills.lock) and vendored unmodified:
  `frappe-app-dev`, `code-style`, `frappe-code-review` (frappe/skills),
  `frappe-ui` (frappe/frappe-ui), and `frappe-migration`, `grilling`,
  `pr-review-threads` ([frappe-agent-kit](https://github.com/dee-pat/frappe-agent-kit)).
  The same lock pins the _Shared Frappe rules_ block in `AGENTS.md`. Run
  `scripts/sync-skills.sh check` to confirm the copies match their pins (the
  lint gate runs it). To upgrade, edit a revision, run
  `scripts/sync-skills.sh sync`, and commit the lock and the copies together.
- **`playwright-cli`**: symlink to `node_modules/@playwright/cli/skills/playwright-cli`,
  pinned by `package.json`; run `yarn install` in the app root to resolve it.
- **This app** (`bond-management-debugging`, `bond-management-migration`): edit
  here.

[frappe-agent-kit.md](../../docs/plans/frappe-agent-kit.md) records how the
shared kit was split out of this app.
