# Bond Management domain model

This is a source-derived map of the current app, not a proposed schema. The app
has six standalone DocTypes and four child-table DocTypes.

## How to read the graphs

- An edge label is the field that creates the relationship.
- Solid edges are ordinary `Link` or `Table` relationships.
- Dotted edges are persisted links maintained by server code.
- Child tables have Frappe's implicit `parent`, `parenttype`, and `parentfield`
  fields.

## DocType relationships

```mermaid
flowchart TB
    subgraph Setup["Setup"]
        BP["Bond Portfolio"]
        BM["Bond Master<br/>name = ISIN"]
        BCS[["Bond Coupon Schedule<br/>child table"]]
        BPS[["Bond Principal Schedule<br/>child table"]]
    end

    subgraph Activity["Portfolio activity"]
        BT["Bond Transaction"]
        BS["Bond Statement"]
        BSD[["Bond Statement Details<br/>child table"]]
    end

    subgraph Market["Market data"]
        BMD["Bond Market Date"]
        BMP[["Bond Market Prices<br/>child table"]]
        BER["Bond Exchange Rate"]
    end

    BM -->|"coupon_schedule"| BCS
    BM -->|"principal_schedule"| BPS

    BT -->|"portfolio_name"| BP
    BT -->|"isin"| BM
    BS -->|"portfolio_name"| BP
    BS -->|"bond_statement_details"| BSD
    BSD -->|"isin"| BM

    BMD -->|"bond_market_prices"| BMP
    BMP -->|"isin"| BM
    BS -.->|"market_price_posting"| BMD
    BER -.->|"statement"| BS
```

`Bond Master` and `Bond Exchange Rate` also link to Frappe's `Currency`
DocType. Statement and transaction attachments use private Frappe `File`
records; those framework relationships are omitted above to keep the domain
graph focused.

## Main processing flow

```mermaid
flowchart LR
    SPDF["Statement PDF"] --> BS["Bond Statement"]
    TPDF["Transaction PDF"] --> BT["Bond Transaction"]

    BS -->|"holdings"| BSD["Statement Details"]
    BS -->|"prices"| MARKET["Market Date + Prices"]
    BS -->|"FX rates"| FX["Exchange Rates"]
    BS --> REPORT["Reconciliation report"]

    DATA["Portfolios + transactions<br/>+ bonds + market data + FX"]
    PP["Portfolio Performance"]
    YIELD["Bond Yield Comparison"]
    API["Read-only investor API"]
    SPA["Investor app"]

    DATA --> PP
    MARKET --> YIELD
    PP --> API
    YIELD --> API
    API --> SPA
```

Desk owns financial writes. The investor app reads fixed, permission-scoped API
projections.

## Important behavior

- `Bond Transaction` is the portfolio ledger.
- Saving a `Bond Statement` derives holdings, market prices, exchange rates,
  reconciliation status, and a private reconciliation report.
- A statement-derived exchange rate links back to its statement; a manual rate
  does not.
- Portfolio performance combines all core financial data. Yield comparison
  reads persisted market snapshots.

## Source anchors

- [DocType metadata](../bond_management/bond_management/doctype/)
- [Statement-derived data](../bond_management/bond_management/doctype/bond_statement/bond_statement.py)
- [Performance inputs](../bond_management/bond_management/utils/performance.py)
- [Investor API](../bond_management/bond_management/api/investor.py)
