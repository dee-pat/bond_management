# Bond Management agent guidance

The parent `frappe-bench/AGENTS.md` contains rules shared by Frappe v16 apps.
This file contains only bond-management-specific additions and overrides. When
the two files conflict, this app-level file governs.

## Local guidance and verification

- Never install or update skills globally. App-specific skills must live under
  `.agents/skills/` in this app.
- Before changing files, running verification, investigating CI/Cypress failures,
  or reporting completion, read [verification.md](docs/verification.md). It owns
  the mandatory gate commands, evidence format, fresh-site checks, and runtime
  recovery procedures. Apply the parent's completion and CI-failure rules.

## App baseline and structure

- This is a custom Frappe Framework v16 application for bond portfolios,
  accruals, schedules, and statement/transaction attachments. Do not assume
  ERPNext is installed.
- Before environment setup, dependency changes, or deployment, read
  [.codex/context.md](.codex/context.md) for the local/CI runtime baseline.
  Check compatibility against the target Frappe v16 release and host.
- The app root is `<bench>/apps/bond_management`; this checkout is already that
  app root.
- The outer Python package is `bond_management/` and uses the import prefix
  `bond_management`.
- The Frappe module package is `bond_management/bond_management/` and uses the
  import prefix `bond_management.bond_management`. There is no third nested
  `bond_management` package.
- Before adding an import, inspect the actual package tree and nearby imports;
  prefer absolute imports and do not infer paths from names alone.
- Keep DocType controllers focused on their own DocType. Put shared logic under
  `bond_management/bond_management/utils`.

## Bond financial conventions

- Construct precision-sensitive monetary values, accrued interest, yields, and
  quantities with `Decimal` from strings rather than binary floats. Quantize
  only at the business-rule boundary with an explicit rounding mode and
  documented precision. Keep `Decimal` through calculations; convert to binary
  floats only inside a named external-library adapter or explicit JSON/clipboard
  serialization boundary, with precision regression tests.
- Preserve the existing rounding, cash-flow sign, commission, and bank-price
  conventions. Change a convention only with an explicit business decision and
  boundary tests.
- Coupon schedules are generated from issue date through maturity using the
  configured day-count convention. Preserve their period boundaries and
  coupon-date semantics.
- Principal repayment rows must be positive and unique. The latest contractual
  repayment date determines maturity, and repayment dates must align with
  coupon dates under the current Bond Master rule.
- Amortisation changes outstanding principal or the principal factor; it does
  not reduce transaction quantity unless an explicit business rule says so.
- Ledger position uses `settlement_date` as its effective date. Maturity-day
  and same-day coupon/repayment behavior use explicit pre- and post-payment
  rules; do not replace them with generic date comparisons.
- Market prices are quoted per 100 of original face value. Do not apply a
  principal factor a second time to market-price cash flows.
- Attachment-managed statement fields are server-authoritative; Desk
  `read_only` settings are not sufficient protection.
- Transaction, posting, accrual, reconciliation, and attachment mutations are
  server-authoritative. Do not use local-first optimistic state for financial
  values or durable document status; show pending/failed state until the server
  confirms the result. Optimistic UI is limited to non-financial presentation
  state and must support recovery.

## Attachments and secrets

- Keep uploaded financial documents private. Read them through Frappe's File
  APIs and storage abstraction rather than assuming a filesystem path.
- Validate actual file content and expected document structure; do not trust
  extensions, MIME types, filenames, or client-extracted values alone.
- Never return, log, persist in plain text, or include configured PDF passwords
  in exceptions. Standardize filenames only after identifying the document and
  preserve private-file semantics.
- Parsers must reject missing or conflicting identity fields instead of
  guessing. A documented legacy fallback is allowed only when the primary
  source is absent, and the primary source wins when both exist.

## Controlled Frappe integration exceptions

- `scripts/cypress-runtime.sh` may temporarily add Frappe's v16 Cypress
  dependencies to the framework manifest because Frappe's own UI runner uses
  that bootstrap. It must restore `apps/frappe/package.json` on every exit,
  never commit framework-manifest changes, and keep installed versions pinned.
- Permission-query hooks may return a SQL condition only where Frappe requires
  that hook shape. Use fixed DocType/field identifiers, escape every value with
  Frappe's database API, and never interpolate client-controlled identifiers.
- `ignore_permissions=True` is allowed for generated reports, migrations, and
  administrative invariant checks only when the caller's permission boundary is
  verified separately and the code documents that service boundary.

## App-specific migrations and permissions

- Put data patches under `bond_management/patches/` and register them in
  `bond_management/patches.txt`; apply the parent's migration rules.
- Test the registered patch sequence against representative legacy data, not
  only each patch function in isolation. Include a safe rerun and verify the
  resulting business data and indexes.
- Install manual unique indexes idempotently on both fresh installation and
  migration; test both paths alongside controller validation.
- Frappe marks an app's registered patches complete before `after_install` runs.
  Any permission, index, or other invariant that must exist on a fresh install
  must therefore also be bootstrapped by an idempotent `after_install` hook;
  verify both fresh-install and migrate paths.

## Test site and app tests

- `test_site` is the canonical site for automated server and UI tests. Use
  `dev.local` for interactive development; never run destructive tests against
  `dev.local` or another non-test site.
- Before testing, ensure `bond_management` is installed on `test_site`, migrate
  it, and enable tests with
  `bench --site test_site set-config allow_tests true`.
- Reuse an existing local `test_site`. Do not recreate, drop, or restore it
  without explicit user approval. Do not record site credentials or
  machine-specific database configuration in repository files.
- Factories may use collision-safe generated names, but test outcomes must not
  depend on their random suffixes.
- Attachment parsers need current, supported legacy, malformed, conflicting,
  encrypted, invalid-password, and non-PDF cases.
- Use stable routes, labels, roles, and data attributes. Avoid asserting CSS
  layout, SVG geometry, or internal formatter registration. Prefer visible
  controls; use `window.cur_frm` or direct `script_manager.trigger` only for a
  specifically justified client-script hook (for example, deterministic PDF
  attachment parsing where native file upload adds no useful coverage).
- When a backend field or permission is exposed through Desk, update the
  relevant form/list/workspace code and one representative Cypress smoke
  assertion; server tests own the complete permission and validation matrix.

## References

- Parent shared policy: `../../AGENTS.md`
- Project context and troubleshooting: `.codex/context.md`
- Common bench and verification commands: `.codex/commands.md`
- Framework documentation: https://docs.frappe.io/framework/user/en/introduction
