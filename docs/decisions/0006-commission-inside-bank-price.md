# 0006: Commission is already inside the bank price

- Status: Accepted
- Date: 2026-10-15 (recorded after the fact)

## Context

Bank transaction confirmations report a price, a principal, a settlement
amount, and a commission as a percentage, an amount, or both. The price the
bank prints already includes its commission, so adding commission to the
settlement again would overstate the cost of a purchase. Paths below are
relative to `bond_management/bond_management/`.

## Decision

- `commission` on Bond Transaction is a percentage of original principal
  (`face_value_per_unit × quantity_face_value`), not of the price-based
  principal (`doctype/bond_transaction/bond_transaction.py:_calculate_amount_values`).
- `commission_amount = original_principal × commission / 100`, quantized with
  `quantize_money`. It is informational.
- `principal` uses the commission-inclusive price
  (`calculate_transaction_principal_value`), and
  `settlement_amount = principal + accrued_interest_paid`. Commission is not
  added to either.
- `transaction_amount = settlement_amount - commission_amount` for both
  Purchase and Sale.
- XIRR uses `settlement_amount` only and never adds `commission_amount`
  (`utils/xirr.py:create_past_cash_flows`).
- Commission must be zero or greater
  (`BondTransaction.validate_financial_terms`).
- When reading a transaction PDF
  (`utils/transaction_pdf.py:_parse_commission` and
  `get_transaction_attachment_details`):
  - a valid `Commission %` is the primary source, even when an amount is also
    present; the amount labels must still parse;
  - without a percentage, `Commission Amount` or `Commission` is converted to a
    percentage of original principal; two amount labels with different values
    are rejected;
  - blank and `N/A` commission values mean zero, and a negative amount is
    rejected;
  - a row with no commission label at all is rejected;
  - the resulting percentage is stored with `quantize_percent`.

## Consequences

- Changing the basis to price-based principal, or adding commission to
  settlement, changes stored amounts and every past XIRR; it needs a
  superseding record and boundary tests.
- A data source whose price excludes commission would have to convert at its
  boundary.

## Open questions

- Why commission is computed on original principal rather than on the
  price-based principal is not recorded.
- What `transaction_amount` (settlement less commission, for either direction)
  is meant to represent is not recorded beyond the field description; no
  calculation in the app reads it.
- `docs/plans/review-fix-1.md` confirms the blank/N/A-as-zero and
  percentage-first parsing rules were kept deliberately but gives no reason.
