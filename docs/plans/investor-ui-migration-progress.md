# Investor UI Migration Progress

Last updated: 2026-08-26
Specification: [investor-ui-migration.md](../specs/investor-ui-migration.md)
Current phase: Phase 7 — Pilot
Overall status: Phase 7 in progress; pilot acceptance pending

This file records execution state and evidence. Product, architecture and acceptance decisions belong in the specification.

## Status legend

- `Pending`: no implementation started.
- `In progress`: current implementation slice.
- `Blocked`: cannot proceed; the blocker and required decision are recorded below.
- `Complete`: every completion criterion and required gate passed for the current change.

## Phase summary

| Phase | Slice                                | Status      | Evidence                                                                   |
| ----- | ------------------------------------ | ----------- | -------------------------------------------------------------------------- |
| 0     | Decision record and baseline         | Complete    | Specification and this tracker created; documentation lint recorded below. |
| 1     | Compatibility and toolchain          | Complete    | Local and fresh-site gates recorded below.                                 |
| 2     | Coexistence shell                    | Complete    | Route matrix, responsive navigation and complete gates recorded below.     |
| 3     | Transaction tracer bullet            | Complete    | API projections, responsive routes and complete gates recorded below.      |
| 4     | Remaining read-only records          | Complete    | All four record surfaces and complete gates recorded below.                |
| 5     | Reports                              | Complete    | Both report surfaces and complete gates recorded below.                    |
| 6     | Parity and hardening                 | Complete    | Shared hardening and clean-site verification recorded below.               |
| 7     | Pilot                                | In progress | Acceptance cycle and rollback evidence tracked below.                      |
| 8     | Cutover                              | Pending     | —                                                                          |
| 9     | Legacy investor workspace retirement | Pending     | Separate release.                                                          |

## Completed slice: Phase 1

Objective: prove Vue 3, Frappe UI, Playwright and the existing Frappe v16/Cypress stack can coexist in a production-shaped build before feature screens are added.

### Planned work

- [x] Record the intended Phase 1 file and command changes before implementation.
- [x] Scaffold root package delegation, `frontend/`, `e2e/` and Playwright configuration.
- [x] Select and pin exact Frappe UI, Vue, Vite and Playwright versions compatible with Node 24 and Frappe v16.
- [x] Build the generated assets and website entry through `bench build --app bond_management`.
- [x] Add the feature-gated route and minimum website boot context needed for a real same-origin session/CSRF request.
- [x] Add one explicit read-only bootstrap or health endpoint with role and feature checks.
- [x] Add deterministic investor user/portfolio seed support for `test_site`.
- [x] Add Playwright authentication state plus desktop Chromium and Pixel 7 shell tests.
- [x] Add a Playwright mode to `scripts/verify.sh`; make `pre-push-ui` run all active UI suites.
- [x] Add a separate Playwright CI job with browser caching and failure artifacts.
- [x] Keep the existing Cypress job and all seven Cypress specs unchanged.

### Intended Phase 1 implementation slice — 2026-08-24

The first implementation slice will cross the source, server, build, browser,
and CI layers without adding an investor record surface:

- Add the root package delegation and `frontend/` Vue 3/TypeScript scaffold.
- Pin `frappe-ui` `1.0.0-beta.25`, Vue `3.5.16`, Vue Router `4.5.1`, Vite
  `5.4.10`, `@vitejs/plugin-vue` `5.1.4`, TypeScript `5.8.3`, and
  `@playwright/test` `1.57.0`; verify the generated lockfiles in the current
  Node 24 environment.
- Add `bond_management/www/bond-investor.py`, the generated SPA entry path,
  the nested website route rule, and a site-level feature gate that defaults
  to disabled and preserves `/desk/bond-investor` as the fallback.
- Add the read-only `get_bootstrap` API with session, role, feature, portfolio
  projection, and attachment-omission tests. Add an idempotent administrative
  test-site seed helper for the investor role, assigned portfolio, and user
  permission; credentials remain caller-provided.
- Add the authenticated Playwright setup, desktop/mobile shell smoke tests,
  local verification mode, and a separate CI job with browser caching and
  failure artifacts. The existing Cypress specs and ownership remain intact.

Commands to record after implementation are the frontend lint/typecheck/build,
`bench build --app bond_management`, targeted and complete server tests, the
focused and complete Playwright suites, the existing Cypress suite, both shared
verification modes, and fresh-site CI-shaped verification. Generated frontend
assets and the copied website entry remain build output and are ignored.

### Completion evidence

- [x] Frontend install, lint, typecheck and production build exit 0.
- [x] Focused Playwright shell test exits 0 on desktop and mobile.
- [x] Complete Playwright suite exits 0.
- [x] Existing complete Cypress suite exits 0.
- [x] `apps/bond_management/scripts/verify.sh pre-push` exits 0.
- [x] `apps/bond_management/scripts/verify.sh pre-push-ui` exits 0.
- [x] CI-shaped fresh-site install and build exit 0.
- [x] Local-versus-CI differences are recorded.

## Completed slice: Phase 2

Objective: complete the coexistence shell around the already proven route and
bootstrap seam without changing the pilot login or Apps screen fallback.

### Planned work

- [x] Record the Home navigation parity inventory before implementation.
- [x] Add persistent responsive navigation for every included investor surface.
- [x] Give every navigation destination a stable nested route and intentional pre-surface state.
- [x] Complete disabled, guest, unauthorized, investor, manager and Administrator website-route coverage.
- [x] Add desktop deep-link/refresh, session-expiry and mobile navigation Playwright coverage.
- [x] Keep `/desk/bond-investor` as the login and Apps screen route during pilot.

### Intended Phase 2 implementation slice — 2026-08-24

This slice will reuse the Phase 1 feature, role, bootstrap and nested-route seams
and finish the common shell only. It will add one navigation contract shared by
the router and responsive UI, explicit placeholder states for record/report
routes that belong to later phases, server route-matrix tests, and focused
desktop/mobile Playwright flows. It will not add record queries, report data,
financial calculations, mutation controls, or change legacy Desk redirects.

### Home navigation parity inventory

Evidence source: the standard `Bond Investor` Workspace and Workspace Sidebar.

| Order | Investor label        | Legacy destination      | SPA route                         | Phase 2 state           |
| ----- | --------------------- | ----------------------- | --------------------------------- | ----------------------- |
| 1     | Home                  | Bond Investor Workspace | `/bond-investor`                  | Shell/bootstrap status  |
| 2     | Bond Transactions     | Bond Transaction list   | `/bond-investor/transactions`     | Intentional placeholder |
| 3     | Bond Statements       | Bond Statement list     | `/bond-investor/statements`       | Intentional placeholder |
| 4     | Bond Master           | Bond Master list        | `/bond-investor/bonds`            | Intentional placeholder |
| 5     | Bond Market Dates     | Bond Market Date list   | `/bond-investor/market-dates`     | Intentional placeholder |
| 6     | Bond Exchange Rates   | Bond Exchange Rate list | `/bond-investor/exchange-rates`   | Intentional placeholder |
| 7     | Portfolio Performance | Portfolio Performance   | `/bond-investor/performance`      | Intentional placeholder |
| 8     | Bond Yield Comparison | Bond Yield Comparison   | `/bond-investor/yield-comparison` | Intentional placeholder |

The order and plural investor-facing labels follow the Workspace shortcuts.
The SPA adds `Home`, matching the Workspace Sidebar. Field, filter and result
parity remains owned by each later surface slice.

## Surface parity inventory

Fill each row before implementing that surface. Link the inventory or acceptance note in the Evidence column; avoid copying detailed field lists into this tracker.

| Surface               | Inventory | Implementation | Server tests | Playwright desktop/mobile | Acceptance evidence                        |
| --------------------- | --------- | -------------- | ------------ | ------------------------- | ------------------------------------------ |
| Home navigation       | Complete  | Complete       | Complete     | Complete                  | Phase 2 inventory and verification below.  |
| Bond Transactions     | Complete  | Complete       | Complete     | Complete                  | Phase 3 inventory and verification below.  |
| Bond Statements       | Complete  | Complete       | Complete     | Complete                  | Phase 4a inventory and verification below. |
| Bond Master           | Complete  | Complete       | Complete     | Complete                  | Phase 4b inventory and verification below. |
| Bond Market Dates     | Complete  | Complete       | Complete     | Complete                  | Phase 4c inventory and verification below. |
| Bond Exchange Rates   | Complete  | Complete       | Complete     | Complete                  | Phase 4d inventory and verification below. |
| Portfolio Performance | Complete  | Complete       | Complete     | Complete                  | Phase 5a inventory and verification below. |
| Bond Yield Comparison | Complete  | Complete       | Complete     | Complete                  | Phase 5b inventory and verification below. |

## Completed slice: Phase 3

Objective: deliver the transaction tracer bullet from the assigned-portfolio
bootstrap through read-only transaction list and detail routes.

### Planned work

- [x] Record the Bond Transaction Desk parity inventory before implementation.
- [x] Record the explicit list/detail API and permission contracts.
- [x] Add permission-scoped list/detail APIs with allow-listed attachment projections.
- [x] Add responsive list/detail routes with loading, empty, failed and retry states.
- [x] Add deterministic transaction browser fixtures and desktop/mobile Playwright flows.
- [x] Run focused and complete server, frontend, Playwright and shared UI gates.

### Intended Phase 3 implementation slice — 2026-08-24

This slice will add two allow-listed GET methods to the existing investor API,
one paginated transaction list route, and one read-only detail route. It will
reuse the existing portfolio User Permission and DocType permission hooks, and
will deny an unreadable or unknown direct record with the same permission
failure. It will not add transaction mutations, uploads, generic client
filters, new calculations, schema, permissions, hooks or dependencies.

### Bond Transaction Desk parity inventory

Evidence source: the standard `Bond Transaction` DocType metadata. There is no
app-owned list-view override, so the standard Desk list behavior applies.

- Row title: Settlement Date, with Transaction Reference retained as the stable
  record identifier and detail route key.
- List fields, in metadata order: Transaction Type, Portfolio Name, ISIN, Trade
  Date, Quantity/ Face Value and Price.
- Standard filter: Portfolio Name. The SPA presents `All assigned portfolios`
  plus only the portfolio choices returned by bootstrap; it does not expose
  Desk's generic arbitrary-field filter builder.
- Default sorting: Creation descending. The API adds Name descending as a
  deterministic tie-breaker without changing the visible order contract.
- Page length: 20 by default, with an allow-listed maximum of 50.
- Detail fields, in form order after layout fields are removed: Transaction
  Type, Portfolio Name, ISIN, Bond Name, Account Number, Transaction Reference,
  Trade Date, Settlement Date, Quantity/ Face Value, Price, Principal,
  Commission %, Accrued Interest Calculated, Accrued Interest Paid, Currency,
  Maturity Date, Coupon frequency, Coupon Rate %, Face Value Per Unit, Issue
  Date, Day Count Convention, Commission Amount, Settlement Amount and
  Transaction Amount.
- Attachment access: assigned investors may view/download the private PDF from
  transaction detail only. List rows expose no attachment URL or file actions.
  Hidden PDF Portfolio Override, file metadata and every
  create/edit/delete/upload action remain omitted.
- View states: initial loading; empty portfolio assignment; empty filtered
  result; failed request with Retry; paginated results; read-only detail;
  unreadable/missing detail; and expired-session redirect preserving the full
  list or detail route.

### Transaction API contracts

`GET bond_management.bond_management.api.investor.get_transactions`

- Inputs: optional `portfolio` string; optional non-negative `start` integer
  defaulting to `0`; optional `page_length` integer defaulting to `20` and
  capped at `50`. No arbitrary filter, field or sort input is accepted.
- Response: `{ data, pagination }`, where every row contains only `name`,
  `settlement_date`, `transaction_type`, `portfolio_name`, `isin`, `trade_date`,
  `quantity_face_value` and `price`; pagination contains `start`, `page_length`
  and `has_more`. List rows omit attachment URLs.
- Permission behavior: an investor without assignments receives an empty page;
  an omitted portfolio searches all readable assigned portfolios; an explicit
  unreadable portfolio is rejected before the query. Managers and Administrator
  retain their normal DocType and User Permission behavior.

`GET bond_management.bond_management.api.investor.get_transaction`

- Input: required non-empty `name` string.
- Response: `{ transaction }`, containing the visible detail fields listed above
  plus the permission-scoped private PDF URL.
- Permission behavior: the query uses normal read permissions. An unreadable or
  unknown name returns the same permission failure, preventing record-existence
  disclosure across portfolios.

### Desktop/mobile acceptance flow

The seeded investor opens the list, sees only the transaction in their assigned
portfolio, filters to that portfolio, and opens its detail route. Desktop checks
the configured list headers and representative formatted values; Pixel 7 checks
the same record and detail route without horizontal viewport overflow. Server
tests, rather than the browser, own the cross-portfolio denial matrix and exact
response projection.

## Completed slice: Phase 4a — Bond Statements

Objective: deliver the first remaining read-only record surface through a
permission-scoped statement list and detail route.

### Planned work

- [x] Record the Bond Statement Desk parity inventory before implementation.
- [x] Record the explicit list/detail API and permission contracts.
- [x] Add permission-scoped list/detail APIs with attachment-free projections.
- [x] Add responsive list/detail routes with loading, empty, failed and retry states.
- [x] Add deterministic statement browser fixtures and desktop/mobile Playwright flows.
- [x] Run focused and complete server, frontend, Playwright and shared UI gates.

### Intended Phase 4a implementation slice — 2026-08-24

This slice will add two allow-listed GET methods to the existing investor API,
one paginated statement list route, and one read-only detail route. It will
reuse the existing portfolio User Permission and Bond Statement permission
hooks, and will deny an unreadable or unknown direct record with the same
permission failure. It will not add statement mutations, uploads, PDF parsing,
financial calculations, schema, permissions, hooks or
dependencies.

### Bond Statement Desk parity inventory

Evidence source: the standard `Bond Statement` DocType metadata and its
app-owned list formatter.

- Row title: Statement Date, with the generated statement name retained as the
  stable record identifier and detail route key.
- List fields, in metadata order: Portfolio Name and Reconciliation Status.
  The SPA retains the list formatter's status meaning with a visible status
  badge rather than reproducing Desk markup.
- Standard filters: Reconciliation Status. The SPA also presents Portfolio Name
  as an assignment-aware filter, consistent with the transaction surface; its
  choices remain limited to bootstrap portfolios.
- Default sorting: Creation descending. The API adds Name descending as a
  deterministic tie-breaker without changing the visible order contract.
- Page length: 20 by default, with the shared allow-listed maximum of 50.
- Detail fields, in form order after layout fields are removed: Portfolio Name,
  Statement Date, Market Price Posting, Reconciliation Status and Bond
  Statement Details. Each visible holding row contains ISIN, Quantity,
  Principal Factor, Market Price and Currency.
- Attachment access: assigned investors may view/download the statement PDF and
  Quantity Reconciliation Report from statement detail. File metadata and every
  create/edit/delete/upload action remain omitted.
- View states: initial loading; empty portfolio assignment; empty filtered
  result; failed request with Retry; paginated results; read-only detail;
  unreadable/missing detail; and expired-session redirect preserving the full
  list or detail route.

### Statement API contracts

`GET bond_management.bond_management.api.investor.get_statements`

- Inputs: optional `portfolio` string; optional `reconciliation_status` in
  `Matched` or `Mismatched`; optional non-negative `start` integer defaulting to
  `0`; optional `page_length` integer defaulting to `20` and capped at `50`.
  No arbitrary filter, field or sort input is accepted.
- Response: `{ data, pagination }`, where every row contains only `name`,
  `statement_date`, `portfolio_name` and `reconciliation_status`; pagination
  contains `start`, `page_length` and `has_more`.
- Permission behavior: an investor without assignments receives an empty page;
  an omitted portfolio searches all readable assigned portfolios; an explicit
  unreadable portfolio is rejected before the query. Managers and Administrator
  retain their normal DocType and User Permission behavior.

`GET bond_management.bond_management.api.investor.get_statement`

- Input: required non-empty `name` string.
- Response: `{ statement }`, containing visible parent fields, statement PDF
  URL and reconciliation-report URL plus `bond_statement_details`; each child row contains the five
  visible holding fields listed above.
- Permission behavior: the parent query uses normal read permissions. An
  unreadable or unknown name returns the same permission failure, preventing
  record-existence disclosure across portfolios. Child rows are projected only
  after the readable parent has been resolved.

### Desktop/mobile acceptance flow

The seeded investor opens the statement list, sees only the statement in their
assigned portfolio, filters by that portfolio and Matched status, and opens its
detail route. Desktop checks the configured list headers, status and holding
projection; Pixel 7 checks the same statement and detail route without
horizontal viewport overflow. Server tests own the cross-portfolio denial
matrix and exact allow-listed file projections.

## Completed slice: Phase 4b — Bond Master

Objective: deliver the shared Bond Master reference catalog through a
permission-scoped list and read-only detail route.

### Planned work

- [x] Record the Bond Master Desk parity inventory before implementation.
- [x] Record the explicit list/detail API and permission contracts.
- [x] Add permission-scoped list/detail APIs with allow-listed projections.
- [x] Add responsive list/detail routes with loading, empty, failed and retry states.
- [x] Extend the deterministic browser fixture and add desktop/mobile Playwright flows.
- [x] Run focused and complete server, frontend, Playwright and shared UI gates.

### Intended Phase 4b implementation slice — 2026-08-24

This slice will add two allow-listed GET methods to the existing investor API,
one paginated Bond Master list route and one read-only detail route. Bond Master
is shared security reference data rather than portfolio-owned data, so users
with the approved investor application role will see the catalog permitted by
normal Bond Master read permissions even when they have no portfolio
assignment. It will not add bond mutations, schedule recalculation, arbitrary
client filters, financial calculations, schema, permissions, hooks or
dependencies.

### Bond Master Desk parity inventory

Evidence source: the standard `Bond Master` DocType metadata and its child
schedule metadata. There is no app-owned list-view override.

- Row title: ISIN, which is also the stable document name and detail route key.
- List fields, in metadata order: Bond Name, ISIN, Currency and Issue Date.
- Standard filters: none configured. The SPA does not expose Desk's generic
  arbitrary-field filter builder.
- Default sorting: Creation descending. The API adds Name descending as a
  deterministic tie-breaker without changing the visible order contract.
- Page length: 20 by default, with the shared allow-listed maximum of 50.
- Detail fields, in form order after layout fields are removed: Bond Name,
  ISIN, Issue Date, First Coupon Date, Face Value Per Unit, Coupon Frequency,
  Bond Type, Maturity Date, Currency, Coupon Rate %, Withholding Tax %, Day
  Count Convention, Quantity Change, Principal Schedule and Coupon Schedule.
- Each visible principal row contains Repayment Date, Principal Units and
  Repayment %. Each visible coupon row contains Coupon Date, Period Start,
  Period End and Coupon Factor.
- Explicit omissions: document and child-row metadata, schedule editing and
  recalculation controls, and every create/edit/delete/import/rename action.
- View states: initial loading; empty catalog; failed request with Retry;
  paginated results; read-only detail; unavailable/missing detail; and
  expired-session redirect preserving the full list or detail route.

### Bond Master API contracts

`GET bond_management.bond_management.api.investor.get_bonds`

- Inputs: optional non-negative `start` integer defaulting to `0`; optional
  `page_length` integer defaulting to `20` and capped at `50`. No arbitrary
  filter, field or sort input is accepted.
- Response: `{ data, pagination }`, where every row contains only `name`,
  `bond_name`, `isin`, `currency` and `issue_date`; pagination contains
  `start`, `page_length` and `has_more`.
- Permission behavior: the query uses normal Bond Master read permissions.
  Portfolio User Permissions do not filter this shared catalog. Guest,
  disabled-feature and unapproved-role requests remain rejected by the common
  investor application gate.

`GET bond_management.bond_management.api.investor.get_bond`

- Input: required non-empty `name` string.
- Response: `{ bond }`, containing exactly the 13 scalar fields and the two
  child schedules listed above. Each child row contains only its visible
  schedule fields.
- Permission behavior: the parent query uses normal read permissions. An
  unknown or unreadable name returns the same permission failure. Child rows
  are projected only after the readable parent has been resolved.

### Desktop/mobile acceptance flow

The seeded investor opens the Bond Master list without relying on portfolio
assignment, sees the deterministic test bond and opens its detail route.
Desktop checks the configured list headers, representative formatted values
and both schedule projections; Pixel 7 checks the same bond and detail route
without horizontal viewport overflow. Server tests own the exact projection,
role/feature matrix, pagination boundaries and metadata omission.

## Completed slice: Phase 4c — Bond Market Dates

Objective: deliver the shared Bond Market Date reference history through a
permission-scoped list and read-only detail route, including the existing yield
curve meaning.

### Planned work

- [x] Record the Bond Market Date Desk parity inventory before implementation.
- [x] Record the explicit list/detail API and permission contracts.
- [x] Add permission-scoped list/detail APIs with allow-listed projections.
- [x] Add responsive list/detail routes with loading, empty, failed and retry states.
- [x] Preserve the visible yield curve from server-provided values without client financial recalculation.
- [x] Extend the deterministic browser fixture and add desktop/mobile Playwright flows.
- [x] Run focused and complete server, frontend, Playwright and shared UI gates.

### Intended Phase 4c implementation slice — 2026-08-24

This slice will add two allow-listed GET methods to the existing investor API,
one paginated Bond Market Date list route and one read-only detail route. Bond
Market Date is shared security reference data rather than portfolio-owned data,
so users with the approved investor application role will see the history
permitted by normal Bond Market Date read permissions even when they have no
portfolio assignment. The detail will render its existing yield curve from
persisted server-provided yields and weighted repayment timing; the client will
only calculate presentation coordinates. This slice will not add market-data
mutations, recalculation, cash-flow copying, arbitrary client filters, new
financial calculations, schema, permissions, hooks or dependencies.

### Bond Market Date Desk parity inventory

Evidence source: the standard `Bond Market Date` DocType metadata, its `Bond
Market Prices` child metadata and the app-owned Desk form script. There is no
app-owned list-view override.

- Row title: Date, with the generated market-date name retained as the stable
  record identifier and detail route key.
- List fields: Date. No additional fields are marked for the standard Desk list.
- Standard filters: none configured. The SPA does not expose Desk's generic
  arbitrary-field filter builder.
- Default sorting: Creation descending. The API adds Name descending as a
  deterministic tie-breaker without changing the visible order contract.
- Page length: 20 by default, with the shared allow-listed maximum of 50.
- Detail fields, in form order after layout fields are removed: Date, Bond
  Market Prices and Yield Curve.
- Each visible market-price row contains ISIN, Principal Factor, Market Price,
  Currency, Future XIRR, Weighted Average Principal Repayment Date and Maturity
  Date. The hidden persisted Weighted Average Principal Repayment Years is
  returned only as the yield curve's horizontal coordinate and is not displayed
  as another row field.
- Yield curve: group points by Currency; plot Future XIRR against Weighted
  Average Principal Repayment Years; retain ISIN and weighted repayment date in
  each accessible point label. Values remain server-authoritative.
- Explicit omissions: child-row and document metadata, the hidden years value
  as a standalone visible field, cash-flow clipboard actions, editing,
  recalculation and every create/delete/import/rename action.
- View states: initial loading; empty history; failed request with Retry;
  paginated results; read-only detail; empty market-price and yield-curve
  states; unavailable/missing detail; and expired-session redirect preserving
  the full list or detail route.

### Bond Market Date API contracts

`GET bond_management.bond_management.api.investor.get_market_dates`

- Inputs: optional non-negative `start` integer defaulting to `0`; optional
  `page_length` integer defaulting to `20` and capped at `50`. No arbitrary
  filter, field or sort input is accepted.
- Response: `{ data, pagination }`, where every row contains only `name` and
  `date`; pagination contains `start`, `page_length` and `has_more`.
- Permission behavior: the query uses normal Bond Market Date read permissions.
  Portfolio User Permissions do not filter this shared history. Guest,
  disabled-feature and unapproved-role requests remain rejected by the common
  investor application gate.

`GET bond_management.bond_management.api.investor.get_market_date`

- Input: required non-empty `name` string.
- Response: `{ market_date }`, containing exactly `date` and
  `bond_market_prices`. Each child row contains only `isin`, `principal_factor`,
  `market_price`, `currency`, `future_xirr`,
  `weighted_avg_repayment_date`, `weighted_avg_repayment_years` and
  `maturity_date`.
- Permission behavior: the parent query uses normal read permissions. An
  unknown or unreadable name returns the same permission failure. Child rows
  are projected only after the readable parent has been resolved.

### Desktop/mobile acceptance flow

The seeded investor opens the Bond Market Date list without relying on
portfolio assignment, sees the deterministic test date and opens its detail
route. Desktop checks the date, configured child columns, representative
formatted values, currency series and accessible yield point; Pixel 7 checks
the same market date and detail route without horizontal viewport overflow.
Server tests own the exact projection, role/feature matrix, pagination
boundaries and metadata omission.

## Completed slice: Phase 4d — Bond Exchange Rates

Objective: deliver the shared Bond Exchange Rate reference history through a
permission-scoped list and read-only detail route while preserving persisted
rate and reciprocal-rate values.

### Planned work

- [x] Record the Bond Exchange Rate Desk parity inventory before implementation.
- [x] Record the explicit list/detail API and permission contracts.
- [x] Add permission-scoped list/detail APIs with allow-listed projections.
- [x] Add responsive list/detail routes with loading, empty, failed and retry states.
- [x] Keep persisted Rate and Reverse Rate values server-authoritative.
- [x] Extend the deterministic browser fixture and add desktop/mobile Playwright flows.
- [x] Run focused and complete server, frontend, Playwright and shared UI gates.

### Intended Phase 4d implementation slice — 2026-08-24

This slice will add two allow-listed GET methods to the existing investor API,
one paginated Bond Exchange Rate list route and one read-only detail route. Bond
Exchange Rate is shared reference data rather than portfolio-owned data, so
users with the approved investor application role will see the history
permitted by normal Bond Exchange Rate read permissions even when they have no
portfolio assignment. The client will format persisted Rate and Reverse Rate
values without recalculating either value. This slice will not add exchange-rate
mutations, reciprocal synchronization, arbitrary client filters, new financial
calculations, schema, permissions, hooks or dependencies.

### Bond Exchange Rate Desk parity inventory

Evidence source: the standard `Bond Exchange Rate` DocType metadata and its
app-owned Desk form script. There is no app-owned list-view override.

- Row title: From Currency, with the generated exchange-rate name retained as
  the stable record identifier and detail route key.
- List fields, in metadata order: Rate Date, From Currency, To Currency, Rate
  and Reverse Rate.
- Standard filters: none configured. The SPA does not expose Desk's generic
  arbitrary-field filter builder.
- Default sorting: Rate Date descending. The API adds Name descending as a
  deterministic tie-breaker without changing the visible order contract.
- Page length: 20 by default, with the shared allow-listed maximum of 50.
- Detail fields, in form order after layout fields are removed: Rate Date, From
  Currency, To Currency, Source, Rate, Reverse Rate and Statement. The Statement
  reference is shown only when the caller may read that portfolio-owned
  statement; otherwise the field remains present with an empty value.
- Persisted values: Rate remains target-currency units for one source-currency
  unit; Reverse Rate remains source-currency units for one target-currency unit.
  The server controller owns reciprocal synchronization; the SPA only formats
  returned values to the DocType's 12-place precision.
- Explicit omissions: unreadable cross-portfolio Statement identifiers,
  document metadata, reciprocal editing and synchronization controls, and every
  create/edit/delete/import/rename action.
- View states: initial loading; empty history; failed request with Retry;
  paginated results; read-only detail; unavailable/missing detail; and
  expired-session redirect preserving the full list or detail route.

### Bond Exchange Rate API contracts

`GET bond_management.bond_management.api.investor.get_exchange_rates`

- Inputs: optional non-negative `start` integer defaulting to `0`; optional
  `page_length` integer defaulting to `20` and capped at `50`. No arbitrary
  filter, field or sort input is accepted.
- Response: `{ data, pagination }`, where every row contains only `name`,
  `rate_date`, `from_currency`, `to_currency`, `rate` and `reverse_rate`;
  pagination contains `start`, `page_length` and `has_more`.
- Permission behavior: the query uses normal Bond Exchange Rate read
  permissions. Portfolio User Permissions do not filter this shared history.
  Guest, disabled-feature and unapproved-role requests remain rejected by the
  common investor application gate.

`GET bond_management.bond_management.api.investor.get_exchange_rate`

- Input: required non-empty `name` string.
- Response: `{ exchange_rate }`, containing exactly `rate_date`,
  `from_currency`, `to_currency`, `source`, `rate`, `reverse_rate` and
  `statement`. `statement` is `null` when no statement is linked or the caller
  cannot read the linked portfolio-owned statement.
- Permission behavior: the query uses normal read permissions. An unknown or
  unreadable name returns the same permission failure.

### Desktop/mobile acceptance flow

The seeded investor opens the Bond Exchange Rate list without relying on
portfolio assignment, sees the deterministic test rate and opens its detail
route. Desktop checks all configured list headers, representative 12-place
formatted Rate and Reverse Rate values, Source and read-only presentation;
Pixel 7 checks the same exchange rate and detail route without horizontal
viewport overflow. Server tests own the exact projection, role/feature matrix,
pagination boundaries and metadata omission.

## Completed slice: Phase 5a — Portfolio Performance

Objective: migrate the existing Portfolio Performance report through a
permission-scoped adapter and responsive read-only table without duplicating or
changing any financial calculation.

### Planned work

- [x] Record the Portfolio Performance Desk parity inventory before implementation.
- [x] Record the explicit report and cash-flow API contracts.
- [x] Add a permission-scoped adapter around the existing report and cash-flow services.
- [x] Add the responsive report route with loading, initial, empty, failed and retry states.
- [x] Preserve the app-owned XIRR cash-flow copy action without adding generic exports.
- [x] Add desktop/mobile Playwright flows and run focused and complete gates.

### Intended Phase 5a implementation slice — 2026-08-24

This slice will add two allow-listed GET methods behind the existing investor
application gate: one stable projection of the authoritative Portfolio
Performance report and one projection of its existing XIRR cash flows. The SPA
will render only returned values and format them from returned report metadata;
all portfolio, position, price, accrual, exchange-rate, total and XIRR work will
remain in the existing Python report and utilities. It will not add or change a
financial formula, report role, DocType permission, schema, hook, dependency,
legacy redirect or Desk report behavior.

### Portfolio Performance Desk parity inventory

Evidence source: the standard `Portfolio Performance` Script Report, its
app-owned report JavaScript and the standard Query Report runner.

- Filters, in order: required Portfolio and Valuation Date. Portfolio is a
  `Bond Portfolio` Link; Valuation Date defaults to the current date in Desk and
  is required by the server. The SPA limits Portfolio choices to bootstrap
  assignments and exposes no arbitrary report filter.
- Row order: ISIN ascending. A calculated `TOTAL` row appears last only when at
  least one bond row exists.
- Native columns, in order: ISIN, CCY, Prin. Factor, Nominal Value, Purchases
  Value, Proceeds Value, Market Value, Gain Value, XIRR and Future XIRR.
- Mixed-currency columns: Market Value (USD) appears after Market Value and XIRR
  (USD) appears after XIRR when any bond currency is not USD. USD-only results
  omit both duplicate reporting-currency columns. Hidden calculation helpers,
  including Exchange Rate and the other USD value fields, are not displayed.
- Currency and percentage meaning: native money columns use each row's CCY;
  Market Value (USD) uses the report's USD reporting currency; Percent and
  Float precision follows the resolved report/system precision. Values remain
  server-authoritative.
- Total behavior: single-currency results contain native money and XIRR totals.
  Mixed-currency results leave native money and native XIRR totals blank and
  retain the comparable USD Market Value and XIRR totals. Principal Factor is
  blank on `TOTAL`.
- Chart: none. The existing report returns no chart or chart series, so Phase 5a
  adds no visualization.
- App-owned action: each non-null visible XIRR value copies its underlying
  native or reporting-currency cash flows as sanitized TSV with columns ISIN,
  Transaction Type, Date, Currency, Amount, Quantity and Rate. A mixed-currency
  `TOTAL` has no native cash-flow action. This confirmed investor-visible,
  non-mutating action remains in scope.
- Explicit omissions: hidden report row fields and generic Desk print, email and
  export controls. The latter are framework actions, not app-owned report
  behavior, and remain outside the approved SPA product boundary.
- View states: no assigned portfolio; filters ready but not run; loading; empty
  result; failed request with Retry; read-only results and total; cash-flow copy
  pending, empty, failed and successful feedback; expired-session redirect; and
  stale-response suppression after filter changes or a newer run.

### Portfolio Performance API contracts

`GET bond_management.bond_management.api.investor.get_portfolio_performance`

- Inputs: required non-empty `portfolio` and `valuation_date` strings. No
  arbitrary filters, fields, sorting, pagination or client-supplied calculation
  options are accepted.
- Response: `{ report }`. `report` contains the canonical `filters`, normalized
  allow-listed `columns`, fixed allow-listed `rows` and `chart: null`. Column
  metadata contains only `fieldname`, `label`, `fieldtype`, `options`,
  `description`, resolved `precision` and the optional cash-flow action. Rows
  contain only `isin`, `currency`, `reporting_currency`, `principal_factor`,
  `nominal_value`, `purchases_value`, `proceeds_value`, `market_value`,
  `market_value_usd`, `gain_value`, `xirr`, `xirr_usd` and `future_xirr`.
- Permission behavior: the common feature, session and role gate runs first;
  normal Report-role and `Bond Portfolio` report permissions remain required;
  the requested portfolio must also resolve through normal read permissions.
  An unreadable and unknown portfolio returns the same permission failure.

`GET bond_management.bond_management.api.investor.get_portfolio_performance_cashflows`

- Inputs: required `portfolio`, `valuation_date`, `isin` and `xirr_type` strings;
  `xirr_type` is `past` or `future`; optional `cashflow_currency` is `native` or
  `reporting` and defaults to `native`.
- Response: `{ cashflows }`, where every row contains exactly `isin`,
  `transaction_type`, `date`, `currency`, `amount`, `quantity` and `rate` in
  deterministic date/amount order.
- Permission behavior: the same report and portfolio boundary runs before the
  existing cash-flow service validates the requested ISIN and cash-flow mode.

### Desktop/mobile acceptance flow

The seeded investor opens Portfolio Performance, chooses the assigned portfolio
and `2025-12-31`, runs the report and sees the deterministic bond plus `TOTAL`.
Desktop checks all ten USD-only column labels, representative native money and
Future XIRR values, the omitted duplicate USD columns and a working sanitized
cash-flow copy action. Pixel 7 checks the same filters, bond, total and values
without horizontal viewport overflow. Server tests own cross-portfolio denial,
exact column/row/cash-flow projections, dynamic mixed-currency columns, totals
and financial-value equivalence with the existing report.

## Completed slice: Phase 5b — Bond Yield Comparison

Objective: migrate Bond Yield Comparison through a permission-scoped adapter
and responsive chart-only view without recalculating any persisted market
yield.

### Planned work

- [x] Record the Bond Yield Comparison Desk parity inventory.
- [x] Resolve the shared-history permission and audit-copy product decisions.
- [x] Record the explicit report API contract.
- [x] Add a permission-scoped adapter around the existing report.
- [x] Add the responsive chart-only route with loading, initial, empty, failed and retry states.
- [x] Preserve client-only bond selection and the sanitized audit-copy action.
- [x] Add desktop/mobile Playwright flows and run focused and complete gates.

### Intended Phase 5b implementation slice — 2026-08-26

This slice will add one allow-listed GET method behind the existing investor
application gate. It will project the authoritative Bond Yield Comparison
report into stable filters, columns, rows and chart-series inputs. The SPA will
render only persisted Market Price and Future XIRR values, select visible bond
series locally, and preserve the app-owned audit-data clipboard action. It will
not add or change a financial formula, Report role, DocType permission, schema,
hook, dependency, legacy redirect or Desk report behavior.

### Bond Yield Comparison Desk parity inventory

Evidence source: the standard `Bond Yield Comparison` Script Report, its
app-owned report JavaScript and the standard Query Report runner.

- Filters, in order: optional From Date and To Date. From Date defaults to the
  oldest permission-readable persisted yield date and To Date defaults to the
  current site date. Both bounds remain editable and inclusive; an omitted
  bound leaves that side open. From Date must be on or before To Date. Bond
  selection is an app-owned client-only control, not a server report filter in
  the SPA.
- Raw columns, in order: Date, ISIN, CCY, Market Price and Future XIRR. The Desk
  table is hidden after a successful refresh; the SPA likewise keeps these raw
  rows out of the visible result surface.
- Row order: Date ascending, then ISIN ascending.
- Chart: one line series per readable bond, named by ISIN and colored by
  currency. Horizontal positions use the persisted market date, but the visible
  axis shows each year once. The chart renders lines without point markers; its
  accessible description retains each point's Date, ISIN, Currency, Market
  Price and Future XIRR. Missing bond/date values remain gaps rather than being
  interpolated or recalculated.
- Bond selection: all returned bonds are selected initially. Select-all and
  individual selection alter visible chart series only; they do not issue a new
  request or change the authoritative rows.
- Shared-history permission: an approved investor-role user may run the report
  without a portfolio assignment. The common feature/session/role gate,
  standard Report-role check and normal Bond Market Date and Bond Master read
  permissions remain required.
- App-owned action: Copy audit data to Excel remains available. It copies only
  the adapter's five allow-listed columns and rows as TSV. Text cells are
  stripped of control characters and prefixed when they could be interpreted
  as spreadsheet formulas.
- Explicit omissions: visible raw result table, generic Desk print/email/export
  controls, arbitrary report filters, client financial calculations and
  mutation controls.
- View states: filters ready but not run; loading; empty result; failed request
  with Retry; chart with all, some or no bonds selected; audit copy success or
  failure; expired-session redirect; and stale-response suppression after
  filter changes or a newer run.

### Bond Yield Comparison API contract

`GET bond_management.bond_management.api.investor.get_yield_comparison_defaults`

- Inputs: none.
- Response: `{ filters }`, containing only `from_date` and `to_date`.
  `from_date` is the oldest Bond Market Date containing a permission-readable
  bond yield, or `null` when no readable history exists. `to_date` is the
  current site date.
- Permission behavior: the common feature, session and role gate, standard
  Report-role permission and normal Bond Market Date/Bond Master read
  permissions match the report endpoint. No portfolio assignment is required.

`GET bond_management.bond_management.api.investor.get_bond_yield_comparison`

- Inputs: optional `from_date` and `to_date` strings. Both must be valid dates
  when present, and From Date must be on or before To Date. No portfolio,
  client-selected bond list, arbitrary filters, fields, sorting, pagination or
  calculation options are accepted.
- Response: `{ report }`. `report` contains canonical `filters`, five normalized
  allow-listed `columns`, fixed allow-listed `rows` and chart metadata. Column
  metadata contains only `fieldname`, `label`, `fieldtype`, `options`,
  `description` and resolved `precision`. Rows contain only `date`, `isin`,
  `currency`, `market_price` and `future_xirr`. Chart metadata identifies Date
  as the horizontal field, Future XIRR as the value field and ISIN as the series
  field; the client derives presentation coordinates without changing values.
- Permission behavior: the common feature, session and role gate runs first;
  normal Report-role permission and normal Bond Market Date/Bond Master read
  permissions remain required. No portfolio assignment is required because the
  report uses the same shared reference history as the completed Market Dates
  surface.

### Desktop/mobile acceptance flow

The seeded investor opens Bond Yield Comparison without relying on a portfolio
assignment, receives the oldest-readable/current-date defaults, enters an
inclusive deterministic date range, runs the report and sees the persisted test
bond series. Desktop checks all filter labels, line-only rendering, one label
per visible year, series selection, representative accessible Market Price and
Future XIRR point text, a chart gap, the hidden raw table and sanitized
audit-copy output. Pixel 7 checks the same filters, yearly axis, series and
representative values without horizontal viewport overflow. Server tests own
role and Report permission, no-assignment access, default bounds, exact dynamic
projection, date validation, persisted-value equivalence, permission-scoped
Bond Market Date/Bond Master reads and rejected arbitrary arguments.

## Completed slice: Phase 6 — Parity and hardening

Objective: close shared recovery, accessibility and response-boundary gaps
without changing investor data, financial calculations or pilot routing.

### Planned work

- [x] Audit every migrated route for loading, empty, failure, retry,
      stale-response, expired-session, deep-link, accessibility and responsive
      behavior.
- [x] Replace stale migration-shell copy and unreachable planned-surface state
      now that all eight investor surfaces are available.
- [x] Add route-specific document titles and move focus to the page heading
      after SPA navigation.
- [x] Add deterministic Playwright coverage for shared loading, empty,
      failure/retry, stale-response, expired-session, deep-link, keyboard-focus and
      mobile-overflow behavior.
- [x] Add one server invariant that rejects attachment/private-file fields in
      every investor response allow-list, complementing each endpoint's exact
      projection tests.
- [x] Run targeted server and browser tests, frontend checks, complete
      Playwright and Cypress suites, shared `pre-push` and `pre-push-ui` gates, and
      CI-shaped fresh-site verification required to close Phase 6.

### Intended Phase 6 implementation slice — 2026-08-26

This slice will keep existing endpoint and financial contracts unchanged. It
will harden shared navigation semantics, prove recovery states with controlled
investor-API responses, prove stale report responses cannot overwrite newer
filter state, and lock all API field allow-lists against attachment or private
file metadata. Existing per-surface server and real-data browser tests remain
the primary parity evidence. Controlled browser responses are limited to UI
state-machine regressions that cannot be made deterministic through persistent
test fixtures.

## In-progress slice: Phase 7 — Pilot

Objective: validate the completed read-only SPA with real pilot workflows while
retaining the legacy investor Workspace as the active login and Apps fallback.

### Planned work

- [x] Record the pilot acceptance and rollback evidence contract before pilot operations.
- [x] Verify pilot feedback change: line-only Yield Comparison chart, yearly x-axis labels and permission-scoped default date range.
- [ ] Record internal-team acceptance, participants, date and reviewed surfaces.
- [ ] Complete one full statement/reporting cycle with pilot investors and record the date, participants and defects found.
- [ ] Resolve every high-severity pilot defect and link its verification evidence.
- [x] Run the complete Playwright and Cypress suites against the restored `test_site` pilot configuration; rerun after pilot defects or config changes.
- [x] Rehearse rollback by disabling `bond_investor_spa_enabled`, verifying the SPA route returns to `/desk/bond-investor`, then restore the approved pilot state.
- [ ] Record the final pilot flag state and the person approving that state. `test_site` is restored to its initial enabled state; pilot-site approval remains pending.

### Intended Phase 7 pilot slice — 2026-08-26

Pilot evidence must identify who accepted the release, when they accepted it,
which of the eight migrated surfaces they exercised, and any defect or follow-up
created. The statement/reporting cycle must use a real pilot investor's assigned
portfolio and cover a statement plus both reports without recording financial
values, credentials or private attachment metadata in this repository.

Rollback rehearsal will use the canonical `test_site`: capture the initial flag
state, disable the flag, verify `/bond-investor` temporarily redirects to the
unchanged `/desk/bond-investor` fallback, restore the approved pilot state and
verify the SPA route again. No financial data, schema, login redirect, Apps route
or legacy Workspace changes are part of this slice.

### Pilot acceptance record

- Internal-team acceptance: Pending.
- Pilot statement/reporting cycle: Pending.
- High-severity defects: Pending pilot execution; none inferred from pre-pilot gates.
- Final pilot flag state and approver: Pending.
- Rollback rehearsal: Complete on `test_site` on 2026-08-26; evidence is in the verification log.
- Pilot feedback complete: Yield Comparison now uses line-only rendering, one label per year, oldest-readable/current-date defaults and an accessible non-visual point description.

## Pilot and retirement gates

- [x] Full surface parity inventory accepted.
- [x] Server permission matrix green.
- [x] Complete Playwright desktop/mobile suite green.
- [x] Complete Cypress suite green.
- [ ] Internal-team acceptance recorded.
- [ ] One full statement/reporting cycle completed with pilot investors.
- [x] Pilot rollback rehearsed by disabling the site flag.
- [ ] Cutover observation period completed without a rollback condition.
- [ ] Legacy workspace removal approved as a separate release.
- [ ] Internal Desk behaviours and their Cypress ownership confirmed before removing any Cypress spec.

## Verification log

Add one entry after every slice. Preserve failed or unavailable gates; later success does not erase earlier diagnostic evidence.

### 2026-08-22 — Phase 0 documentation

- Risk classification: Documentation and app-local agent guidance.
- Required gates: Formatting/lint for changed Markdown and YAML; no application test is affected.
- Commands executed:
  - `../frappe/node_modules/.bin/prettier --write docs/specs/investor-ui-migration.md docs/plans/investor-ui-migration-progress.md`.
  - `../frappe/node_modules/.bin/prettier --check .codex/context.md docs/specs/investor-ui-migration.md docs/plans/investor-ui-migration-progress.md`.
  - `../../env/bin/pre-commit run --files .codex/context.md docs/specs/investor-ui-migration.md docs/plans/investor-ui-migration-progress.md .agents/skills/writing-for-agents/SKILL.md .agents/skills/writing-for-agents/SKILL-MECHANICS.md .agents/skills/writing-for-agents/agents/openai.yaml`.
  - `SSL_CERT_FILE=/etc/ssl/cert.pem XDG_CONFIG_HOME=/tmp/bond-management-semgrep-config SEMGREP_LOG_FILE=/tmp/bond-management-semgrep.log SEMGREP_SETTINGS_FILE=/tmp/bond-management-semgrep-settings.yml SEMGREP_VERSION_CACHE_PATH=/tmp/bond-management-semgrep-version SEMGREP_SEND_METRICS=off SEMGREP_BIN=/Users/deepakpatel/frappe-dev/frappe-bench/env/bin/semgrep scripts/verify.sh lint`.
- Exit statuses: `0`, `0`, `0`, `0`.
- Tests passed: All pre-commit hooks; Frappe blocking and advisory scans with zero findings; Bond Management scan with zero findings; Semgrep rule tests `2/2`.
- Tests failed: Initial lint attempts exposed host CA, sandbox cache and relative-binary-path issues; the final absolute-path command passed without repository changes.
- Tests not run: Server and browser suites; no runtime behaviour changed.
- Blockers: None.
- Unverified local/CI differences: None expected for documentation-only files.

### 2026-08-24 — Phase 1 compatibility/toolchain slice

- Risk classification: Cross-layer frontend/server/CI bootstrap; changes include a new website route, a read-only API, app hooks, Node dependencies, generated assets, browser tests, and CI setup.
- Required gates: Frontend lint/typecheck/build; targeted and complete server tests; focused desktop/mobile and complete Playwright suites; complete Cypress suite; `pre-push`; `pre-push-ui`; fresh-site validation for the installation and dependency changes.
- Commands executed:
  - `yarn install` in `frontend/` after the parser pin update — exit `0`.
  - `yarn lint`, `yarn typecheck`, and `bench build --app bond_management` — exit `0`.
  - `bench --site test_site migrate` — exit `0`.
  - Targeted modules `bond_management.bond_management.tests.test_investor_ui_seed`, `bond_management.bond_management.api.test_investor`, and `bond_management.www.test_bond_investor` — exit `0`; 9 tests passed.
  - `bench --site test_site run-tests --app bond_management` through the shared gates — exit `0`; 219 tests passed.
  - Focused Playwright desktop and mobile commands, followed by `yarn test:e2e` — final exits `0`; 3 complete-suite tests passed.
  - `CHROME_BIN="/Applications/Google Chrome.app/Contents/MacOS/Google Chrome" ... apps/bond_management/scripts/verify.sh pre-push` — exit `0`.
  - `CHROME_BIN="/Applications/Google Chrome.app/Contents/MacOS/Google Chrome" BASE_URL=http://127.0.0.1:8001 ... apps/bond_management/scripts/verify.sh pre-push-ui` — exit `0`; all 12 existing Cypress tests and all 3 Playwright tests passed.
  - Existing fresh app-installed site `bond_step9_fresh_20260811`: migration, seed, and the three targeted investor test modules — exit `0`.
  - A new CI-shaped site attempt, `bench new-site --db-root-password root --admin-password admin bond_ui_fresh_20260824`, exited `1` because local MariaDB rejected the assumed root credential. The partial site directory was removed after `bench drop-site ... --force --no-backup` also could not authenticate; no existing site was dropped or recreated.
  - After formatting the new API module with the cached Ruff tool, direct Ruff check/format checks and final reruns of `apps/bond_management/scripts/verify.sh pre-push` and `pre-push-ui` — exit `0`.
- Exit statuses: All completed required local gates above were `0`; the new-site attempt was `1`, and its cleanup command was `1` before the confirmed partial-directory cleanup exited `0`.
- Tests passed: Pre-commit hooks, blocking/advisory Semgrep scans and rule tests; direct Ruff checks for the newly added Python files; 219 server tests; 12 Cypress tests; 3 Playwright tests; fresh app-installed-site migration and targeted investor tests.
- Tests failed: The first desktop Playwright invocation exited `1` because `testDir` excluded `e2e/auth.setup.ts`; the project discovery configuration was corrected and the focused and complete suites then passed. The first fresh-site migration invocation exited `143` while the local bench process was being restarted; the rerun exited `0`.
- Tests not run: A newly created local CI-shaped site could not be installed because MariaDB root authentication is unavailable; GitHub Actions itself was not run in this workspace.
- Blockers: Phase 1 remains `In progress` until the separate CI-shaped fresh-site install/build is observed green in CI or run with valid local MariaDB bootstrap credentials.
- Unverified local/CI differences: Local verification used macOS/arm64, the existing bench and MariaDB instance, an explicit `bond_step9_fresh_20260811` app-installed site for fresh-site behavior, and `test_site` on `127.0.0.1:8001` for Playwright. CI uses a unique Ubuntu runner bench, MariaDB 11.8, Node 24, and `test_site` on `test_site:8000`; the separate Playwright job and its browser/dependency cache remain to be observed in CI.

### 2026-08-24 — Phase 1 review follow-up

- Risk classification: Cross-layer route, browser-authentication and CI verification corrections.
- Required gates: Focused website and seed tests; frontend lint/typecheck/build; investor-authenticated Playwright; `pre-push`; `pre-push-ui`; CI-shaped fresh-site validation remains required for Phase 1.
- Commands executed:
  - `bench --site test_site run-tests --module bond_management.www.test_bond_investor` — final exit `0`; 3 tests passed, including temporary redirect status coverage.
  - `bench --site test_site run-tests --module bond_management.bond_management.tests.test_investor_ui_seed` — exit `0`; 3 tests passed, including required environment-credential coverage.
  - `apps/bond_management/scripts/verify.sh frontend` — exit `0`; frontend lint, typecheck and production build passed.
  - `FRAPPE_USER=... FRAPPE_PASSWORD=... BASE_URL=http://127.0.0.1:8001 apps/bond_management/scripts/verify.sh playwright` with an ephemeral local test password — exit `0`; the setup authenticated as the seeded investor and all 3 Playwright tests passed.
  - `apps/bond_management/scripts/verify.sh pre-push` — exit `0`; lint and security scans passed, migration passed, and all 222 server tests passed.
  - `FRAPPE_USER=... FRAPPE_PASSWORD=... BASE_URL=http://127.0.0.1:8001 CHROME_BIN="/Applications/Google Chrome.app/Contents/MacOS/Google Chrome" apps/bond_management/scripts/verify.sh pre-push-ui` with an ephemeral local test password — exit `0`; all 222 server tests, 12 Cypress tests and 3 investor-authenticated Playwright tests passed.
- Exit statuses: All final commands above exited `0`.
- Tests passed: 6 focused server tests; frontend lint/typecheck/build; 222 complete server tests; 12 Cypress tests; 3 Playwright tests authenticated as `bond-investor-ui@example.com`.
- Tests failed: The first focused guest-route test exposed an unbound request proxy in direct invocation; the route now reads the request through `frappe.local`, and the final focused and complete suites passed.
- Tests not run: The updated GitHub Actions Playwright job and a newly created local CI-shaped site were not run in this workspace.
- Blockers: Phase 1 remains `In progress` until the separate CI-shaped fresh-site install/build is observed green in CI or run with valid local MariaDB bootstrap credentials.
- Unverified local/CI differences: Local browser verification used macOS/arm64, Chrome 151, the existing bench, and an explicit `test_site` server on `127.0.0.1:8001`. CI will generate an ephemeral investor password, run frontend lint/typecheck/build in the separate Ubuntu Playwright job, and serve `test_site` on `test_site:8000`; that job remains to be observed.

### 2026-08-24 — Phase 1 fresh-site closure

- Risk classification: Fresh-site installation, dependency/build and focused cross-layer verification.
- Required gates: A newly created site, app installation, frontend lint/typecheck/production build, deterministic seed, and the focused investor server modules.
- Commands executed:
  - `mariadb-install-db` followed by an isolated MariaDB 12.3.2 server on localhost port `33070` — exit `0`.
  - `bench new-site --force --db-host 127.0.0.1 --db-port 33070 ... bond_ui_fresh_20260824b` — final exit `0`.
  - `bench --site bond_ui_fresh_20260824b install-app bond_management` — exit `0`.
  - `apps/bond_management/scripts/verify.sh frontend` — final exit `0` after rerunning outside the filesystem sandbox; frontend lint, typecheck and production build passed.
  - `bench --site bond_ui_fresh_20260824b execute bond_management.bond_management.tests.investor_ui_seed.seed_investor_ui_browser_test_data` — final exit `0` after starting the bench Redis services.
  - Focused modules `bond_management.bond_management.tests.test_investor_ui_seed`, `bond_management.bond_management.api.test_investor`, and `bond_management.www.test_bond_investor` — exits `0`; 12 tests passed.
- Exit statuses: All final required commands above exited `0`.
- Tests passed: Fresh Frappe site creation; fresh Bond Management installation; frontend lint/typecheck/build; deterministic browser seed; 12 focused investor seed/API/website tests.
- Tests failed: The first new-site attempt exited `1` because MariaDB had pre-created a passwordless `root@127.0.0.1` account; no site database existed and the corrected retry passed. The first frontend command exited `1` because Bench could not write its normal log inside the filesystem sandbox; the escalated rerun passed. The first optional seed attempt exited `1` because Redis Queue was stopped; after starting the existing bench Redis services, the seed and every focused module passed.
- Tests not run: GitHub Actions itself was not run in this workspace.
- Blockers: None; Phase 1 is complete.
- Unverified local/CI differences: The fresh site used the current macOS/arm64 bench, MariaDB 12.3.2 and Redis 8.8.0. CI uses a unique Ubuntu bench fetched from local `file://` source, MariaDB 11.8 and Redis Alpine. The app install, generated schema, frontend dependency graph and production build entry point were exercised on a genuinely new site, while the separate GitHub Playwright job remains to be observed on its native runner.

### 2026-08-24 — Phase 2 coexistence shell

- Risk classification: Authenticated cross-layer website shell and responsive client routing; no financial data, record API, mutation or legacy redirect changed.
- Required gates: Home navigation inventory; focused website route matrix; frontend lint/typecheck/build; focused and complete desktop/mobile Playwright; `pre-push`; `pre-push-ui`, including the unchanged complete Cypress suite.
- Commands executed:
  - `bench --site test_site run-tests --module bond_management.www.test_bond_investor` — final exit `0`; 6 tests passed for disabled, guest, unauthorized, investor, manager and Administrator behavior.
  - `apps/bond_management/scripts/verify.sh frontend` — exit `0`; frontend lint, typecheck and production build passed.
  - Focused `yarn test:e2e:desktop`, `yarn test:e2e:mobile` and named session-expiry commands, followed by `yarn test:e2e` — final exits `0`; the complete run reported 5 tests passed across setup, desktop and Pixel 7 projects.
  - `apps/bond_management/scripts/verify.sh pre-push` — final exit `0`; lint/security scans, migration and all 225 server tests passed.
  - `FRAPPE_USER=... FRAPPE_PASSWORD=... BASE_URL=http://127.0.0.1:8001 CHROME_BIN="/Applications/Google Chrome.app/Contents/MacOS/Google Chrome" apps/bond_management/scripts/verify.sh pre-push-ui` — final exit `0`; lint/security scans, migration, all 225 server tests, frontend lint/typecheck/build, all 12 Cypress tests and all 5 Playwright tests passed.
- Exit statuses: All final required commands above exited `0`.
- Tests passed: 6 focused route tests; 225 complete server tests; 12 unchanged Cypress tests; 5 complete Playwright tests covering authenticated shell navigation, nested-route refresh, isolated real session expiry and Pixel 7 navigation/viewport behavior.
- Tests failed: The first focused route run could not create test Users while local Redis was stopped; the rerun with required services passed. The first sandboxed Chromium launch was denied by macOS process isolation; the approved rerun launched successfully. Early session-expiry attempts called the POST-only logout handler without its CSRF token; the corrected Frappe handler request passed. The first `pre-push` attempt stopped before migration because transient Redis sessions had ended; the complete rerun with persistent local services passed. The first `pre-push-ui` run exposed a shared Playwright session invalidated by the desktop logout test, so mobile was correctly redirected to login; the expiry test now owns a separate authenticated context, the focused mobile and complete Playwright reruns passed, and the final complete UI gate passed. One focused mobile rerun also encountered `ECONNREFUSED` after the explicit test server had stopped; it passed after the server was restarted.
- Tests not run: GitHub Actions itself was not run in this workspace.
- Blockers: None; Phase 2 is complete.
- Unverified local/CI differences: Local browser verification used macOS/arm64, Chrome 151, the cached Playwright Chromium headless shell and explicit `test_site` on `127.0.0.1:8001`. CI uses Ubuntu and serves `test_site` at `test_site:8000`; the separate GitHub Playwright job remains to be observed on its native runner.

### 2026-08-24 — Phase 3 transaction tracer bullet

- Risk classification: Authenticated cross-layer financial record projection and responsive read-only UI; no calculation, mutation, schema, permission, hook, dependency or legacy redirect changed.
- Required gates: Recorded transaction parity and API contracts; focused API and seed tests; frontend lint/typecheck/build; focused desktop/mobile and complete Playwright; `pre-push`; `pre-push-ui`, including the unchanged complete Cypress suite.
- Commands executed:
  - `bench --site test_site run-tests --module bond_management.bond_management.api.test_investor_transactions` — final exit `0`; 10 tests passed for roles, feature flag, portfolio isolation, direct denial without existence leakage, exact list/detail projections, attachment omission, pagination boundaries and rejected arbitrary filters.
  - `bench --site test_site run-tests --module bond_management.bond_management.tests.test_investor_ui_seed` — final exit `0`; 3 tests passed for caller-provided credentials, idempotent transaction fixtures and portfolio assignment.
  - `apps/bond_management/scripts/verify.sh frontend` — exit `0`; frontend lint, typecheck and Bench production build passed.
  - Focused desktop and Pixel 7 transaction specs — final exits `0`; each project passed its authentication setup and transaction list/detail flow.
  - `FRAPPE_USER=... FRAPPE_PASSWORD=... BASE_URL=http://127.0.0.1:8001 apps/bond_management/scripts/verify.sh playwright` — exit `0`; all 7 Playwright setup, desktop and mobile tests passed.
  - `apps/bond_management/scripts/verify.sh pre-push` — exit `0`; pre-commit, blocking/advisory security scans, migration and all 235 server tests passed.
  - `FRAPPE_USER=... FRAPPE_PASSWORD=... BASE_URL=http://127.0.0.1:8001 CHROME_BIN="/Applications/Google Chrome.app/Contents/MacOS/Google Chrome" apps/bond_management/scripts/verify.sh pre-push-ui` — exit `0`; pre-commit/security scans, migration, all 235 server tests, frontend lint/typecheck/build, all 12 Cypress tests and all 7 Playwright tests passed.
- Exit statuses: All final required commands above exited `0`.
- Tests passed: 13 focused server tests; frontend lint/typecheck/production build; 235 complete server tests; 12 unchanged Cypress tests; 7 complete Playwright tests covering authenticated shell behavior plus transaction list, portfolio filtering, detail, refresh and responsive mobile presentation.
- Tests failed: The first focused transaction API run expected the app validator's exception for a complex pagination value, while Frappe's type boundary correctly rejected it first; the assertion was corrected and the final focused and complete suites passed. The first updated seed assertion expected a list where `frappe.db.get_value` returns a tuple; the assertion was corrected and the final focused and complete suites passed.
- Tests not run: GitHub Actions itself was not run in this workspace. Fresh-site validation was not required because this slice did not change schema, hooks, dependencies, installation behavior or manual indexes.
- Blockers: None; Phase 3 is complete.
- Unverified local/CI differences: Local browser verification used macOS/arm64, Chrome 151, the cached Playwright Chromium headless shell and explicit `test_site` on `127.0.0.1:8001`. CI uses Ubuntu and serves `test_site` at `test_site:8000`; no Phase 3 dependency or runner configuration changed.

### 2026-08-24 — Phase 4a Bond Statement slice

- Risk classification: Authenticated cross-layer financial statement projection and responsive read-only UI; no calculation, mutation, attachment access, schema, permission, hook, dependency or legacy redirect changed.
- Required gates: Recorded statement parity and API contracts; focused API and seed tests; affected report regressions after fixture correction; frontend lint/typecheck/build; focused desktop/mobile and complete Playwright; `pre-push`; `pre-push-ui`, including the unchanged complete Cypress suite.
- Commands executed:
  - `bench --site test_site run-tests --module bond_management.bond_management.api.test_investor_statements` — final exit `0`; 9 tests passed for roles, feature flag, portfolio isolation, direct denial without existence leakage, exact list/detail and holding projections, both attachment omissions, status validation, pagination boundaries and rejected arbitrary filters.
  - `bench --site test_site run-tests --module bond_management.bond_management.tests.test_investor_ui_seed` — final exit `0`; 3 tests passed for caller-provided credentials, idempotent statement fixtures, generated holdings and portfolio assignment.
  - The previously affected Portfolio Performance test in isolation and its complete module — exits `0`; 1 and 18 tests passed. The previously affected Bond Yield Comparison test in isolation and its complete module — exits `0`; 1 and 6 tests passed.
  - `apps/bond_management/scripts/verify.sh frontend` and the final direct frontend lint — exits `0`; frontend lint reported no findings, typecheck passed and the Bench production build passed.
  - Focused desktop and Pixel 7 statement specs — final exits `0`; each project passed its authentication setup and statement list/detail flow.
  - `FRAPPE_USER=... FRAPPE_PASSWORD=... BASE_URL=http://127.0.0.1:8001 apps/bond_management/scripts/verify.sh playwright` — exit `0`; all 9 Playwright setup, desktop and mobile tests passed.
  - `apps/bond_management/scripts/verify.sh pre-push` — final exit `0`; pre-commit, blocking/advisory security scans, migration and all 244 server tests passed.
  - `FRAPPE_USER=... FRAPPE_PASSWORD=... BASE_URL=http://127.0.0.1:8001 CHROME_BIN="/Applications/Google Chrome.app/Contents/MacOS/Google Chrome" apps/bond_management/scripts/verify.sh pre-push-ui` — final exit `0`; pre-commit/security scans, migration, all 244 server tests, warning-free frontend lint/typecheck/build, all 12 Cypress tests and all 9 Playwright tests passed.
  - `../frappe/node_modules/.bin/prettier --write docs/plans/investor-ui-migration-progress.md` followed by the same command with `--check` — exits `0`.
- Exit statuses: All final required commands above exited `0`.
- Tests passed: 12 focused investor server tests; both affected report tests in isolation and their 18-test and 6-test modules; frontend lint/typecheck/production build; 244 complete server tests; 12 unchanged Cypress tests; 9 complete Playwright tests covering authenticated shell behavior plus transaction and statement list/detail flows on desktop and Pixel 7.
- Tests failed: The first focused API run failed before exercising eight tests because local Redis was stopped; the rerun passed after starting the existing cache and queue services. The first seed assertion compared Frappe's calendar date to a string; the corrected assertion passed. A later focused API rerun exposed a fixed market-date collision with the persistent browser fixture; the regression now uses the collision-safe factory. The first `pre-push` run then proved that the fixture's global market posting polluted two report tests; the statement fixture no longer creates a market posting, the exact test-owned posting was detached and deleted from `test_site`, both report failures passed in isolation and in their complete modules, and both final shared gates passed. The first complete UI pass exited `0` with Vue template warnings after an explicit Prettier run; the frontend ESLint fixer removed those warnings and the final complete UI gate passed without them.
- Tests not run: GitHub Actions itself was not run in this workspace. Fresh-site validation was not required because this slice did not change schema, hooks, dependencies, installation behavior or manual indexes.
- Blockers: None; Phase 4a is complete.
- Unverified local/CI differences: Local browser verification used macOS/arm64, Chrome 151, the cached Playwright Chromium headless shell and explicit `test_site` on `127.0.0.1:8001`. CI uses Ubuntu and serves `test_site` at `test_site:8000`; no Phase 4a dependency or runner configuration changed.

### 2026-08-24 — Phase 4b Bond Master slice

- Risk classification: Authenticated cross-layer shared Bond Master projection and responsive read-only schedules; no financial calculation, mutation, schema, permission, hook, dependency or legacy redirect changed.
- Required gates: Recorded Bond Master parity and API contracts; focused API and seed tests; frontend lint/typecheck/build; focused desktop/mobile and complete Playwright; `pre-push`; `pre-push-ui`, including the unchanged complete Cypress suite.
- Commands executed:
  - `bench --site test_site migrate`, `bench --site test_site run-tests --module bond_management.bond_management.api.test_investor_bonds`, and `bench --site test_site run-tests --module bond_management.bond_management.tests.test_investor_ui_seed` — exits `0`; 8 Bond Master API tests and 3 seed tests passed.
  - `apps/bond_management/scripts/verify.sh frontend` — final exit `0`; warning-free frontend lint, typecheck and Bench production build passed.
  - Focused desktop and Pixel 7 Bond Master specs — exits `0`; each project passed authentication setup and its catalog/detail flow.
  - `FRAPPE_USER=... FRAPPE_PASSWORD=... BASE_URL=http://127.0.0.1:8001 apps/bond_management/scripts/verify.sh playwright` with an ephemeral local test password — exit `0`; all 11 Playwright setup, desktop and mobile tests passed.
  - `apps/bond_management/scripts/verify.sh pre-push` — exit `0`; pre-commit, blocking/advisory security scans, migration and all 252 server tests passed.
  - `FRAPPE_USER=... FRAPPE_PASSWORD=... BASE_URL=http://127.0.0.1:8001 CHROME_BIN="/Applications/Google Chrome.app/Contents/MacOS/Google Chrome" apps/bond_management/scripts/verify.sh pre-push-ui` with an ephemeral local test password — exit `0`; pre-commit/security scans, migration, all 252 server tests, warning-free frontend lint/typecheck/build, all 12 Cypress tests and all 11 Playwright tests passed.
- Exit statuses: All final required commands above exited `0`.
- Tests passed: 11 focused server tests; frontend lint/typecheck/production build; 252 complete server tests; 12 unchanged Cypress tests; 11 complete Playwright tests covering authenticated shell behavior plus transaction, statement and Bond Master list/detail flows on desktop and Pixel 7.
- Tests failed: None. The first direct formatting attempt exited `127` because `../../env/bin/ruff` is unavailable; the repository's required pre-commit Ruff hooks then passed on every changed Python file. The first sandboxed Bench invocation exited `1` because Bench could not write its log outside the app workspace; the approved rerun passed. The first frontend gate exited `0` but reported Vue template warnings after explicit Prettier formatting; the project ESLint fixer removed them and the final frontend and complete UI gates passed warning-free.
- Tests not run: GitHub Actions itself was not run in this workspace. Fresh-site validation was not required because this slice did not change schema, hooks, dependencies, installation behavior or manual indexes.
- Blockers: None; Phase 4b is complete.
- Unverified local/CI differences: Local browser verification used macOS/arm64, Chrome 151, the cached Playwright Chromium headless shell and explicit `test_site` on `127.0.0.1:8001`. CI uses Ubuntu and serves `test_site` at `test_site:8000`; no Phase 4b dependency or runner configuration changed.

### 2026-08-24 — Phase 4c Bond Market Date slice

- Risk classification: Authenticated cross-layer shared Bond Market Date projection, persisted financial values and responsive read-only yield visualization; no financial recalculation, mutation, schema, permission, hook, dependency or legacy redirect changed.
- Required gates: Recorded Bond Market Date parity and API contracts; focused API and seed tests; affected Yield Comparison regression in isolation and its complete module; frontend lint/typecheck/build; focused desktop/mobile and complete Playwright; `pre-push`; `pre-push-ui`, including the unchanged complete Cypress suite.
- Commands executed:
  - `bench --site test_site set-config allow_tests true`, `bench --site test_site migrate`, `bench --site test_site run-tests --module bond_management.bond_management.api.test_investor_market_dates`, and `bench --site test_site run-tests --module bond_management.bond_management.tests.test_investor_ui_seed` — final exits `0`; 8 Market Date API tests and 3 seed tests passed.
  - The affected `test_empty_selection_returns_all_readable_bonds` test in isolation and complete `bond_management.bond_management.report.bond_yield_comparison.test_bond_yield_comparison` module — final exits `0`; 1 and 6 tests passed.
  - `apps/bond_management/scripts/verify.sh frontend` — exit `0`; warning-free frontend lint, typecheck and Bench production build passed.
  - Focused desktop and Pixel 7 Bond Market Date specs — final exits `0`; each project passed authentication setup and its list/detail/yield-curve flow.
  - `FRAPPE_USER=... FRAPPE_PASSWORD=... BASE_URL=http://127.0.0.1:8001 apps/bond_management/scripts/verify.sh playwright` with an ephemeral local test password — exit `0`; all 13 Playwright setup, desktop and mobile tests passed.
  - `apps/bond_management/scripts/verify.sh pre-push` — exit `0`; pre-commit, blocking/advisory security scans, migration and all 260 server tests passed.
  - `FRAPPE_USER=... FRAPPE_PASSWORD=... BASE_URL=http://127.0.0.1:8001 CHROME_BIN="/Applications/Google Chrome.app/Contents/MacOS/Google Chrome" apps/bond_management/scripts/verify.sh pre-push-ui` with an ephemeral local test password — exit `0`; pre-commit/security scans, migration, all 260 server tests, warning-free frontend lint/typecheck/build, all 12 Cypress tests and all 13 Playwright tests passed.
  - `../frappe/node_modules/.bin/prettier --write docs/plans/investor-ui-migration-progress.md`, the matching `--check`, `git diff --check`, and `../../env/bin/pre-commit run --files ...` for every Phase 4c changed or new file — final exits `0`.
- Exit statuses: All final required commands above exited `0`.
- Tests passed: 11 focused investor server tests; affected Yield Comparison regression in isolation and its 6-test module; frontend lint/typecheck/production build; 260 complete server tests; 12 unchanged Cypress tests; 13 complete Playwright tests covering authenticated shell behavior plus transaction, statement, Bond Master and Bond Market Date list/detail flows on desktop and Pixel 7.
- Tests failed: The first Market Date API run used attribute access against an intentionally plain projected child dictionary; the corrected exact-projection assertion passed. The first desktop Market Date spec used an accessible-name query unsupported for the text-only list item; its page snapshot proved the USD legend was present, the locator was corrected to the visible text, and both focused projects passed. The persisted browser market row then exposed the Yield Comparison test's assumption that no pre-existing readable market rows existed; the failure reproduced in the complete module and in isolation, the test now records the exact pre-existing readable set before adding its own rows, and both isolated and complete-module reruns passed. The first explicit changed-file pre-commit shorthand exited `127` because `pre-commit` is not on the interactive shell PATH; the bench environment's explicit binary then passed every Phase 4c file.
- Tests not run: GitHub Actions itself was not run in this workspace. Fresh-site validation was not required because this slice did not change schema, hooks, dependencies, installation behavior or manual indexes.
- Blockers: None; Phase 4c is complete.
- Unverified local/CI differences: Local browser verification used macOS/arm64, Chrome 151, the cached Playwright Chromium headless shell and explicit `test_site` on `127.0.0.1:8001`. CI uses Ubuntu and serves `test_site` at `test_site:8000`; no Phase 4c dependency or runner configuration changed.

### 2026-08-24 — Phase 4d Bond Exchange Rate slice

- Risk classification: Authenticated cross-layer shared Bond Exchange Rate projection, persisted financial values and responsive read-only UI; unreadable linked Statement identifiers are masked. No financial recalculation, mutation, schema, permission, hook, dependency or legacy redirect changed.
- Required gates: Recorded Exchange Rate parity and API contracts; focused API and seed tests; affected Portfolio Performance module after persistent fixture seeding; frontend lint/typecheck/build; focused desktop/mobile and complete Playwright; `pre-push`; `pre-push-ui`, including the unchanged complete Cypress suite.
- Commands executed:
  - `bench --site test_site set-config allow_tests true`, `bench --site test_site migrate`, `bench --site test_site run-tests --module bond_management.bond_management.api.test_investor_exchange_rates`, and `bench --site test_site run-tests --module bond_management.bond_management.tests.test_investor_ui_seed` — final exits `0`; 10 Exchange Rate API tests and 3 seed tests passed.
  - `bench --site test_site run-tests --module bond_management.bond_management.report.portfolio_performance.test_portfolio_performance` after the persistent GBP browser fixture was seeded — exit `0`; all 18 tests passed.
  - Targeted Frappe and Bond Management Semgrep scans against every Phase 4d Python and TypeScript target, with the pinned Frappe rules and `SSL_CERT_FILE` set to the bench CA bundle — final exits `0`; the Frappe scan parsed 9 targets with 0 findings and the app scan parsed 4 Python targets with 0 findings.
  - `apps/bond_management/scripts/verify.sh frontend` — final post-normalization exit `0`; warning-free frontend lint, typecheck and Bench production build passed.
  - Focused desktop and Pixel 7 Bond Exchange Rate specs — final exits `0`; each project passed authentication setup and its list/detail flow.
  - `FRAPPE_USER=... FRAPPE_PASSWORD=... BASE_URL=http://127.0.0.1:8001 apps/bond_management/scripts/verify.sh playwright` with an ephemeral local test password — final post-normalization exit `0`; all 15 Playwright setup, desktop and mobile tests passed.
  - `apps/bond_management/scripts/verify.sh pre-push` — final exit `0` after the Semgrep translation correction; pre-commit, blocking/advisory security scans, migration and all 270 server tests passed.
  - `FRAPPE_USER=... FRAPPE_PASSWORD=... BASE_URL=http://127.0.0.1:8001 CHROME_BIN="/Applications/Google Chrome.app/Contents/MacOS/Google Chrome" apps/bond_management/scripts/verify.sh pre-push-ui` with an ephemeral local test password — final exit `0`; pre-commit/security scans, migration, all 270 server tests, frontend lint/typecheck/build, all 12 Cypress tests and all 15 Playwright tests passed.
  - `../../env/bin/pre-commit run --files ...` for the Phase 4d files, Prettier checks for the tracker and Playwright specs, final direct frontend ESLint normalization, and `git diff --check` — final exits `0`.
- Exit statuses: All final required commands above exited `0`.
- Tests passed: 13 focused investor server tests; affected 18-test Portfolio Performance module after persistent fixture seeding; frontend lint/typecheck/production build; 270 complete server tests; 12 unchanged Cypress tests; 15 complete Playwright tests covering authenticated shell behavior plus every read-only record list/detail flow on desktop and Pixel 7.
- Tests failed: The first focused desktop spec used a partial accessible-name match for `Rate`, which also matched `Rate Date` and `Reverse Rate`; exact header matching fixed the locator, then the desktop, mobile and complete Playwright runs passed. The first explicit targeted Semgrep invocation exited `2` because its HTTPS CA bundle was unavailable; the corrected invocation found one untranslated seed-helper error, the message was wrapped in `_()`, and both final targeted scans reported 0 findings. Initial full frontend lint reported 306 Vue template warnings in three Phase 4c files; a later complete UI gate exited `0` but reported 403 non-blocking warnings across those files and the two new Exchange Rate pages. Final ESLint normalization removed them, then warning-free frontend lint/typecheck/build and all 15 Playwright tests passed. Initial sandboxed Bench commands could not write `logs/bench.log`; approved reruns passed.
- Tests not run: GitHub Actions itself was not run in this workspace. Fresh-site validation was not required because this slice did not change schema, hooks, dependencies, installation behavior or manual indexes.
- Blockers: None; Phase 4d and Phase 4 are complete.
- Unverified local/CI differences: Local browser verification used macOS/arm64, Chrome 151, the cached Playwright Chromium headless shell and explicit `test_site` on `127.0.0.1:8001`. CI uses Ubuntu and serves `test_site` at `test_site:8000`; no Phase 4d dependency or runner configuration changed.

### 2026-08-24 — Phase 5a Portfolio Performance slice

- Risk classification: Authenticated cross-layer financial-report projection and responsive read-only UI with an existing sanitized cash-flow copy action; no financial calculation, mutation, schema, permission, hook, dependency or legacy redirect changed.
- Required gates: Recorded Portfolio Performance parity and API contracts; focused adapter and authoritative report tests; frontend lint/typecheck/build; focused desktop/mobile and complete Playwright; `pre-push`; `pre-push-ui`, including the unchanged complete Cypress suite.
- Commands executed:
  - `bench --site test_site run-tests --module bond_management.bond_management.api.test_investor_performance` — final exit `0`; 10 tests passed for feature, role, Report and portfolio permissions, identical unknown/unreadable denial, Administrator and Manager access, empty results, exact dynamic projection, hidden-field omission, authoritative mixed-currency totals, cash flows and rejected invalid arguments.
  - `bench --site test_site run-tests --module bond_management.bond_management.report.portfolio_performance.test_portfolio_performance` — exit `0`; all 18 authoritative report tests passed unchanged.
  - `apps/bond_management/scripts/verify.sh frontend` — exit `0`; frontend lint, typecheck and Bench production build passed.
  - Focused `yarn playwright test e2e/tests/investor-performance.spec.ts --project=chromium` and `yarn playwright test e2e/tests/investor-performance.mobile.spec.ts --project=mobile` runs — final exits `0`; each passed authentication setup and its Portfolio Performance flow.
  - `FRAPPE_USER=... FRAPPE_PASSWORD=... BASE_URL=http://127.0.0.1:8001 apps/bond_management/scripts/verify.sh playwright` with an ephemeral local test password — exit `0`; all 17 Playwright setup, desktop and mobile tests passed.
  - `apps/bond_management/scripts/verify.sh pre-push` — exit `0`; pre-commit, blocking/advisory security scans, migration and all 280 server tests passed.
  - `FRAPPE_USER=... FRAPPE_PASSWORD=... BASE_URL=http://127.0.0.1:8001 CHROME_BIN="/Applications/Google Chrome.app/Contents/MacOS/Google Chrome" apps/bond_management/scripts/verify.sh pre-push-ui` with an ephemeral local test password — exit `0`; pre-commit/security scans, migration, all 280 server tests, frontend lint/typecheck/build, all 12 Cypress tests and all 17 Playwright tests passed.
  - `../frappe/node_modules/.bin/prettier --write docs/plans/investor-ui-migration-progress.md`, the matching `--check`, `../../env/bin/pre-commit run --files ...` for every Phase 5a changed or new file, and `git diff --check` — final exits `0`.
- Exit statuses: All final required commands above exited `0`.
- Tests passed: 10 focused investor report-adapter tests; 18 unchanged authoritative Portfolio Performance tests; frontend lint/typecheck/production build; 280 complete server tests; 12 unchanged Cypress tests; 17 complete Playwright tests covering authenticated shell behavior plus every record surface and Portfolio Performance on desktop and Pixel 7.
- Tests failed: The first two focused desktop attempts exposed an ambiguous Portfolio label and then a wrapping-label accessible name that included its options. Explicit `for`/`id` filter labels and exact accessible-name queries fixed the form contract; focused desktop, mobile and complete Playwright reruns passed. An explicit Prettier pass exposed non-blocking Vue template indentation warnings; project ESLint normalization removed them before the final warning-free frontend checks and shared gates.
- Tests not run: GitHub Actions itself was not run in this workspace. Fresh-site validation was not required because this slice did not change schema, hooks, dependencies, installation behavior or manual indexes.
- Blockers: None; Phase 5a is complete.
- Unverified local/CI differences: Local browser verification used macOS/arm64, Chrome 151, the cached Playwright Chromium headless shell and explicit `test_site` on `127.0.0.1:8001`. CI uses Ubuntu and serves `test_site` at `test_site:8000`; no Phase 5a dependency or runner configuration changed.

### 2026-08-26 — Phase 5b Bond Yield Comparison slice

- Risk classification: Authenticated cross-layer shared-history financial-report projection, persisted market values, responsive chart-only UI and sanitized audit clipboard action; no financial calculation, mutation, schema, permission, hook, dependency or legacy redirect changed.
- Required gates: Recorded Yield Comparison parity, permission and API contracts; focused adapter, seed and authoritative report tests; targeted security scans; frontend lint/typecheck/build; focused desktop/mobile and complete Playwright; `pre-push`; `pre-push-ui`, including the complete Cypress suite.
- Commands executed:
  - `bench --site test_site migrate` and `bench --site test_site run-tests --module bond_management.bond_management.api.test_investor_yield_comparison` — final exits `0`; all 8 adapter tests passed.
  - `bench --site test_site run-tests --module bond_management.bond_management.tests.test_investor_ui_seed` and `bench --site test_site run-tests --module bond_management.bond_management.report.bond_yield_comparison.test_bond_yield_comparison` — final exits `0`; all 3 seed and 6 authoritative report tests passed.
  - Targeted Frappe and Bond Management Semgrep scans over the new Phase 5b Python, TypeScript and Vue targets — exits `0`; the Frappe scan parsed 6 supported targets and the app scan parsed 5 Python targets with 0 findings.
  - `apps/bond_management/scripts/verify.sh frontend` after final ESLint normalization — exit `0`; warning-free frontend lint, typecheck and Bench production build passed.
  - Focused desktop and Pixel 7 Yield Comparison specs — exits `0`; each project passed authentication setup and its chart, selection, gap, persisted-value and responsive flow.
  - `FRAPPE_USER=... FRAPPE_PASSWORD=... BASE_URL=http://127.0.0.1:8001 apps/bond_management/scripts/verify.sh playwright` with an ephemeral local test password — exit `0`; all 19 Playwright setup, desktop and mobile tests passed.
  - `apps/bond_management/scripts/verify.sh pre-push` — exit `0`; pre-commit, blocking/advisory security scans, migration and all 288 server tests passed.
  - `FRAPPE_USER=... FRAPPE_PASSWORD=... BASE_URL=http://127.0.0.1:8001 CHROME_BIN="/Applications/Google Chrome.app/Contents/MacOS/Google Chrome" apps/bond_management/scripts/verify.sh pre-push-ui` with an ephemeral local test password — exit `0`; pre-commit/security scans, migration, all 288 server tests, warning-free frontend lint/typecheck/build, all 13 Cypress tests and all 19 Playwright tests passed.
  - `../../env/bin/pre-commit run --files ...` for every Phase 5b changed or new file, Prettier write/check for the tracker and Playwright specs, final direct frontend ESLint normalization, and `git diff --check` — final exits `0`.
- Exit statuses: All final required commands above exited `0`.
- Tests passed: 11 focused investor server tests; 6 unchanged authoritative Yield Comparison tests; targeted Frappe and app security scans with 0 findings; frontend lint/typecheck/production build; 288 complete server tests; 13 complete Cypress tests; 19 complete Playwright tests covering every migrated record and report surface on desktop and Pixel 7.
- Tests failed: The first migration attempt could not run because the bench-local Redis cache and queue services were stopped; both services were started and every subsequent migration passed. The first adapter module run used fixed market dates that collided across persistent test runs and a broad date range that included another test's rows; factory-assigned dates and exact bounds made the suite deterministic, then all 8 tests passed. A root `yarn prettier` attempt exited `1` because Prettier is owned by Frappe's Node dependencies; the explicit bench-local Prettier binary passed. Prettier formatting exposed 371 non-blocking Vue template warnings; final project ESLint normalization removed them before the warning-free frontend and complete UI gates.
- Tests not run: GitHub Actions itself was not run in this workspace. Fresh-site validation was not required because this slice did not change schema, hooks, dependencies, installation behavior or manual indexes.
- Blockers: None; Phase 5b and Phase 5 are complete.
- Unverified local/CI differences: Local browser verification used macOS/arm64, Chrome 151, the cached Playwright Chromium headless shell and explicit `test_site` on `127.0.0.1:8001`. CI uses Ubuntu and serves `test_site` at `test_site:8000`; no Phase 5b dependency or runner configuration changed.

### 2026-08-26 — Phase 6 parity and hardening slice

- Risk classification: Cross-surface authenticated read-only UI and session-response hardening; no financial calculation, mutation, schema, permission, hook, dependency or legacy redirect changed.
- Required gates: Response allow-list invariant; frontend lint/typecheck/build; focused recovery/session Playwright; complete Playwright and Cypress suites; shared `pre-push` and `pre-push-ui`; clean-site app installation and complete UI verification.
- Commands executed:
  - `bench --site test_site run-tests --module bond_management.bond_management.api.test_investor_response_boundary` — exit `0`; the response-boundary invariant passed for every investor record and report allow-list.
  - `apps/bond_management/scripts/verify.sh frontend` — exit `0`; warning-free frontend lint, typecheck and production build passed.
  - Focused `e2e/tests/investor-hardening.spec.ts` Playwright run — final exit `0`; all 6 route-title, focus, loading, failure/retry, empty, stale-response and session-boundary tests passed.
  - `FRAPPE_USER=... FRAPPE_PASSWORD=... BASE_URL=http://127.0.0.1:8001 apps/bond_management/scripts/verify.sh playwright` with ephemeral local test credentials — exit `0`; all 24 Playwright setup, desktop, mobile and hardening tests passed.
  - `apps/bond_management/scripts/verify.sh pre-push` — exit `0`; pre-commit, blocking/advisory security scans, migration and all 289 server tests passed.
  - `FRAPPE_USER=... FRAPPE_PASSWORD=... BASE_URL=http://127.0.0.1:8001 CHROME_BIN="/Applications/Google Chrome.app/Contents/MacOS/Google Chrome" apps/bond_management/scripts/verify.sh pre-push-ui` with ephemeral local test credentials — exit `0`; the full server, frontend, Cypress and Playwright gates passed.
  - An isolated MariaDB 12.3.2 instance was initialized under `/private/tmp`; `bond_ui_phase6_fresh_20260826b` was created, the app installed, migrated and configured, then `TEST_SITE=bond_ui_phase6_fresh_20260826b ... apps/bond_management/scripts/verify.sh pre-push-ui` — exit `0`; the same 289 server tests and complete frontend, Cypress and Playwright gates passed on the new site.
  - Final continuation checks reran `bench --site bond_ui_phase6_fresh_20260826b migrate` and its complete app suite, followed by the exact local `apps/bond_management/scripts/verify.sh pre-push` command — exits `0`; clean-site and canonical-site server suites remained green.
  - `yarn --cwd frontend lint`, `yarn --cwd frontend typecheck` and `git diff --check` after aligning Vue formatting rules with the repository Prettier configuration — exits `0` with no lint warnings.
  - `../../env/bin/pre-commit run --files ...` for every Phase 6 changed or new file, Prettier write/check for the tracker and Playwright spec, and `git diff --check` — final exits `0`.
- Exit statuses: Every final required Phase 6 command exited `0`.
- Tests passed: 1 focused response-boundary invariant; 6 focused hardening browser tests; warning-free frontend lint/typecheck/production build; 289 complete server tests; complete 13-test Cypress suite; complete 24-test Playwright suite; clean-site install and complete UI gate.
- Tests failed: Initial focused browser runs used pre-change assets, then exposed that Frappe rejects a logged-out guest with dispatcher `403` before the non-guest endpoint can return `401`. The API adapter now confirms that ambiguous `403` against the website authentication gate and maps only a login redirect to session expiry; an authenticated record denial remains `403`. A shared authentication-state attempt also let the logout case invalidate the next denial test, so the expiry scenario now owns an isolated authenticated context. The first new-site command prompted after an empty database-root password and exited `1`, leaving the unused partial site directory `bond_ui_phase6_fresh_20260826`; the second unique site used an ephemeral root credential and passed installation and all required gates. During final continuation, one `pre-push` attempt found stopped Redis services, one `pre-push-ui` attempt found the explicit test server unavailable before Cypress, and one clean-site check found its isolated MariaDB stopped. The required services and same isolated database were restarted; every final rerun passed. An explicit Prettier check also exposed conflicting Vue whitespace rules; formatting-only Vue rules now defer to repository Prettier, and final frontend lint is warning-free.
- Tests not run: GitHub Actions itself was not run in this workspace.
- Blockers: None for Phase 6. Phase 7 requires internal-team and pilot-investor acceptance plus a feature-flag rollback rehearsal.
- Unverified local/CI differences: Local verification used macOS/arm64, Chrome 151, Playwright Chromium, Redis 8.8 and MariaDB 12.3.2. CI uses Ubuntu, MariaDB 11.8 and Redis Alpine. The clean site used the current bench rather than CI's separately initialized run-scoped bench fetched through a local `file://` source; app installation, generated schema, migration and complete gates were exercised, while GitHub Actions remains unobserved.

### 2026-08-26 — Phase 7 pilot readiness and rollback rehearsal

- Risk classification: Operational test-site rollout rehearsal plus documentation; no production site, financial data contract, schema, login redirect, Apps route or legacy Workspace changed.
- Required gates: Capture initial `test_site` flag state; verify enabled and disabled route behavior over HTTP with process reloads; restore and confirm the initial state; run complete server, frontend, Cypress and Playwright gates; format and lint the changed tracker.
- Commands executed:
  - `jq -r '.bond_investor_spa_enabled // "unset"' apps/bond_management/../../sites/test_site/site_config.json` before and after rehearsal — both returned `1`.
  - Explicit `bench --site test_site serve --port 8001 --noreload` processes plus header-only requests to `http://127.0.0.1:8001/bond-investor` before rollback, after disabling, and after restoration. Initial and restored enabled states returned temporary login redirects; disabled state returned `302 Location: /desk/bond-investor` after the test process reloaded site configuration.
  - `bench --site test_site set-config bond_investor_spa_enabled 0`, followed by `bench --site test_site set-config bond_investor_spa_enabled 1` after the redirect check — exits `0`.
  - `FRAPPE_USER=... FRAPPE_PASSWORD=<ephemeral> BASE_URL=http://127.0.0.1:8001 CHROME_BIN="/Applications/Google Chrome.app/Contents/MacOS/Google Chrome" apps/bond_management/scripts/verify.sh pre-push-ui` — exit `0`.
  - Bench-local Prettier, targeted pre-commit and `git diff --check` for this tracker — exits `0`.
- Exit statuses: Every final rehearsal, restoration, shared-gate and tracker-verification command exited `0`.
- Tests passed: Pre-commit and security scans; migration; 289 complete server tests; warning-free frontend lint, typecheck and production build; 13 complete Cypress tests; 24 complete Playwright tests; enabled/disabled/restored HTTP route checks.
- Tests failed: One HTTP request immediately after the first flag write still observed the enabled state because the running development process cached site configuration. Restarting the explicit test server loaded the disabled state and produced the required legacy redirect; the restored state was verified through another clean process.
- Tests not run: Real internal-team acceptance and a real pilot-investor statement/reporting cycle; GitHub Actions itself was not run.
- Blockers: Phase 7 cannot complete until named internal and pilot participants provide acceptance evidence, the real statement/reporting cycle finishes, high-severity defects are closed and the final pilot-site flag state has an approver.
- Unverified local/CI differences: Rollback used local `test_site`, macOS/arm64 and the development server on `127.0.0.1:8001`. Pilot environment hosting, process reload mechanism, participants and data remain external to this workspace.

### 2026-08-26 — Phase 7 Yield Comparison pilot feedback

- Risk classification: Permission-scoped read-only report defaults and client-only chart presentation; no financial calculation, persisted market value, schema, mutation, role, legacy redirect or Desk report changed.
- Required gates: Update settled report UX and API contracts; focused default-date API tests; frontend lint, typecheck and production build; focused desktop/mobile Yield Comparison tests; visual chart inspection; complete server, Cypress and Playwright suites through `pre-push-ui`; final formatting and scoped diff checks.
- Commands executed:
  - `bench --site test_site run-tests --module bond_management.bond_management.api.test_investor_yield_comparison` — exit `0`; 10 tests passed.
  - `apps/bond_management/scripts/verify.sh frontend` — final exit `0`; warning-free frontend lint, typecheck and production build passed.
  - Focused desktop and Pixel 7 Yield Comparison Playwright runs — final exits `0`; each passed authentication setup and its report flow.
  - Authenticated Chromium screenshot of the focused report range — exit `0`; visual inspection confirmed line-only rendering, no point markers and one centered `2095` x-axis label.
  - `FRAPPE_USER=... FRAPPE_PASSWORD=<ephemeral> BASE_URL=http://127.0.0.1:8001 CHROME_BIN="/Applications/Google Chrome.app/Contents/MacOS/Google Chrome" apps/bond_management/scripts/verify.sh pre-push-ui` — exit `0`.
  - Bench-local Prettier, targeted pre-commit, warning-free ESLint/typecheck and `git diff --check` for changed files — final exits `0`.
- Exit statuses: Every final required command exited `0`.
- Tests passed: 10 focused API tests; focused desktop and Pixel 7 report flows; pre-commit and security scans; migration; 291 complete server tests; warning-free frontend lint, typecheck and production build; 13 complete Cypress tests; 24 complete Playwright tests.
- Tests failed: Initial focused desktop/mobile assertions showed that Chromium did not expose an SVG `<desc>` as the chart's accessible description. A visually hidden HTML description linked with `aria-describedby` preserved point details without restoring markers; focused and complete reruns passed. Prettier also restored two non-blocking Vue void-element warnings; ESLint normalization removed them before final gates.
- Tests not run: GitHub Actions itself was not run. Fresh-site validation was not required because this slice changed no schema, hooks, dependencies, installation behavior or manual indexes.
- Blockers: None for this feedback slice. Phase 7 still requires named internal-team and pilot-investor acceptance, a real statement/reporting cycle and final pilot-site flag approval.
- Unverified local/CI differences: Local browser verification used macOS/arm64, Chrome 151, Playwright Chromium and explicit `test_site` on `127.0.0.1:8001`. CI uses Ubuntu and serves `test_site` at `test_site:8000`; no runner or dependency changed.

### 2026-08-26 — Pull request CI follow-up

- Risk classification: Test formatting, frontend formatter ownership, Playwright origin configuration and manual CI dispatch support; no financial calculation, API projection, schema, permission, mutation or legacy route changed.
- Required gates: Inspect the exact failed GitHub Actions logs; pre-commit and security scans; migration and complete server suite; frontend lint, typecheck and production build; complete Cypress and Playwright suites; shared `pre-push-ui`; manually dispatched GitHub Actions on the pushed revision because GitHub did not create a check suite for the pull-request synchronization or reopen events.
- Commands executed:
  - `gh run view 32968173294 --log-failed` and `gh run view 32968173299 --log-failed` — exits `0`; confirmed Ruff/Prettier rewrites, a root ESLint dependency-boundary failure and clipboard failures on the non-secure `test_site` browser origin.
  - `FRAPPE_USER=... FRAPPE_PASSWORD=<ephemeral> BASE_URL=http://127.0.0.1:8001 CHROME_BIN="/Applications/Google Chrome.app/Contents/MacOS/Google Chrome" apps/bond_management/scripts/verify.sh pre-push-ui` — exit `0`.
- Exit statuses: Every final local command above exited `0`.
- Tests passed: Pre-commit and security scans; migration; 291 complete server tests; warning-free frontend lint, typecheck and production build; 13 complete Cypress tests; 24 complete Playwright tests, including both clipboard flows.
- Tests failed: No local test failed. The preceding GitHub revision failed Server and Frappe Linter because committed files did not match Ruff/Prettier and the root ESLint hook entered the separately managed frontend without its dependencies; Playwright failed both clipboard flows because `http://test_site:8000` was not a secure browser context. The fixes use the repository formatters, keep frontend ESLint under its installed frontend toolchain and use the loopback `localhost` origin in CI.
- Tests not run: GitHub Actions on the follow-up commit remains pending until push and manual dispatch.
- Blockers: None for pushing the CI follow-up.
- Unverified local/CI differences: Local verification used macOS/arm64, Chrome 151, Playwright Chromium and explicit `test_site` on `127.0.0.1:8001`. The manually dispatched GitHub runs will verify Ubuntu, MariaDB 11.8, Redis Alpine and the CI-owned fresh bench/site with `localhost:8000`.

## Next slice: Phase 7

Record named internal-team acceptance and one complete statement/reporting cycle
with pilot investors. Close any high-severity defects, rerun affected and
complete UI gates after changes, then record the approved pilot-site flag state.
Do not begin cutover until those acceptance gates are recorded.

## Blockers and deviations

Phase 7 depends on pilot participants, acceptance evidence and an approved final
pilot-site flag state. Rollback mechanics are rehearsed locally. The Phase 6
fresh-site workaround used an isolated MariaDB 12.3 server because the shared
MariaDB root credential is intentionally unavailable; it did not touch or
recreate an existing site.

When implementation changes a settled decision, record the reason here during the slice and update the specification before marking that slice complete.
