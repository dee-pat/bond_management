# Shared Frappe agent kit

Status: all phases done. The kit is public at
[dee-pat/frappe-agent-kit](https://github.com/dee-pat/frappe-agent-kit);
Bond Management, Gita and task_list pin `v0.2.1`
(`57cb2573b7948a98a3d20e224e11ca03892c0388`), and the bench `AGENTS.md` is
retired.

## Goal

Keep agent guidance that applies to every Frappe app in one versioned repo, and
let each app pin and vendor exactly the revision it uses. Bond Management then
carries only bond-specific guidance.

Consumers today: `bond_management`, `Gita` and `task_list` in this bench. The
shared rules currently live in the bench `AGENTS.md`, which no agent loads on its
own and which Codex's GitHub review cannot see.

The kit repo is public, so `sync` and `check` need no credentials locally, in
CI or in cloud agents. It must never hold app-specific data, site names,
credentials or anything from private repos.

## Non-goals

- Forking `frappe/skills` or `frappe/frappe-ui`. Their skills stay upstream and
  are pinned straight from there.
- Personal skills (`caveman`, `writing-for-agents`). They belong in
  `~/.agents/skills`.
- Symlinks or git submodules to a shared checkout. CI, fresh clones, worktrees
  and Codex review must see plain files in the app repo.

## Layers

| Layer          | Source                                    | How an app gets it                                       |
| -------------- | ----------------------------------------- | -------------------------------------------------------- |
| Upstream       | `frappe/skills`, `frappe/frappe-ui`       | Vendored unmodified at a pinned revision (`skills.lock`) |
| Kit            | `dee-pat/frappe-agent-kit`                | Vendored unmodified at a pinned revision (`skills.lock`) |
| Kit rules      | `rules/frappe.md` in the kit              | Synced into a marked block in the app's `AGENTS.md`      |
| App            | This repo                                 | Written here                                             |
| npm-packaged   | `@playwright/cli`                         | Symlink into `node_modules`, pinned by `package.json`    |

Always-on rules cannot be a skill: a skill loads only when its description
fires. They go into each app's `AGENTS.md` as a generated block between
`<!-- BEGIN frappe-agent-kit:rules/frappe.md@<rev> -->` and the matching `END`
marker. The sync script owns the block; hand edits inside it fail the check.

## Inventory

### Moves to the kit

| Today                                                  | Kit destination              | Notes                                                                                                   |
| ------------------------------------------------------ | ---------------------------- | ------------------------------------------------------------------------------------------------------- |
| Bench `AGENTS.md` (88 lines)                           | `rules/frappe.md`            | Becomes the source; the bench file shrinks to a pointer or goes away once every app syncs the block.   |
| Root `AGENTS.md` _Frappe rules_                        | `rules/frappe.md`            | Merge with the bench rules; they overlap.                                                               |
| Root `AGENTS.md` _Migrations and invariants_, generic bullets | `rules/frappe.md`     | Patch idempotency, `after_install` bootstrapping, DB uniqueness, owned DocPerm rows.                    |
| Root `AGENTS.md` _Before you report done_, gate bullets | `rules/frappe.md`           | Observed zero exit, stale results, unavailable gate is a blocker. Domain-model sync stays in the app.   |
| Root `AGENTS.md` _Tests_, generic bullets              | `rules/frappe.md`            | Determinism, `>=` boundaries, Python vs browser ownership.                                              |
| `bond-management-migration` references (about 95%)     | `skills/frappe-migration/`   | Staged constraints, renames, expand/contract, retirement, lifecycle fixtures. Replace app names with placeholders. |
| `grilling`                                             | `skills/grilling/`           | Generalize the description's "financial" trigger to "business-rule".                                    |
| _GitHub review conversations_ in `docs/code-review.md` | `skills/pr-review-threads/`  | Its own skill: it runs on request, not every turn.                                                      |
| `e2e/AGENTS.md` _Writing specs_ items 2–4              | `rules/frappe.md` or a later `frappe-playwright` skill | Only if another app adopts Playwright.                                       |

### Stays in Bond Management

| Item                                                        | Why                                                                     |
| ----------------------------------------------------------- | ----------------------------------------------------------------------- |
| Root `AGENTS.md`: Layout, Architecture, Bond financial conventions, Attachments and secrets, Sites, Commands | Domain and environment facts.        |
| Root `AGENTS.md`: _Review guidelines_                       | Codex GitHub review reads it from the repo; keep it short and local.    |
| `frontend/AGENTS.md`, `e2e/AGENTS.md` (except shared items) | SPA and seed specifics.                                                 |
| `docs/verification.md`, `docs/domain-model.md`, `docs/testing-matrix.md` | App gates, sites, data model.                              |
| Thin `bond-management-migration`                            | Sources of truth, `migration-lifecycle.md` helper, the bond reference list for renames (`_financial_doctypes`, investor projections, seed, domain model), `Decimal` and provenance assertions; then "follow `frappe-migration`". |

### Stays upstream

`frappe-app-dev`, `code-style`, `frappe-code-review` (frappe/skills) and
`frappe-ui` (frappe/frappe-ui): already pinned in `skills.lock`.

## Pinning and sync

- `skills.lock` at the app root lists one skill per line: name, repository,
  path, revision, and optional comma-separated excludes.
- `scripts/sync-skills.sh` fetches each repository at its revision (shallow
  fetch by SHA, cached under `<bench>/.cache/agent-skills/`, the same pattern as
  the Semgrep rules in `verify.sh`) and:
  - `sync` replaces `.agents/skills/<name>/` with the upstream path, minus
    excludes;
  - `check` (default) compares each vendored folder with its pinned upstream
    copy and exits non-zero on any drift.
- To upgrade, edit the revision in `skills.lock`, run `sync`, review the diff,
  and commit both together.
- Phase 3 adds rules-block support: a `rule` line in `skills.lock` and the same
  `sync`/`check` behaviour for the `AGENTS.md` block.

## Phases

1. **Done here:** `skills.lock` and `scripts/sync-skills.sh` for the four
   upstream skills already vendored. `check` passes against the current tree.
2. **Done:** created the public kit with `rules/frappe.md`,
   `skills/frappe-migration`, `skills/grilling`, `skills/pr-review-threads` and
   `tools/sync-skills.sh`, extracted from this app and the bench file and
   scrubbed of app names, sites and data. Tagged `v0.1.0`. Verified end to end:
   the kit's own `sync-skills.sh` synced and checked all three kit skills into a
   scratch app at that revision. The kit's `tools/sync-skills.sh` is now the
   canonical copy; this app's `scripts/sync-skills.sh` should be refreshed from
   it in phase 3.
3. **Done:** the kit's `tools/sync-skills.sh` gained `rule` lines that sync
   `rules/frappe.md` between BEGIN/END markers (kit `v0.2.0`). Bond Management
   vendors that script, pins `frappe-migration`, `grilling`,
   `pr-review-threads` and the rules block in `skills.lock`, replaced its
   _Frappe rules_, generic migration, test and gate bullets with the generated
   _Shared Frappe rules_ block, thinned `bond-management-migration` to bond
   references and lifecycle-harness specifics, moved the review-thread steps to
   `pr-review-threads`, and runs `sync-skills.sh check` in `verify.sh lint`.
   Kit `v0.2.1` then trimmed the always-on rules to about 250 words and moved
   migration invariants into `frappe-migration`, so Bond's always-loaded
   `AGENTS.md` shrank instead of growing.
4. **Done:** Gita and task_list vendor `sync-skills.sh`, pin `frappe-app-dev`,
   `code-style`, `frappe-code-review`, `frappe-migration` and the rules block in
   `skills.lock`, and gained `CLAUDE.md` and `.claude/skills` links. task_list's
   stale `frappe-app-dev` and `code-style` were replaced, and its pre-commit runs
   `sync-skills.sh check`. Gita has no lint gate, so its `AGENTS.md` asks for the
   check after guidance changes. Changes are local and uncommitted in both
   repos, alongside unrelated in-progress work.
5. **Done:** the bench `AGENTS.md` is deleted. Personal process rules (spec and
   progress note, tracer bullet, dependencies, backward compatibility, branches
   and handoff) moved to `~/.codex/AGENTS.md`, with `~/.claude/CLAUDE.md` linked
   to it. Backups of the original and trimmed bench files are in the bench's
   `archived/` folder.

## Acceptance

- Every vendored skill matches its pinned revision (`sync-skills.sh check`
  exits 0 locally and in CI).
- No app's agent guidance depends on a file outside its repo.
- A rule change in the kit reaches an app only through a reviewed revision bump.
- Bond's always-loaded guidance (`AGENTS.md` plus skill descriptions) does not
  grow; moved text is replaced by the generated block, not duplicated.

## Open decisions

- **Network in the lint gate.** `check` fetches pinned revisions. CI has network;
  local runs use the cache after the first fetch. Alternative: run `check` only
  in CI.
- **Kit license:** MIT. Change it before outside apps adopt the kit if you
  prefer another.
