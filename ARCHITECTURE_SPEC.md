# Bond Management Architecture Spec

## Goal

Make financial-document ingestion, derived persistence, and Desk workflows
portable, retryable, and easy to test without changing bond cash-flow,
rounding, permission, or file-privacy semantics.

This is a follow-up specification. It records work that still needs an
explicit implementation slice; it does not restore or replace deleted review
progress files.

## Current evidence

- `bond_management/bond_management/utils/private_attachment.py` still has two
  distinct concerns: reading private content through `File` and canonicalizing
  attachment names. Canonicalization currently depends on local filesystem
  paths. Remote/private storage behavior needs an explicit adapter contract.
- `statement_pdf.py` and `transaction_pdf.py` parse different document formats
  but share account identity, password, private-file, and failure-boundary
  rules. Shared identity behavior must stay format-independent.
- `statement_quantity_report.py` owns generated private files. Replacement,
  obsolete-file cleanup, after-commit behavior, and cleanup failure logging
  must remain idempotent and observable.
- `bond_statement.py` runs exchange-rate synchronization and report generation
  synchronously during document updates. A future retry/status design must not
  expose a durable success before every derived write is confirmed.
- `bond_market_date.js` combines server recalculation, clipboard export, and
  SVG rendering. `bond_transaction.js` combines PDF selection/attachment state
  and amount calculation. Their seams should be split only when a concrete
  change needs the seam.
- Existing Cypress specs cover client state and serialization with stubs. A
  small server-backed smoke path is still needed for attachment upload,
  authoritative PDF response, save, and generated report/file behavior.
- Generated PDFs cover parser-shaped text and malformed/password cases. Add a
  small sanitized real-document corpus before claiming layout/font/encoding
  compatibility.

## Non-goals

- No change to financial conventions, date semantics, principal-factor rules,
  cash-flow signs, or Decimal precision.
- No public attachment URLs or guest access.
- No background job or optimistic financial state without an approved retry and
  idempotency contract.
- No broad module split based only on line count.

## Design requirements

### Private file adapter

Create one narrow storage adapter for private financial documents. It must:

1. resolve a `File` through Frappe permissions;
2. return bytes, original filename, content size, and storage identity;
3. enforce private-file and maximum-size rules before parsing;
4. support local and configured remote storage through Frappe's storage hook,
   or fail with a clear deployment error when canonical rename is unsupported;
5. never expose passwords, signed URLs, or storage credentials in logs/errors;
6. make canonicalization idempotent for same-content retries;
7. serialize same-target operations with a documented DB/storage lock strategy;
8. clean temporary objects only after transaction outcome is known.

Canonical names remain derived from validated account/date values. Path
components, URL schemes, and client filenames are never trusted as storage
identifiers.

### Derived persistence

Treat statement-owned exchange rates and reconciliation reports as one logical
update:

- document save owns the transaction;
- generated files have one current owner and stable replacement identity;
- retries produce the same final rows/files;
- failures preserve traceback context and expose a retryable status or clear
  next action;
- after-commit cleanup is safe when the target was already deleted;
- delete operations remove only files owned by the statement.

If a future async path is approved, define job key, retry limit, stale-state
behavior, permission boundary, and user-visible pending/failed states first.

### Client/server contract

For PDF attachment, calculation, schedule, report, and clipboard flows:

- server values are authoritative;
- every async handler returns its Promise;
- stale responses cannot mutate newer form state;
- failed calls leave fields editable and show a recovery action;
- durable success is shown only after server confirmation;
- numeric serialization occurs only at the report/clipboard boundary;
- clipboard text escapes tabs/newlines and formula prefixes while preserving
  numeric cells.

### Module boundaries

Use deletion tests before splitting modules. Candidate seams:

- private storage read/copy/replace adapter;
- account identity and canonical filename policy;
- market-data calculation, clipboard serialization, and chart rendering;
- transaction PDF parsing/selection and amount calculation;
- report context loading, financial calculation, and output serialization.

Each extracted public module gets a small typed interface and focused tests.
Do not duplicate parser or permission logic across adapters.

## Test plan

### Unit and integration

- local, remote, public, missing, malformed, oversized, and conflicting-target
  attachment cases;
- same-content canonicalization retry, different-content collision, rollback,
  commit cleanup, and concurrent same-target attempts;
- current and legacy statement/transaction layouts from sanitized fixtures,
  including font, positioning, encoding, metadata, and wrapped-line variation;
- statement report replacement, stale-file cleanup, failed cleanup logging, and
  safe parent deletion;
- migration/index/permission bootstrap on fresh and existing sites;
- test factories must create isolated market-date parents unless a test passes
  an explicit parent for an intentional same-date multi-bond case;
- equality and both sides for every financial comparison boundary.

### Cypress

Add one focused server-backed smoke spec covering:

1. private PDF attachment;
2. server extraction of portfolio/date or transaction values;
3. save with server-authoritative fields;
4. generated private report/file visibility for the owning record; and
5. failed extraction recovery without losing newer form input.

Keep existing stubbed specs for deterministic client formatting, stale-response,
and clipboard behavior. Do not duplicate the full financial matrix in Cypress.

## Acceptance criteria

- No parser or controller reads a private attachment through a raw local path.
- Remote-storage support is either tested through the configured Frappe storage
  adapter or explicitly rejected before any rename/write attempt.
- Same logical request can be retried without duplicate rates, reports, or
  canonical files.
- A concurrent canonicalization cannot publish conflicting metadata or leave a
  partial target.
- Focused server tests, complete server gate, and (for UI changes) complete UI
  gate pass on `test_site` and CI fresh-site setup.
- The spec's unresolved deployment/storage decisions are approved before the
  next implementation slice starts.

## Rollout and compatibility

Keep existing `File` rows, URLs, DocTypes, and public method signatures
backward-compatible. Use normal schema migration for schema-only changes. Add
an idempotent data patch only when transforming existing data. Validate local
and fresh-site behavior before enabling any remote-storage or async path.

## Bond yield comparison report

### Goal and user outcome

Provide one Desk report that compares the stored Future XIRR history of
selected bonds over a date range. Users can add or remove bonds from the
checkbox table below the chart, inspect the underlying market snapshots, and
distinguish currencies by chart colour.

### Non-goals and source of truth

Do not add a second yield-history DocType or recalculate historical values from
current Bond Master terms. The report reads `Bond Market Date.date` and its
`Bond Market Prices` child rows, using the server-persisted `future_xirr` and
market price values as-of each market snapshot.

### Data, chart, and permission contract

The Script Report is backed by Bond Market Date report permission and returns
one row per readable bond and market date, ordered by date and ISIN. Filters
are optional from date and to date; API callers may also pass a bond subset,
while the Desk report lists all readable bonds in the date range. The chart uses
year labels and one line per selected bond; all lines with the same bond
currency use the same deterministic currency colour. Bond selection is shown
in a table below the chart with one checkbox per bond and a currency column.
The table has a select-all checkbox, and its individual checkboxes control the
lines shown. The report rows retain every market snapshot for audit, while the
chart connects each finite value to the next finite value for each selected
bond and leaves missing snapshots out of the line. This avoids Frappe Charts
converting missing values to false zeroes; missing values are never
interpolated. Lines are rendered without point markers or a chart legend/key.
Hovering a line shows only that line's ISIN and Future XIRR value. Audit rows
are copied as tab-separated values by the Copy audit data to Excel action
instead of being rendered in a second data table.

Only rows whose Bond Master is readable are returned. Read-only investors may
run the report without receiving write, import, or mutation access.

### Failure, rollout, and tests

Reject malformed filter types, invalid date ranges, and unreadable bonds at the
report boundary. Add server tests for filtering, ordering, stored-value use,
currency metadata, permissions, and empty results. Add one Cypress smoke test
that selects multiple bonds, verifies the report request, and checks that the
chart renders with one dataset per selected bond and currency-derived colours.
Add the report to the Bond Investor workspace and bootstrap its report
permission idempotently for fresh installs and migrations.
