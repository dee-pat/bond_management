# Bond Yield Comparison report

## Goal and user outcome

Provide one Desk report that compares the stored Future XIRR history of
selected bonds over a date range. Users can add or remove bonds from the
checkbox table below the chart, inspect the underlying market snapshots, and
distinguish currencies by chart colour.

## Non-goals and source of truth

Do not add a second yield-history DocType or recalculate historical values from
current Bond Master terms. The report reads `Bond Market Date.date` and its
`Bond Market Prices` child rows, using the server-persisted `future_xirr` and
market price values as-of each market snapshot.

## Data, chart, and permission contract

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

## Failure, rollout, and tests

Reject malformed filter types, invalid date ranges, and unreadable bonds at the
report boundary. Add server tests for filtering, ordering, stored-value use,
currency metadata, permissions, and empty results. Add one Playwright smoke test
that selects multiple bonds, verifies the report request, and checks that the
chart renders with one dataset per selected bond and currency-derived colours.
Add the report to the Bond Investor workspace and bootstrap its report
permission idempotently for fresh installs and migrations.
