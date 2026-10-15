# 0003: Shared exchange rates with statement provenance

- Status: Accepted
- Date: 2026-10-14 (recorded after the fact)

## Context

Statements from different portfolios often report the same currency pair on the
same date. A rate is market reference data rather than portfolio-owned data
(investor UI Phase 4d, [PR #3](https://github.com/dee-pat/bond_management/pull/3)), but each statement
that reported it must stay traceable, and that trace must not leak another
portfolio's statement ([PR #19](https://github.com/dee-pat/bond_management/pull/19)).

## Decision

- Saving a statement writes one canonical `Bond Exchange Rate` row per pair and
  date, plus a `Bond Exchange Rate Source` row per statement recording its
  provenance (`utils/statement_exchange_rates.py`).
- Statements whose rates are equal at the 12-place, half-up storage boundary
  share the canonical row.
- A conflicting value fails the whole statement save. That covers a conflict
  within one PDF, with another statement's source, or with a manual fallback
  rate. Rows within one PDF conflict on any difference in their raw values;
  the other comparisons use the storage boundary above.
- Investors read rate history without a portfolio assignment, but the
  representative statement link is permission level 1 and is returned only when
  the caller can read that statement.

## Consequences

- Statement import is all-or-nothing whenever rates conflict; the user resolves
  the conflict before the statement saves.
- Deleting a statement deletes its source rows and recomputes each affected
  canonical rate (`delete_statement_exchange_rates`). A rate with sources left
  keeps them as provenance; one with none reverts to `Manual` when it has a
  manual fallback and is deleted otherwise.
- Rounding for the comparison is fixed by [0001](0001-decimal-precision-and-rounding.md).
