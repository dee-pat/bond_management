# Multi-currency reporting

## Goal

Keep Bond Master, Bond Transaction, and Bond Statement amounts in each bond's
native currency while showing portfolio performance in both native currency
and USD reporting currency.

## Current problem

Bond currency is already captured per Bond Master, but statement PDFs' dated FX
rates are not parsed or persisted, and Portfolio Performance has no reporting-
currency values or mixed-currency USD total.

## Contract and design

- Add a portfolio-scoped `Bond Exchange Rate` record containing the effective
  date, source currency, target currency, rate, source, and optional statement.
- Store rates as target-currency units per one source-currency unit. The
  statement example `KES / USD 0.00772499` is stored as KES -> USD at
  `0.00772499`.
- Parse and reconcile statement-provided rates as desired state. Replacing or
  deleting a statement removes rates that were owned by its previous PDF while
  preserving unrelated manual fallbacks. If a statement has no rate for a
  needed currency/date, the report raises an actionable message telling the
  user to add a manual Bond Exchange Rate record.
- Use the latest available rate on or before each historical cash-flow date
  for past transaction/proceeds conversions. Use the valuation-date rate for
  current market/nominal values and for future cash-flow projections, because
  future FX is unknown.
- Keep nominal, purchase, proceeds, gain, and XIRR values in native currency.
  To keep the report compact, expose only Market Value and XIRR as additional
  USD columns. Mixed native-currency totals are blank, while the USD
  market-value total and USD XIRR remain available. Native TOTAL cash-flow
  export is disabled for mixed portfolios; the USD XIRR column exports the
  converted cash flows used by those values.
- USD bonds use an implicit 1:1 rate and do not require an exchange-rate row.
- Kenya Actual/364 coupon schedules are anchored to the latest contractual
  repayment and generated backwards in exact 182-day steps. The issue-to-first
  coupon stub is prorated, and earlier repayments must match the derived dates.

## Permissions and consistency

- Bond Exchange Rate rows are scoped to the portfolio for investors.
- Bond Management Manager and System Manager can create and maintain manual
  rates.
- Statement-derived rates are server-created from private PDFs and replace a
  manual rate for the same portfolio/date/currency pair when present.
- A controller validation and an idempotent database unique index enforce one
  rate per portfolio/date/source/target currency pair.

## Verification and rollout

- Add parser unit tests for current, missing, invalid, and conflicting rate
  rows, plus integration coverage for statement upsert and manual fallback.
- Add report tests covering native values, USD conversions, mixed-currency USD
  totals, missing-rate guidance, and USD cash-flow serialization.
- Run the targeted server tests, the complete server gate, and the complete UI
  gate because DocTypes, report columns, permissions, and Desk behavior change.
- The feature is backward-compatible for existing USD bonds; existing sites
  need normal schema migration and the idempotent index/permission hooks.
- Registered data patches regenerate legacy Kenya schedules, backfill
  price-adjusted transaction principal, and rerun the v8 statement
  reconciliation under a new Patch Log identity.
