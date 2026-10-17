# 0011: Accrued-interest valuation is net of withholding tax

- Status: Accepted
- Date: 2026-10-16

## Context

The bank deducts withholding tax before it pays coupons or accrued interest to
the investor. The XIRR cash-flow builders already value accrued interest net of
tax ([0005](0005-cash-flow-signs.md)), but the Portfolio Performance row valued
it gross. With a nonzero `withholding_tax`, the displayed market value and gain
could not reconcile to the report's terminal cash flows or XIRR. Paths below
are relative to `bond_management/bond_management/`.

## Decision

- Portfolio Performance values accrued interest on the valuation date net of
  the bond's `withholding_tax`, through `utils/xirr.py:apply_withholding_tax`
  (`report/portfolio_performance/portfolio_performance.py:get_data`).
- `market_value` (and `market_value_usd`) is therefore
  `effective_quantity × (face_value_per_unit × price / 100 + net accrued interest)`,
  and equals the sum of the past `market_price` and `accrued_interest` flows.
- `gain_value = market_value + proceeds_value - purchases_value` is unchanged
  in form and now uses the net market value.

## Consequences

- With withholding tax, market value and gain are lower than before by the tax
  on accrued interest; with zero tax nothing changes.
- The Investor SPA shows the same server values; it computes nothing itself.
- Regression test:
  `report/portfolio_performance/test_portfolio_performance.py::test_market_value_and_gain_use_accrued_interest_net_of_withholding_tax`.
