# 0002: Market prices per 100 of original face value

- Status: Accepted
- Date: 2026-10-14 (recorded after the fact)

## Context

Banks quote bond prices per 100 of face value, and statements report them that
way. Amortising bonds repay principal over time, so outstanding principal falls
below the original face value while the quote basis does not change.

## Decision

- Market prices are stored and read as quoted per 100 of original face value.
- One held unit is worth `face_value_per_unit × price / 100 × quantity_factor`
  (`utils/xirr.py:_unit_market_value`). Standard bonds keep a factor of 1. KES
  quantity-change bonds reduce the quantity the quote represents after each
  repayment.
- Statement quantities are either unit counts or monetary nominal
  (`ParsedMarketPrice.quantity_is_face_value`). Only monetary-nominal
  quantities value as `reported_quantity × price / 100`. Legacy rows choose the
  interpretation whose value is closer to the printed market value and reject
  ties (`utils/statement_pdf.py:_legacy_quantity_is_monetary_nominal`).
- The principal factor is never applied a second time to market-price cash
  flows.

## Consequences

- Amortisation changes outstanding principal or the principal factor, not
  transaction quantity, unless a bond follows the KES quantity-change rule.
- A data source quoting on outstanding face would need converting at its
  boundary, or a superseding record.
