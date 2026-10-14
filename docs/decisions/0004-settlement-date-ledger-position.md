# 0004: Settlement date drives ledger position

- Status: Accepted
- Date: 2026-10-14 (recorded after the fact)

## Context

A trade has a trade date and a later settlement date. Positions, coupon
entitlement, and statement reconciliation must agree with the custodian, and
coupon, repayment, and maturity events can fall on the same day as a
settlement.

## Decision

- Ledger position on a date counts purchases and subtracts sales with
  `settlement_date` on or before that date
  (`utils/portfolio.py:get_ledger_position_from_transactions`).
- Coupon entitlement counts transactions settled before the coupon date. A
  purchase settling on the coupon date counts only when its accrued interest
  paid covers the full coupon (`get_coupon_position_from_transactions`).
- On a repayment date the coupon is paid on the pre-payment factor
  (`utils/xirr.py:_coupon_position_factor`).
- A principal repayment is paid on the end-of-day ledger position at the
  repayment date, so a purchase settling that day receives it and a sale
  settling that day reduces it (`utils/xirr.py:create_past_cash_flows`).
- On a valuation date on or after maturity the holding is redeemed: its
  terminal market value and accrued interest use a position of zero.
- Same-day and maturity-day behavior follows these explicit pre- and
  post-payment rules, never a generic date comparison.

## Consequences

- Trades between trade and settlement date do not change position yet.
- Any rule comparing dates needs greater-than, less-than, and equality tests.

## Open questions

- The reason a same-day purchase's entitlement depends on accrued interest paid
  (rather than always or never counting) is not recorded.
