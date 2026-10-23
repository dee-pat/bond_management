# Decision records

Each file here records one business or architecture decision the app depends
on: what was decided, why, and what it costs. Plans in `docs/plans/` describe
work in progress and can be archived once merged; a decision record stays
current for as long as the code follows it.

## When to write one

Write a record in the same change when a change:

- adopts or changes a financial convention (rounding, precision, signs, price
  basis, effective dates, day counts);
- changes how data is shared, scoped, or derived across DocTypes;
- picks one approach over a credible alternative that a future change might
  revisit.

AGENTS.md requires an explicit business decision before a convention changes.
That decision is a new record, or a status change on an existing one, approved
by the user.

## Lifecycle

Status is `Accepted`, `Superseded by NNNN`, or `Deprecated`. Never rewrite an
accepted record's decision: supersede it with a new number and link both ways.
Recording a decision the code already follows uses status `Accepted` and notes
that it was recorded after the fact.

## Template

```markdown
# NNNN: Title

- Status: Accepted
- Date: YYYY-MM-DD

## Context

The problem and forces at play, with links to code and specs.

## Decision

What the app does, stated so a test could check it.

## Consequences

What follows, including costs and what would have to change to reverse it.

## Open questions

Anything not yet known, such as an unrecorded rationale. Delete when empty.
```

## Index

- [0001: Decimal precision and rounding](0001-decimal-precision-and-rounding.md)
- [0002: Market prices per 100 of original face value](0002-market-price-per-100-original-face.md)
- [0003: Shared exchange rates with statement provenance](0003-shared-exchange-rates.md)
- [0004: Settlement date drives ledger position](0004-settlement-date-ledger-position.md)
- [0005: Cash-flow signs follow the investor](0005-cash-flow-signs.md)
- [0006: Commission is already inside the bank price](0006-commission-inside-bank-price.md)
- [0007: Financial dates are calendar dates normalized with getdate](0007-calendar-dates-normalized-with-getdate.md)
- [0008: Coupon schedules and day-count conventions](0008-coupon-schedule-and-day-count.md)
- [0009: Principal repayment rows define maturity](0009-principal-repayment-schedule.md)
- [0010: Financial and attachment mutations are server-authoritative](0010-server-authoritative-mutations.md)
- [0011: Accrued-interest valuation is net of withholding tax](0011-withholding-tax-on-accrued-valuation.md)
- [0012: Financial documents are never shared](0012-financial-documents-are-never-shared.md)
