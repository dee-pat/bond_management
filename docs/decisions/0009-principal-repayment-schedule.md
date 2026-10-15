# 0009: Principal repayment rows define maturity

- Status: Accepted
- Date: 2026-10-15 (recorded after the fact)

## Context

Bonds can repay principal in one bullet payment or in several amortising
payments. The principal schedule drives the principal factor, repayment cash
flows, weighted average repayment, and the coupon schedule's end date, so its
rows must be unambiguous. Paths below are relative to
`bond_management/bond_management/`.

## Decision

`BondMaster.validate` runs these steps in order
(`doctype/bond_master/bond_master.py:BondMaster._recalculate_schedules`):

- At least one principal schedule row is required
  (`validate_principal_schedule`).
- Every row needs `principal_units` greater than zero (an `Int` field of
  original principal units) and a `repayment_date`.
- Repayment dates are unique after `getdate` normalization; a duplicate date
  is rejected.
- `maturity_date` is set to the latest repayment date
  (`update_maturity_date`). The field is read-only in Desk, so the principal
  schedule is the only way to change maturity.
- `maturity_date` must be after `issue_date` (`validate_dates`).
- `repayment_percent` is derived, never entered: each row except the last in
  table order gets `principal_units / total units × 100`, quantized with
  `quantize_percent`, and the last row gets `100` minus the sum of the others,
  so the percentages total exactly 100 (`update_principal_percentages`).
- After the coupon schedule is regenerated, every repayment date must equal a
  coupon date (`validate_principal_alignment`). For the Kenya convention the
  generator already rejects a repayment date off the 182-day cadence (see
  [0008](0008-coupon-schedule-and-day-count.md)).

## Consequences

- Maturity cannot be edited directly; changing the final repayment changes
  maturity and therefore the whole coupon schedule.
- Because repayments sit on coupon dates, same-day coupon and repayment rules
  apply (see [0004](0004-settlement-date-ledger-position.md)).
- The last row in table order absorbs rounding, so reordering rows can move
  the rounding remainder between rows.
- Allowing a repayment between coupon dates needs a superseding record and
  tests for the principal factor, accrual, and coupon entitlement around it.

## Open questions

- Why repayment dates must align with coupon dates is not recorded.
- Whether the remainder should go to the last row in table order rather than
  the latest repayment date is not recorded; the server does not sort rows by
  date.
