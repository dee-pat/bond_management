# Browser test guide

Playwright specs are organized by product surface, with fixtures and helpers
beside each surface's tests:

```text
e2e/
├── investor/
│   ├── auth.setup.ts
│   ├── fixtures.ts
│   ├── helpers/
│   └── *.spec.ts
└── desk/
    ├── auth.setup.ts
    ├── fixtures.ts
    ├── helpers/
    └── *.spec.ts
```

The shared Playwright configuration stays at the app root. Investor and Desk
use separate authentication setup because their browser permissions differ.

## Ownership

- Python tests own financial rules and report calculations, permissions, API
  validation, migrations, and data invariants.
- Playwright owns visible investor SPA behavior and Desk wiring: routes,
  navigation, rendering, responsive behavior, and browser-to-Frappe integration.
  Keep browser permission coverage to a representative allowed-data flow;
  Python tests own the full role and portfolio matrix.
- Investor specs live in `e2e/investor/`; Desk form, report, and attachment
  specs live in `e2e/desk/`. The [investor migration spec](../docs/specs/investor-ui-migration.md)
  records the Playwright coverage and boundaries.

## Accounts and fixture lifecycle

The Playwright gate migrates the canonical `bond-management-test.localhost`, enables the investor
SPA, then calls
`bond_management.bond_management.tests.investor_ui_seed.seed_investor_ui_browser_test_data`
as Administrator. The idempotent helper ensures deterministic synthetic
portfolios, bonds, market data, transactions, statements, private PDF fixtures,
and a user named by `FRAPPE_USER`. That user receives the Investor role and a
portfolio assignment; `FRAPPE_PASSWORD` sets its password.

CI applies this setup before starting its fresh-site web server so the process
loads the enabled feature flag. The `ui` verification mode repeats migration,
configuration, and fixture seeding before each Playwright run.

The investor authentication setup logs in as that investor, confirms the
investor route, and saves Playwright storage state under the ignored
`e2e/.auth/` directory. The separate Desk setup saves Administrator state for
Desk specs. Seeded investor records remain on `bond-management-test.localhost` after the run; there
is no teardown. The seed helper ensures the same named fixture records on later
runs. Administrator and Manager access matrices are covered by server route
and API tests; the investor account is never elevated to Administrator.

## Real and synthetic behavior

Browser flows use a real Frappe session, the app's SPA, and real investor APIs
against seeded test-site documents. Seeded financial records and blank private
PDFs are synthetic and exist only for repeatable tests. Playwright may stub an
investor API response in a focused case for controlled loading, failure,
recovery, or edge-state presentation; such responses do not test business
calculations or permissions.

The investor SPA is read-only: create, edit, delete, submit, cancel, upload,
PDF parsing, and internal operations are outside its browser scope. Chart
checks assert user-visible labels and values, not SVG geometry or chart-library
internals, as specified in the migration plan.

## Running the suite

Use [`scripts/verify.sh`](../scripts/verify.sh) and follow
[`docs/verification.md`](../docs/verification.md) for the supported gates,
site setup, credentials, and URL overrides. The shared script prepares the
test site and seeds the browser fixture before Playwright runs; do not use a
development or production site for these tests.
