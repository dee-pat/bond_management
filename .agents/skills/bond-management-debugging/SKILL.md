---
name: bond-management-debugging
description: Root-cause triage for this app. Use when a server test, Playwright spec, build, migration, or CI job fails, or when Desk or SPA behavior contradicts the expected financial or permission rule.
---

# Bond Management Debugging

Load `frappe-debugging` for the method (classify, reproduce, localize, reduce, regression test, fix, verify). This skill adds only this app's sources and clues.

## Sources of truth

- [verification.md](../../../docs/verification.md) owns gates, evidence, local runtime recovery (MariaDB, Redis, `DocType not found`, build), Playwright setup and recovery, and CI bootstrap.
- [testing-matrix.md](../../../docs/testing-matrix.md), the test rules in [AGENTS.md](../../../AGENTS.md) and [e2e/AGENTS.md](../../../e2e/AGENTS.md) own where a regression test belongs and how to write it.
- `<test site>` is `bond-management-test.localhost`; the full suites are `scripts/verify.sh server` and `ui`. Patch and install regressions also follow `bond-management-migration`.

## Clues by symptom

- **Off by a cent or a tiny fraction:** a binary float entered the calculation, or quantization happened before the business-rule boundary.
- **Wrong amount on a settlement, coupon, repayment, or maturity day:** pre- vs post-payment ordering, or a generic date comparison replacing the explicit rule.
- **Investor sees too much or too little:** `permission_query_conditions`/`has_permission` in `utils/investor_permissions.py`, `_financial_doctypes` in `hooks.py`, or User Permission/DocShare consistency in `utils/investor_shares.py`.
- **Statement save fails on exchange rates:** a conflicting value for an existing canonical `Bond Exchange Rate`; equal values are shared, conflicting ones fail the whole save by design.
- **Works on a migrated site, fails on a fresh one (or vice versa):** an invariant registered in `patches.txt` but missing from `after_install`, or the reverse.
- **PDF parse errors:** check content and identity fields, not filename or MIME. Never print, log, or include the configured PDF password in a diagnostic.
