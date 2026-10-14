# 0001: Decimal precision and rounding

- Status: Accepted
- Date: 2026-10-14 (recorded after the fact)

## Context

Bond cash flows, accrued interest, yields, and quantities must reconcile with
bank statements and transaction confirmations. Binary floats cannot represent
most decimal amounts exactly, so repeated arithmetic drifts. Rounding happens at
several storage boundaries, and they do not all use the same mode.

## Decision

- Values are built as `Decimal` from strings through
  `utils/financial.py:to_decimal`, which converts `None` and other empty
  values to `Decimal("0")` and rejects other malformed or non-finite input.
  Callers that must distinguish a missing value check for it before
  converting. Values stay `Decimal` through calculation and become floats only in a
  named external-library adapter or at JSON/clipboard serialization.
- Cash and settlement amounts quantize to 4 decimal places, half-even
  (`quantize_money`).
- Calculated percentages quantize to 9 decimal places, half-even
  (`quantize_percent`).
- Exchange rates compare at the 12-place, half-up storage boundary of the rate
  fields (`utils/statement_exchange_rates.py:_stored_rate`); see
  [0003](0003-shared-exchange-rates.md).
- Weighted repayment days round to whole days, half-up (`utils/accrual.py`).

## Consequences

- Each boundary's mode is intentional: switching cash amounts to half-up, or
  rates to half-even, changes stored values and needs a superseding record plus
  boundary tests.
- New calculations reuse `to_decimal` and the quantize helpers instead of
  calling `quantize` with a new precision.

## Open questions

- Why cash and percentages use half-even while rate storage and repayment days
  use half-up is not recorded. `docs/plans/pr9-review-fixes.md` confirms the rate
  boundary was deliberately kept half-up but gives no reason.
