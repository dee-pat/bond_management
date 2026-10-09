# Interest Difference by Portfolio report

## Goal and user outcome

Provide a Desk report that compares recorded accrued interest calculated with
recorded accrued interest charged for Bond Transactions. Positive means an
investor gain and negative means a loss. Reverse the report's previous sign on
both transaction types: purchases use calculated minus charged; sales use
charged minus calculated. Require one portfolio per run, place its filter
first, and show transaction detail with portfolio/currency totals.

Expose the same fixed report projection in the investor app for the selected
portfolio, with the same optional settlement-date range and currency totals.

## Design and data contract

- Read the persisted `accrued_interest_paid` and `accrued_interest_calculated`
  fields on Bond Transaction; do not recalculate using current Bond Master terms.
- Include purchases and sales.
- Require one portfolio and apply optional inclusive From Date and To Date
  filters to settlement date.
- Display transaction reference, settlement date, currency, ISIN, transaction
  type, calculated interest, charged interest, signed difference, and the
  equivalent signed accrual days under the transaction's saved day-count terms.
- Use the current Bond Master coupon/principal schedule dates for
  convention-specific daily accrual when converting the difference to days.
- Append a total row for each portfolio/currency group with summed monetary
  amounts/difference. Leave equivalent days blank on totals
  because days from different bonds or conventions are not additive. Include a
  language-independent `is_total_row` marker in investor rows so the UI does not
  infer row type from the translated transaction reference.
- Use existing Frappe permission-aware query APIs and portfolio access rules.

## Permissions and consistency

The report is available to Bond Management Manager and Bond Investor Read Only.
The report query must respect Bond Transaction document permissions and the
readable portfolio scope. Values are a read-only projection of saved records.

## Tests and acceptance

Cover signed differences in both directions and equality, grouping by portfolio
and currency, both transaction types, inclusive settlement date filters, and
permission-scoped query behavior. Run the required server and report/UI gates
from `docs/verification.md`.

## Rollout and follow-up

The standard report metadata syncs during migration. No data patch or schema
change is needed. Review the domain-model report flow as part of this change.
