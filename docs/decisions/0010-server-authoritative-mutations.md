# 0010: Financial and attachment mutations are server-authoritative

- Status: Accepted
- Date: 2026-10-15 (recorded after the fact)

## Context

Desk forms let users type amounts, attach bank PDFs, and edit schedules, and
any field the browser sends can be altered regardless of Desk `read_only`
settings. Stored financial values must match the source PDF and the Bond
Master that produced them. `ARCHITECTURE_SPEC.md` lists "no background job or
optimistic financial state without an approved retry and idempotency
contract" as a non-goal. Paths below are relative to
`bond_management/bond_management/`.

## Decision

### Controllers recompute on save

- Bond Transaction (`doctype/bond_transaction/bond_transaction.py`):
  `validate` copies `BOND_SNAPSHOT_FIELDS` from Bond Master
  (`set_authoritative_bond_snapshot`) and recomputes `principal`,
  `commission_amount`, `settlement_amount`, `transaction_amount`, and
  `accrued_interest_calculated` (`calculate_amounts`), replacing any submitted
  values.
- Bond Master: `validate` recomputes `quantity_change`, `maturity_date`,
  `repayment_percent`, and `coupon_schedule`, and for the Kenya convention
  `first_coupon_date` (`BondMaster._recalculate_schedules`).
- Bond Market Date: `validate` recomputes each price row's derived values
  through `utils/market_data.py:calculate_market_data`
  (`BondMarketDate._recalculate_market_data`).
- Bond Exchange Rate: `before_validate` re-derives the pair from one side
  (`BondExchangeRate._sync_rate_values`). `rate` is the source unless it is
  empty, or unless an existing row changes only `reverse_rate`; then `rate` is
  `1 / reverse_rate`. A positive `rate` then sets `reverse_rate = 1 / rate`.
- Bond Statement: `validate` rebuilds `bond_statement_details` from the
  ledger (`populate_holdings`); when a PDF was read, it sets each row's market
  price from the PDF and sets `reconciliation_status`
  (`BondStatement.validate`).

### Attachments are re-read on the server

- Bond Transaction with a PDF attachment: before validation the server parses
  the private PDF and rejects any difference in the `PDF_MANAGED_FIELDS`
  (`BondTransaction._validate_attachment_row`). After calculation, the
  computed `principal` and `settlement_amount` must match the PDF's values,
  where the PDF reports them, at two decimal places (`validate_pdf_amounts`). A non-PDF attachment is
  rejected unless it is unchanged from the last save. A portfolio different
  from the PDF's is accepted only when set while creating rows from a
  multi-transaction PDF (`create_selected_pdf_transactions`) and left
  unchanged afterwards.
- Bond Statement: when the attachment is new or changed, the server sets
  `portfolio_name` and `statement_date` from the PDF. Otherwise, editing
  `portfolio_name`, `statement_date`, `market_price_posting`, or
  `quantity_reconciliation_report` is rejected, and the PDF is re-read and must
  still match the statement's portfolio and date
  (`BondStatement.before_validate`). The `ignore_statement_pdf` flag that skips
  this is set only by the test factories and the UI seed.
- Statement-derived writes (canonical attachment name, market prices,
  exchange rates, and the reconciliation report) run synchronously in
  `before_save` and `on_update`. An exception in any of them fails the save;
  the `on_update` steps also log the failing stage
  (`BondStatement._run_update_side_effect`).
- Desk `read_only` on PDF-managed fields is only a convenience
  (`bond_transaction.js:set_pdf_fields_read_only`,
  `bond_statement.js:set_portfolio_field_read_only`).

### Desk previews are value-only and discard stale responses

- Forms preview server results through endpoints that return values, never a
  Document: `get_calculated_amounts` and `read_transaction_pdf` (Bond
  Transaction), `get_recalculated_schedules` (Bond Master),
  `get_recalculated_market_data` (Bond Market Date), and `read_statement_pdf`
  (Bond Statement).
- Each form numbers its requests and ignores a response when a newer request
  has started (`request_id` checks in `bond_transaction.js`, `bond_master.js`,
  `bond_market_date.js`, and `bond_statement.js`). Saved values still come
  only from the controllers above.
- Two forms derive values locally as a preview, and the server replaces both:
  - Bond Master's `quantity_change` (`bond_master.js:update_quantity_change`),
    replaced by the schedule response and recomputed in `validate`;
  - Bond Exchange Rate's reciprocal, where editing `rate` or `reverse_rate`
    sets the other field to `1 / value` in the browser
    (`bond_exchange_rate.js:sync_exchange_rate`), re-derived on save by
    `BondExchangeRate._sync_rate_values`.

### Investors cannot mutate

- Every investor API endpoint is whitelisted for `GET` only
  (`api/investor.py`, `api/investor_reports.py`).
- For each DocType in `_financial_doctypes` (`hooks.py`), the
  `before_insert`, `before_validate`, `before_cancel`,
  `before_update_after_submit`, and `on_trash` events call
  `utils/investor_shares.py:reject_investor_mutation`, which denies investor
  users.

## Consequences

- A new financial or attachment-managed field must be recomputed or validated
  in its controller; Desk `read_only` alone is not enough.
- Client code must show a pending state until the server responds. A local
  preview of a financial value is allowed only when the controller recomputes
  it on save, as with the two previews above.
- A background job or optimistic update for these values needs an approved
  retry and idempotency contract and a superseding record.

## Open questions

- No record explains why statement-derived writes are synchronous rather than
  queued, beyond the non-goal in `ARCHITECTURE_SPEC.md`.
