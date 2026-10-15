# 0007: Financial dates are calendar dates normalized with getdate

- Status: Accepted
- Date: 2026-10-15 (recorded after the fact)

## Context

Dates reach the app as Date field values, ISO strings from whitelisted calls
and report filters, `DD/MM/YYYY` text in bank PDFs, and `date` objects from
other helpers. Comparing mixed types, or a date against a timestamp, gives
wrong or failing comparisons. Paths below are relative to
`bond_management/bond_management/`.

## Decision

- Every financial date on the app's DocTypes is a `Date` field, never
  `Datetime`: Bond Master `issue_date`, `first_coupon_date`, `maturity_date`;
  Bond Coupon Schedule `coupon_date`, `period_start`, `period_end`; Bond
  Principal Schedule `repayment_date`; Bond Transaction `trade_date`,
  `settlement_date`, `issue_date`, `maturity_date`; Bond Statement
  `statement_date`; Bond Market Date `date`; Bond Market Prices
  `maturity_date`, `weighted_avg_repayment_date`; Bond Exchange Rate
  `rate_date`.
- Shared helpers and controllers pass date inputs through
  `frappe.utils.getdate` before comparing or doing arithmetic, for example
  `utils/coupon_schedule.py:generate_coupon_schedule` and `year_fraction`,
  `utils/accrual.py:get_coupon_period` and `_outstanding_factor`,
  `utils/portfolio.py:get_ledger_position_from_transactions`,
  `utils/xirr.py:consolidate_cashflows`,
  `BondMaster.validate_principal_schedule`, and
  `BondTransaction.validate_transaction_dates`. The Portfolio Performance
  report normalizes its valuation date the same way
  (`report/portfolio_performance/portfolio_performance.py`).
- Bank PDFs give dates as `DD/MM/YYYY` and are parsed with that exact format
  into `date` objects (`utils/statement_pdf.py:_parse_statement_date`,
  `utils/transaction_pdf.py:_parse_date`); the transaction parser also
  requires two-digit day and month.
- Date arithmetic works on unadjusted calendar dates. Day counts are date
  subtractions, schedule steps add or subtract calendar months or days (see
  [0008](0008-coupon-schedule-and-day-count.md)), and no code adjusts a date
  for weekends or holidays.
- Bond Transaction dates must satisfy, inclusively,
  `issue_date <= trade_date <= settlement_date` and both trade and settlement
  dates on or before `maturity_date`
  (`BondTransaction.validate_transaction_dates`).
- Where "today" is a default rather than a stored financial date, it is a date,
  not a timestamp: `frappe.utils.today()` for the yield comparison default
  (`api/investor_reports.py:get_yield_comparison_defaults`) and
  `frappe.datetime.get_today()` for the Portfolio Performance filter default.

## Consequences

- New date inputs must be normalized with `getdate` before comparison, and a
  rule that needs a timestamp must say so explicitly.
- `frappe.utils.getdate` returns the current date for an empty value, so
  normalizing does not detect a missing date. Required-date checks run
  separately, such as `BondTransaction.validate_required_inputs` and the
  repayment-date check in `BondMaster.validate_principal_schedule`.
- Adding business-day adjustment would change coupon dates, accrual, and
  position effective dates; it needs a superseding record.

## Open questions

- The reason for using unadjusted calendar dates rather than a business-day
  convention is not recorded.
