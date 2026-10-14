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

- **Additive** (new DocType, field, index, DocPerm): normal Frappe migrate handles schema; add a patch only for data or an invariant, and bootstrap invariants in `after_install` too.
- **Rename** (DocType or field): one release, `[pre_model_sync]` patch, see _Renames_.
- **Remove or retype** (field, DocType, `Link` target, `Table` ownership): expand/contract across releases, see _Expand/contract_.
- **Retire** (one-time patch, deprecated path, dead code): see _Retirement_.

## Renames

Frappe migrates the JSON after `[pre_model_sync]` patches run, so a rename patch there moves data before the new schema loads. Use `frappe.rename_doc("DocType", old, new, force=True)` for a DocType and `frappe.model.utils.rename_field.rename_field(doctype, old, new)` for a field, guarded so a rerun is a no-op. Then update every reference in the same change: controllers, `utils/`, `hooks.py` (`_financial_doctypes`, permission hooks, `doc_events`), `api/investor*.py` projections, reports, Desk JS, the SPA, tests, factories, the Playwright seed, and domain-model.md. Done when `git grep` for the old name returns only the patch.

## Expand/contract

Frappe has no down migration: rollback is restoring the pre-migrate backup. Keep each release valid for both the previous and next code.

1. **Expand.** Add the new field/DocType alongside the old one. Write both from the server; read the new one with a fallback to the old.
2. **Migrate.** A registered, idempotent, batched patch backfills the new shape from the old. Add its legacy rows to the lifecycle fixtures and test results as business data (amounts, `Decimal` precision, provenance), not only row counts.
3. **Switch.** Read only the new shape; stop writing the old one.
4. **Contract,** in a later release after every deployed site ran step 2: delete the old field from JSON. Frappe leaves the database column in place; dropping it (`bench trim-tables`) is a separate, explicitly approved operation on each site.

Done when each release passes the lifecycle sequence and no code reads the old shape.

## Retirement

A one-time data patch is retirable only after the user confirms every deployed site has run it; a fresh install marks it complete without running it. In one change: remove its `patches.txt` line and module, any `after_install`/`after_migrate` entry, its tests, its lifecycle fixtures and assertions, and the references in migration-lifecycle.md. Invariant patches (DocPerms, manual indexes) stay, because fresh installs and migrates both need them.

For deprecated code paths, find every consumer first (`git grep`, `hooks.py`, whitelisted method names called from Desk JS and the SPA, report JSON) and remove the path only when the count is zero. Done when nothing imports, routes to, or calls the removed name.

## Verify

Run the lifecycle sequence for any patch change, plus the applicable gates from verification.md, and drop the temporary site afterwards whether it passed or failed.
