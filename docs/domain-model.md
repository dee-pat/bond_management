# Bond Management domain model

This document maps the current persisted DocType relationships and the main
runtime dependencies between capture, derived data, analytics, and user-facing
surfaces. It is source-derived rather than a proposed schema: update it when
DocType metadata or relationship-owning services change.

## Legend

- Solid edges represent persisted `Link` or `Table` relationships.
- Dotted edges represent runtime reads, derived writes, or service dependencies.
- Frappe child tables also carry the implicit `parent`, `parenttype`, and
  `parentfield` relationship fields.

## DocType relationships

```mermaid
flowchart LR
    subgraph Reference["Reference / instrument data"]
        BM["Bond Master<br/>(name = ISIN)"]
        CUR["Currency<br/>(Frappe core)"]
        BCS[["Bond Coupon Schedule<br/>(child table)"]]
        BPS[["Bond Principal Schedule<br/>(child table)"]]
    end

    subgraph Operations["Portfolio / capture"]
        BP["Bond Portfolio"]
        BT["Bond Transaction"]
        BS["Bond Statement"]
        BSD[["Bond Statement Details<br/>(child table)"]]
    end

    subgraph Market["Market / FX"]
        BMD["Bond Market Date"]
        BMP[["Bond Market Prices<br/>(child table)"]]
        BER["Bond Exchange Rate"]
    end

    FILE["File<br/>(Frappe private storage)"]

    BM -->|"Table: coupon_schedule (1:N)"| BCS
    BM -->|"Table: principal_schedule (1:N)"| BPS
    BMD -->|"Table: bond_market_prices (1:N)"| BMP
    BS -->|"Table: bond_statement_details (1:N)"| BSD

    BT -->|"Link: isin (N:1)"| BM
    BT -->|"Link: portfolio_name (N:1)"| BP
    BS -->|"Link: portfolio_name (N:1)"| BP
    BS -->|"Link: market_price_posting (N:1, derived)"| BMD
    BER -->|"Link: statement (optional PDF owner)"| BS
    BMP -->|"Link: isin (N:1)"| BM
    BSD -->|"Link: isin (N:1)"| BM

    BM -->|"Link: currency"| CUR
    BER -->|"Link: from_currency"| CUR
    BER -->|"Link: to_currency"| CUR

    BS -.->|"Attach: statement PDF + reconciliation report"| FILE
    BT -.->|"Attach: transaction PDF"| FILE
```

## Runtime and reporting dependencies

```mermaid
flowchart TB
    FILE["Private PDF via Frappe File API"]

    SPF["statement_pdf.py<br/>parse identity, holdings, prices, FX"]
    TPF["transaction_pdf.py<br/>parse transaction rows"]

    BS["Bond Statement"]
    BT["Bond Transaction"]
    BP["Bond Portfolio"]
    BM["Bond Master"]

    SMP["statement_market_prices.py"]
    SER["statement_exchange_rates.py"]
    REC["Quantity reconciliation<br/>+ generated report"]

    BMD["Bond Market Date<br/>+ Bond Market Prices"]
    BER["Bond Exchange Rate"]

    CTX["load_portfolio_performance_context()"]
    PP["Portfolio Performance"]
    YIELD["Bond Yield Comparison"]

    API["Investor API<br/>investor.py + investor_reports.py"]
    SPA["Vue investor app<br/>/bond-investor"]
    DESK["Bond Investor Desk workspace"]

    FILE -.-> SPF
    FILE -.-> TPF

    SPF -->|"authoritative PDF values"| BS
    TPF -->|"authoritative PDF values"| BT
    SPF -.-> BP
    SPF -.-> BM
    TPF -.-> BP
    TPF -.-> BM

    BS --> REC
    BS --> SMP
    SMP -->|"upsert by statement date"| BMD
    BS --> SER
    SER -->|"statement-owned rates"| BER

    BP -.-> CTX
    BT -.-> CTX
    BM -.-> CTX
    BMD -.-> CTX
    BER -.-> CTX
    BS -.-> CTX

    CTX --> PP
    BM -.-> YIELD
    BMD -.-> YIELD

    PP --> API
    YIELD --> API
    API --> SPA
    DESK --> BS
    DESK --> BT
    DESK --> BM
    DESK --> BMD
    DESK --> BER
```

## Relationship notes

- `Bond Master` is the reference hub. Its name is the ISIN, and it owns coupon
  and principal schedules as child tables.
- `Bond Transaction` is the portfolio ledger. Each transaction links one bond
  to one portfolio.
- `Bond Statement` is the ingestion and reconciliation hub. Saving a statement
  can populate statement-detail rows, update the market snapshot for its date,
  synchronize statement-owned exchange rates, and generate a private
  reconciliation report.
- `Bond Market Prices` and `Bond Statement Details` each link their row to a
  `Bond Master` in addition to belonging to their respective parent table.
- `Bond Exchange Rate.statement` is optional: statement-derived rates point
  back to their owning statement, while manually maintained rates do not.
- Portfolio performance reads transactions, bond terms and schedules, market
  prices, and exchange rates. Yield comparison reads persisted market-date
  snapshots and filters them through readable `Bond Master` records.
- The investor application is read-only and receives fixed projections through
  the investor API; financial mutations remain in Desk workflows.

## Source anchors

- [DocType metadata](../bond_management/bond_management/doctype/)
- [Bond Statement controller](../bond_management/bond_management/doctype/bond_statement/bond_statement.py)
- [Market-price synchronization](../bond_management/bond_management/utils/statement_market_prices.py)
- [Exchange-rate synchronization](../bond_management/bond_management/utils/statement_exchange_rates.py)
- [Performance context](../bond_management/bond_management/utils/performance.py)
- [Investor API](../bond_management/bond_management/api/investor.py)
