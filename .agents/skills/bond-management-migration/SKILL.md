---
name: bond-management-migration
description: Schema and data migrations for this app. Use when renaming, removing, or retyping a DocType or field, writing or retiring a patch in `patches.txt`, adding a manual index or DocPerm invariant, or deleting a deprecated code path.
---

# Bond Management Migration

Change shape in _expand/contract_ phases so every deployed site migrates safely, then retire what is left behind.

## Sources of truth

- [AGENTS.md](../../../AGENTS.md) "App-specific migrations and permissions" owns patch, index, DocPerm, and `after_install` rules.
- [migration-lifecycle.md](../../../docs/specs/migration-lifecycle.md) owns the registered-patch regression on a temporary site, its representative legacy data, and cleanup.
- [verification.md](../../../docs/verification.md) owns gates and evidence; [domain-model.md](../../../docs/domain-model.md) must change with any DocType, `Link`, or `Table` change.

## Pick the branch

- **Additive** (new DocType, field, index, DocPerm): normal Frappe migrate handles schema; add a patch only for data or an invariant, and bootstrap invariants in `after_install` too. Model sync drops manual indexes that DocField metadata cannot declare, so also reapply them idempotently from `after_migrate`; a logged patch never runs again. A new field with a default on an existing Single DocType is the schema exception: sync stores no `tabSingles` value and defaults apply only when the Single has no stored values at all, so established sites read `None`. Backfill a business default with an idempotent data patch and test it on a populated site.
- **Rename** (DocType or field): one release, one patch, see _Renames_, only when the deployment stops every previous-release worker before migrate and a rollback restores the pre-migrate backup. Otherwise old and new code write different columns or query a renamed table, so treat the rename as a retype and use _Expand/contract_.
- **Remove or retype** (field, DocType, `Link` target, `Table` ownership): expand/contract across releases, see _Expand/contract_.
- **Retire** (one-time patch, deprecated path, dead code): see _Retirement_.

## Renames

The two renames run on opposite sides of model sync, each in a patch whose rerun is a no-op:

- **DocType:** `frappe.rename_doc("DocType", old, new, force=True)` in a `[pre_model_sync]` patch, so the table and links move before the renamed JSON syncs. `rename_doc` loads the old DocType first and raises when it is gone, so guard on existence: rename when only the old exists, skip when only the new exists, and throw when both or neither exist. Test a forced rerun. `DocType.after_rename` skips renaming files and folders while `frappe.flags.in_patch` is set, so rename the module folder, JSON, controller, test files, and controller class in the repository in the same change.
- **Field:** `frappe.model.utils.rename_field.rename_field(doctype, old, new)` in a `[post_model_sync]` patch. It requires the synced DocType and silently returns when the new field is missing, so a pre-sync call copies nothing. It copies every row into the new column with an unconditional `UPDATE`, and Frappe leaves the old column in place, so a forced rerun (the lifecycle `requeue()` deletes Patch Logs) overwrites values the app has since written with stale legacy ones. Patch Log is not a guard: skip the call when a durable marker says the copy already ran, for example a namespaced `frappe.db.set_global` key that cannot match a fieldname, set in the same patch after the copy. Test that a forced rerun after editing the new field on a migrated row keeps the edit. Model sync adds a new `unique` field as `ADD COLUMN ... UNIQUE` with its default, which fails on a populated table for NOT NULL types (`Check`, `Int`, `Currency`, `Float`, `Percent`) or any field with a default; ship the new field without `unique`, copy and check for duplicates, and enforce uniqueness in a later release, with a populated lifecycle case. For a `Table` or `Table MultiSelect` field, do not call `rename_field`: the parent table has no column, so default validation returns early, and with `validate=False` it updates `parentfield` without a `parenttype` predicate, moving the children of every parent that reuses the child DocType. Update the child table where `parenttype` is this DocType and `parentfield` is the old name (a rerun matches nothing), call `update_property_setters` from the same module if any exist, and test that the children load under the new field while another parent's children stay attached. For an `Attach` or `Attach Image` field, `rename_field` leaves `File.attached_to_field` on the old name, and a later private/public change writes the new URL through that stale name; in the same patch update `File` rows for this DocType from the old fieldname to the new one (idempotent by its `WHERE`) and test a private attachment.

Verify the migrated business data on representative legacy rows, not just the absence of errors. Then update every reference in the same change: controllers, `utils/`, `hooks.py` (`_financial_doctypes`, permission hooks, `doc_events`), `api/investor*.py` projections, reports, Desk JS, the SPA, tests, factories, the Playwright seed, and domain-model.md. Done when `git grep` for the old name returns only the patch and its lifecycle fixtures and assertions, and `git ls-files` lists no path containing its snake_case form.

## Expand/contract

Frappe has no down migration: rollback is restoring the pre-migrate backup. Keep each release valid for both the previous and next code.

1. **Expand.** Add the new field/DocType alongside the old one. Write both from the server; read the new one with a fallback to the old.
2. **Migrate.** A registered, idempotent, batched patch backfills the new shape from the old. Add its legacy rows to the lifecycle fixtures and test results as business data (amounts, `Decimal` precision, provenance), not only row counts.
3. **Switch.** Read only the new shape; keep writing both, because previous-release workers or a code rollback without a database restore may still read the old one.
4. **Contract,** in a later release after every deployed site ran step 2 and no release that reads the old shape can still run, stop writing it and remove it:
   - **Field:** delete it from the DocType JSON. Frappe leaves the database column in place; `bench trim-tables` drops orphan columns.
   - **DocType:** first move or delete what still references it (`Link` and `Table` fields, User Permissions, DocShares, attached Files, reports, workspace entries, `_financial_doctypes` and other `hooks.py` entries), then delete its module folder. `bench migrate` removes the orphan `DocType` record but keeps the table; `bench trim-database` drops it.
   - Both trim commands are destructive and site-wide (`trim-database` drops every deleted DocType's table, other apps' included). Run each with `--dry-run` per site, show the user the list, and run it for real only with their explicit approval, never on the persistent dev or test site as part of a routine gate.

Done when each release passes the lifecycle sequence and no code reads the old shape.

## Retirement

A one-time data patch is retirable only after the user confirms every deployed site has run it; a fresh install marks it complete without running it. In one change: remove its `patches.txt` line and module, any `after_install`/`after_migrate` entry, its tests, its lifecycle fixtures and assertions, and the references in migration-lifecycle.md. Invariant patches (DocPerms, manual indexes) stay, because fresh installs and migrates both need them.

For deprecated code paths, find every consumer first (`git grep`, `hooks.py`, whitelisted method names called from Desk JS and the SPA, report JSON) and remove the path only when the count is zero. Done when nothing imports, routes to, or calls the removed name.

## Verify

A fresh install of the current tree creates only the new schema and marks every patch complete, so for a rename or retype, lifecycle `prepare()` must recreate the old shape (the old `DocType` record and its table, or the old column) with direct writes and DDL, load legacy rows into it, and assert it exists before the first migrate. A Single DocType has no table: recreate the old `(doctype, field, value)` row in `tabSingles`, delete any new-field row, and assert the migrated business value. For a DocType rename, first remove the new `DocType` record and table, then assert only the old one exists, because the rename guard throws when both exist; otherwise the guards skip and the test passes without migrating anything.

Run the lifecycle sequence for any patch change, plus the applicable gates from verification.md, and drop the temporary site afterwards whether it passed or failed.
