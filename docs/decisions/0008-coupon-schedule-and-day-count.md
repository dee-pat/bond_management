# 0008: Coupon schedules and day-count conventions

- Status: Accepted
- Date: 2026-10-15 (recorded after the fact)

## Context

Coupon cash flows, accrued interest, and principal alignment all depend on
the coupon schedule stored on Bond Master. Bond Master offers three
conventions: 30E/360, ICMA Actual/Actual, and a Kenyan Actual/364 convention
with fixed 182-day periods. Paths below are relative to
`bond_management/bond_management/`.

## Decision

### Schedule generation

- `BondMaster.validate` regenerates `coupon_schedule` on every save through
  `utils/coupon_schedule.py:generate_coupon_schedule`; the table is read-only
  in Desk.
- Coupon dates are generated backwards from `maturity_date`, keeping every
  date strictly after `issue_date`, then sorted ascending.
- Coupon frequency must be a positive divisor of 12. Bond Master offers 1, 2,
  and 4, with 2 as the default.
- For conventions other than Kenya:
  - each step subtracts `12 / coupon_frequency` calendar months from the
    previous generated date, not from maturity;
  - when `maturity_date` is the last day of its month, every generated date is
    moved to the last day of its month;
  - `first_coupon_date`, when set, must be strictly after `issue_date` and
    strictly before `maturity_date`. Generated dates on or before it are
    dropped and it becomes the first coupon date, so the first period is a
    stub from `issue_date`.
- For the Kenya convention:
  - coupon frequency must be 2;
  - each step subtracts 182 days from the previous date;
  - an entered `first_coupon_date` is not used for generation, and
    `BondMaster.regenerate_coupon_schedule` overwrites it with the first
    generated date;
  - every repayment date must fall on a generated date, so the latest
    repayment date (the maturity) anchors the cadence and earlier repayments
    cannot add coupon boundaries.
- Each row stores `coupon_date`; `period_start`, which is the previous coupon
  date or `issue_date` for the first row; `period_end = coupon_date - 1 day`;
  and `coupon_factor = coupon_rate × year_fraction(period_start, coupon_date)`,
  the period's coupon as a percentage of face value. The generator does not
  quantize `coupon_factor`.

### Day-count conventions

`utils/coupon_schedule.py:year_fraction` returns 0 when the end date is not
after the start date. Otherwise:

- `30E/360`: `(Δyears × 360 + Δmonths × 30 + (min(d2, 30) - min(d1, 30))) / 360`.
- `Actual/Actual(ICMA)` (also accepted as `ACT/ACT`): the interval is split
  across notional coupon periods counted back from a reference end date in
  steps of `12 / coupon_frequency` months, kept at month end when the
  reference end is a month end. Each part contributes
  `overlap days / (notional period days × coupon_frequency)`. The reference
  end defaults to the end date and may not be before it.
- `Actual/364(Kenya)` or `ACT/364(Kenya)`, matched case-insensitively
  (`is_kenya_day_count_convention`), and `ACT/364`: `days / 364`.
- `ACT/365`: `days / 365`.
- Any other value raises `ValueError`.

Bond Master's `day_count_convention` field offers only `30E/360`,
`Actual/Actual(ICMA)`, and `Actual/364(Kenya)`, with `30E/360` as the
default.

### Accrued interest

- The accrual period for a settlement date is the schedule row with
  `period_start <= settlement_date <= period_end`
  (`utils/accrual.py:get_coupon_period`). A settlement on a coupon date falls
  at the start of the next period and accrues zero; a date outside every
  period, including the maturity date, accrues zero.
- Kenya convention: `coupon_factor / 100 × face_value_per_unit ×
  elapsed days / period days`, where period days run from `period_start` to
  `coupon_date`. A row without `coupon_factor` uses
  `coupon_rate / coupon_frequency` instead
  (`utils/accrual.py:calculate_accrued_fraction`).
- Other conventions: `coupon_rate / 100 × face_value_per_unit ×
  year_fraction(period_start, settlement_date)`, with the row's `coupon_date`
  as the ICMA reference end.
- The result is scaled by the principal factor at the settlement date
  (`utils/accrual.py:unit_accrued_interest_from_bond`).

## Consequences

- Editing issue date, maturity (through the principal schedule), frequency,
  rate, first coupon date, or convention rewrites the whole coupon schedule on
  the next save; there is no manual schedule override.
- A new convention needs a `year_fraction` branch, a Bond Master option, and
  boundary tests for period ends, month ends, and leap years.
- Because non-Kenya steps are taken from the previous generated date, a day
  clipped in a short month carries into earlier dates when maturity is not a
  month end (for example, a 30 August maturity with semi-annual coupons gives
  28 February, then 28 August of the year before).

## Open questions

- Whether stepping from the previous date (rather than offsetting each date
  from maturity) is intended for non-month-end maturities is not recorded.
- Why the Kenya convention ignores an entered first coupon date, and why its
  accrual is a linear share of the stored coupon while other conventions
  accrue the annual rate times a year fraction, is not recorded.
- Why `year_fraction` still accepts `ACT/ACT`, `ACT/364`, and `ACT/365`, which
  Bond Master does not offer, is not recorded.
