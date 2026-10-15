# App skills

Codex reads this folder directly; Claude Code reads it through the
`.claude/skills` symlink. Keep upstream skills unmodified and put app-specific
adaptations in the root or nested `AGENTS.md` files instead.

| Skill                       | Source                                                                    |
| --------------------------- | ------------------------------------------------------------------------- |
| `bond-management-migration` | This app                                                                  |
| `grilling`                  | This app                                                                  |
| `frappe-app-dev`            | `frappe/skills` `skills/frappe-app-dev` at `c1118cbf175a3d4393fb7d02d749876eaf8a86e8` |
| `code-style`                | `frappe/skills` `skills/code-style` at the same revision                  |
| `frappe-code-review`        | `frappe/skills` `skills/frappe-code-review` at the same revision          |
| `frappe-ui`                 | `frappe/frappe-ui` `skills/frappe-ui` at `15ed4fecee1c906befdf23cc14f7b7bb0d7acbf4`, without `evals/` |
| `playwright-cli`            | Symlink to `node_modules/@playwright/cli/skills/playwright-cli`; run `yarn install` in the app root to resolve it |

To refresh an upstream skill, replace its folder with the upstream copy at a
newer revision and update the revision above. Do not reformat the copy.
