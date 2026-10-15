# 0005: Cash-flow signs follow the investor

- Status: Accepted
- Date: 2026-10-15 (recorded after the fact)

## Context

XIRR, gain, and the cash-flow exports combine transaction settlements with
coupons, principal repayments, and a terminal valuation. XIRR only has a
solution when the series mixes outflows and inflows, so every builder must
use one sign convention. Paths below are relative to
`bond_management/bond_management/`.

## Decision

- Stored Bond Transaction amounts carry no direction sign.
  `settlement_amount` is `principal + accrued_interest_paid` for both Purchase
  and Sale; the direction comes from `transaction_type`
  (`doctype/bond_transaction/bond_transaction.py:_calculate_amount_values`).
- Cash flows are signed from the investor's side: money paid out is negative,
  money received is positive.
- Past cash flows (`utils/xirr.py:create_past_cash_flows`):
  - a purchase is `-settlement_amount` and a sale is `+settlement_amount`, both
    on the transaction's `settlement_date`;
  - coupons and principal repayments are positive;
  - the terminal market value and accrued interest on the valuation date are
    positive, valuing the position held at that date.
- Future cash flows (`utils/xirr.py:create_future_cash_flows`) model buying at
  the market price on the valuation date: market value and accrued interest on
  that date are negative, and later coupons and principal repayments are
  positive. Every amount is then multiplied by the requested quantity.
- A principal repayment on the maturity date has type `sale`; earlier ones are
  `amortisation` (`utils/xirr.py:_principal_flow_type`).
- Withholding tax reduces only coupons and accrued interest
  (`utils/xirr.py:apply_withholding_tax`); it is not applied to transaction
  settlements, market value, or principal.
- Both builders drop zero amounts and quantize each amount with
  `quantize_money` (`utils/xirr.py:round_cashflow_amounts`).
  `consolidate_cashflows` sums flows on the same date before the solver runs.
- The Portfolio Performance report derives its totals from these signs
  (`report/portfolio_performance/portfolio_performance.py`):
  `purchases_value = -(sum of purchase flows)`, `proceeds_value` is the sum of
  `sale`, `coupon`, and `amortisation` flows, and
  `gain_value = market_value + proceeds_value - purchases_value`.

## Consequences

- Reversing the sign of any flow type changes XIRR, gain, and exports at once;
  it needs a superseding record and tests across the past and future builders.
- Because maturity repayments are typed `sale`, `proceeds_value` already
  includes them; a new flow type must be added to these totals deliberately.
- A new cash-flow source must emit investor-signed amounts and go through
  `round_cashflow_amounts`.

## Open questions

- Why maturity-date repayments share the `sale` type with transaction sales,
  rather than a type of their own, is not recorded.
- Why withholding tax applies to the accrued interest in the terminal and
  future valuation lines, but the accrued interest inside transaction
  settlement amounts is used gross, is not recorded.
