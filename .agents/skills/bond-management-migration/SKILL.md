---
name: bond-management-migration
description: Bond Management specifics for schema and data migrations. Use with frappe-migration when renaming, removing, or retyping a DocType or field, writing or retiring a patch in `patches.txt`, adding a manual index or DocPerm invariant, or deleting a deprecated code path.
---

# Bond Management Migration

Follow the `frappe-migration` skill for the recipe. This skill names where its generic steps land in this app.

## Sources of truth

- `frappe-migration` _Invariants_ and _App migrations and tests_ in [AGENTS.md](../../../AGENTS.md) own patch, index, DocPerm, and `after_install` rules.
- [migration-lifecycle.md](../../../docs/specs/migration-lifecycle.md) is the lifecycle harness: `bond_management.bond_management.tests.migration_lifecycle` with phases `fresh()`, `prepare()`, `verify()` and `requeue()`, on a temporary `bond-management-lifecycle-<32-hex-id>.localhost` site that is dropped afterwards. `requeue()` deletes Patch Logs, so it is the forced rerun that `frappe-migration` warns about.
- [verification.md](../../../docs/verification.md) owns gates and evidence; [domain-model.md](../../../docs/domain-model.md) must change with any DocType, `Link`, or `Table` change.

## References to update

On a rename, removal or retype, update every one of these in the same change, in addition to the generic list:

- `hooks.py`: `_financial_doctypes`, `permission_query_conditions` and `has_permission` (`utils/investor_permissions.py`), `extend_doctype_class` and `doc_events` (`utils/investor_shares.py`), `after_install` and `after_migrate`.
- Investor projections in `api/investor.py` and `api/investor_reports.py`, and the SPA in `frontend/`.
- Script reports, Desk form JS and the `/desk/bond-investor` workspace.
- `tests/factories.py`, `tests/pdf_factory.py`, the Playwright seed `tests/investor_ui_seed.py`, and [testing-matrix.md](../../../docs/testing-matrix.md).
- Before removing a DocType: its User Permissions, DocShares and attached private Files, keeping investor portfolio scope intact.

## Business-data assertions

Lifecycle fixtures assert migrated values as business data, not row counts: transaction amounts as `Decimal` at their stored precision, exchange-rate provenance (`Bond Exchange Rate Source` rows and manual-fallback flags), permissions, and manual indexes. Add representative legacy rows to the harness whenever a new data patch is registered.

Never run `bench trim-tables` or `bench trim-database` against `bond-management-dev.localhost` or `bond-management-test.localhost` as part of a routine gate.
