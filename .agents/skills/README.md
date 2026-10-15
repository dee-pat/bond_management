# App skills

Codex reads this folder directly; Claude Code reads it through the
`.claude/skills` symlink. Keep upstream skills unmodified and put app-specific
adaptations in the root or nested `AGENTS.md` files instead.

- **Pinned** in [`skills.lock`](../../skills.lock) and vendored unmodified:
  `frappe-app-dev`, `code-style`, `frappe-code-review` (frappe/skills),
  `frappe-ui` (frappe/frappe-ui), `playwright-cli` (microsoft/playwright-cli,
  at the commit `@playwright/cli` in `package.json` was built from), and
  `frappe-migration`, `grilling`,
  `pr-review-threads` ([frappe-agent-kit](https://github.com/dee-pat/frappe-agent-kit)).
  The same lock pins the _Shared Frappe rules_ block in `AGENTS.md` and
  Frappe's Semgrep rules in `semgrep/frappe/`. Run
  `scripts/sync-skills.sh check` to confirm the copies match their pins (the
  lint gate runs it). To upgrade, edit a revision, run
  `scripts/sync-skills.sh sync`, and commit the lock and the copies together.
  When bumping `@playwright/cli`, pin `playwright-cli` to the new version's
  `gitHead` (`npm view @playwright/cli@<version> gitHead`).
- **This app** (`bond-management-debugging`, `bond-management-migration`): edit
  here.
