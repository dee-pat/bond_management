# Bond Management agent guidance

The parent `frappe-bench/AGENTS.md` contains rules shared by Frappe v16 apps.
This file contains only bond-management-specific additions and overrides. When
the two files conflict, this app-level file governs.

## App baseline and structure

- This is a custom Frappe Framework v16 application for bond portfolios,
  accruals, schedules, and statement/transaction attachments. Do not assume
  ERPNext is installed.
- The local and CI development baseline is Python 3.14, Node 24, MariaDB 11.8
  or 12.3, and Redis 6 or newer. Deployment compatibility must be checked
  against the target Frappe v16 release and hosting environment.
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
  documented precision.
- Preserve the existing rounding, cash-flow sign, commission, and bank-price
  conventions. Change a convention only with an explicit business decision and
  boundary tests.
- Normalize financial dates with `frappe.utils.getdate` at system boundaries.
  Use calendar dates for issue, coupon, trade, settlement, repayment, and
  maturity rules unless a timestamp is explicitly required.
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
- Keep `Decimal` through business calculations. Convert to binary floats only
  inside a named external-library adapter or an explicit JSON/clipboard
  serialization boundary, with precision regression tests.

## App-specific migrations and permissions

- For changes that transform existing site data, add an idempotent patch under
  `bond_management/patches/`, register it in `bond_management/patches.txt`,
  and test both migration behavior and resulting business data. Do not use a
  patch for schema changes handled by normal Frappe migrations.
- Test the registered patch sequence against representative legacy data, not
  only each patch function in isolation. Include a safe rerun and verify the
  resulting business data and indexes.
- Enforce concurrency-sensitive business uniqueness at both boundaries: use
  controller validation for a useful error and a database unique index as the
  final integrity guarantee. Install manual indexes idempotently, ensure fresh
  app installation creates them too, and test both paths.
- Permission patches should update or create only the `DocPerm` rows they own.
  Do not save a parent `DocType` merely to change permissions, because that can
  validate or rewrite unrelated metadata during migration.

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
  depend on their random suffixes. Tests must be deterministic, independent,
  and rerunnable. Attachment parsers need current, supported
  legacy, malformed, conflicting, encrypted, invalid-password, and non-PDF
  cases.
- For bond rules involving `>`, `>=`, `<`, or `<=`, test greater-than,
  less-than, and equality cases and state equality behavior.
- Add Cypress tests for reports and other client-side interactions. Promise-
  returning JavaScript flows are required for testability. Larger Desk
  workflows require at least one end-to-end Cypress flow; do not introduce a
  second browser framework solely because another project mandates it.
- When a backend field or permission is exposed through Desk, update the
  relevant form/list/workspace code and Cypress coverage in the same change.
- For asynchronous Desk flows, Cypress coverage must include delayed success,
  failed requests, retry/recovery, and stale-response protection. Do not assert
  a saved, posted, reconciled, or uploaded state before the server response.
- For mutation APIs that can be retried or involve multiple writes, test
  permission failures, duplicate/retry behavior, stale-version or modified
  conflicts, and atomic rollback when one logical operation fails.

## App verification gate

- Before committing, pushing, or handing off application-code changes, run the
  relevant targeted test, its complete module, and the full server suite. A
  passing targeted test is not evidence that the full suite passes; tests must
  succeed both independently and under full-suite ordering.
- From the bench directory, run
  `apps/bond_management/scripts/verify.sh pre-push`. This shared gate runs
  pre-commit, migrates `test_site`, and runs the complete server suite. GitHub
  Actions must call the same script so local and CI commands cannot drift.
- Changes to JavaScript, reports, DocType metadata, permissions, workspaces, or
  other Desk behavior must run
  `apps/bond_management/scripts/verify.sh pre-push-ui`, which adds the complete
  headless UI suite. Set `CHROME_BIN` when `chrome` is not on `PATH`.
- The UI gate uses Frappe's Cypress runner with a bench-local cache under
  `.cache/Cypress`. `scripts/cypress-runtime.sh` pins the Frappe v16 Cypress
  dependency set, verifies package/binary compatibility, and repairs cache
  failures before the test run. Host-level Electron launch failures are
  reported without repeatedly downloading the same binary. It also clears
  Electron-as-Node and custom-binary environment overrides that make Cypress
  start incorrectly. Do not rely on a machine-global Cypress cache or bypass
  this preflight.
- `CYPRESS_VERSION` in `scripts/cypress-runtime.sh` and the GitHub Actions
  cache key must be updated together when Frappe v16 changes its supported
  Cypress release. Do not override the version in CI or reuse a cache for a
  different binary.
- Changes to patches, schema, hooks, dependencies, installation, or manual
  indexes must also be validated against a freshly installed site matching the
  GitHub Actions setup. Obtain approval before recreating or dropping a local
  site.
- CI's fresh-site bootstrap must initialize an explicit bench root, assert that
  its `sites/common_site_config.json` exists before running `bench get-app`, and
  fetch the checked-out app through a local `file://` source. Keep the bench
  initialization path, step working directories, caches, and artifact paths in
  sync.
- If a required command cannot run because a service, browser, dependency,
  site, or credential is unavailable, do not substitute an unrelated check.
  Report the exact command, blocking condition, and verification that remains
  outstanding.
- When GitHub Actions fails, inspect the exact traceback and reproduce the
  failing test both in isolation and in the full suite. Do not guess at a fix
  or weaken an assertion merely to make CI pass.
- Do not commit, push, or report a change as complete while a required check is
  failing or unavailable. State exactly which checks ran and their results.
- For a multi-phase feature, record the intended slice and verification steps
  before implementation; for a small bug fix, a focused issue note and
  regression test are sufficient.

## References

- Parent shared policy: `../../AGENTS.md`
- Project context and troubleshooting: `.codex/context.md`
- Common bench and verification commands: `.codex/commands.md`
- Framework documentation: https://docs.frappe.io/framework/user/en/introduction
