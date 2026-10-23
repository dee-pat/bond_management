# Bond Yield Comparison report

## Goal and user outcome

Compare the stored Future XIRR history of selected bonds over a date range.
The investor app (`/bond-investor/yield-comparison`) draws the only chart:
users add or remove bonds from the checkbox table below it, inspect the
underlying market snapshots, and distinguish currencies by line colour. The
Desk script report keeps the same filters and its standard table for audit,
with an "Open chart" button to the investor app.

## Non-goals and source of truth

Do not add a second yield-history DocType or recalculate historical values from
current Bond Master terms. The report reads `Bond Market Date.date` and its
`Bond Market Prices` child rows, using the server-persisted `future_xirr` and
market price values as-of each market snapshot.

## Data, chart, and permission contract

The Script Report is backed by Bond Market Date report permission and returns
one row per readable bond and market date, ordered by date and ISIN. Filters
are optional from date and to date; API callers may also pass a bond subset,
while the Desk report lists all readable bonds in the date range. The
investor chart uses year labels and one line per selected bond; all lines with
the same bond currency use the same deterministic currency colour. Each line
connects finite values only and leaves missing snapshots out; missing values
are never drawn as zero or interpolated. Audit rows are copied as
tab-separated values from the investor app, or exported from the Desk table.

Only rows whose Bond Master is readable are returned. Read-only investors may
run the report without receiving write, import, or mutation access.

## Failure, rollout, and tests

Reject malformed filter types, invalid date ranges, and unreadable bonds at the
report boundary. Add server tests for filtering, ordering, stored-value use,
currency metadata, permissions, and empty results. The investor Playwright spec
covers bond selection, the chart and the audit copy; one Desk smoke test checks
the table and the "Open chart" button.
Add the report to the Bond Investor workspace and bootstrap its report
permission idempotently for fresh installs and migrations.
