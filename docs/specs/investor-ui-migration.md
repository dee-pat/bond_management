# Investor UI Migration

Status: Approved for phased implementation
Last updated: 2026-08-28
Progress: [investor-ui-migration-progress.md](../plans/investor-ui-migration-progress.md)

## Outcome

Provide bond investors with a responsive, read-only Vue 3 and Frappe UI application at `/bond-investor`. Keep internal operations in Desk and keep the existing investor workspace available until the new application completes a controlled pilot and separate retirement release.

Playwright owns the new application. Cypress continues to own Desk behaviour during coexistence.

## Product boundary

### Users

- `Bond Investor Read Only`: sees only portfolios assigned through existing `User Permission` records.
- `Bond Management Manager` and `Administrator`: may access the investor application for support and acceptance, while continuing operational work in Desk.
- Other authenticated users and guests: cannot access the investor application or its APIs.

### Included investor surfaces

1. Home navigation matching the current investor workspace.
2. Bond Transactions: list and read-only detail.
3. Bond Statements: list and read-only detail.
4. Bond Master: list and read-only detail.
5. Bond Market Dates: list and read-only detail.
6. Bond Exchange Rates: list and read-only detail.
7. Portfolio Performance report.
8. Bond Yield Comparison report.

Before implementing a surface, record its investor-visible fields, filters, sorting and empty/error states in the progress tracker. Functional parity means those behaviours match Desk unless this specification explicitly excludes them.

### Excluded

- Creating, editing, deleting, submitting, cancelling or uploading any record.
- Statement and transaction attachment uploads, PDF parsing and file metadata administration.
- Internal reconciliation, posting, accrual, market-data maintenance and attachment workflows.
- New financial calculations, changed rounding, changed cash-flow rules or redesigned report semantics.
- Replacing internal Desk screens.
- Removing Cypress as part of the investor migration.

## Settled decisions

| Area           | Decision                                                                                                                                |
| -------------- | --------------------------------------------------------------------------------------------------------------------------------------- |
| Delivery       | Incremental migration inside the existing `bond_management` app.                                                                        |
| Frontend       | Vue 3, TypeScript, Frappe UI and Vite under `frontend/`.                                                                                |
| Route          | `/bond-investor`, with nested routes served by a website catch-all rule.                                                                |
| Rollout        | Site-level `bond_investor_spa_enabled` flag. During pilot, login and the Apps screen continue to open `/desk/bond-investor`.            |
| Authentication | Existing same-origin Frappe session; no separate identity system or token store.                                                        |
| Authorization  | Existing investor role and portfolio `User Permission` boundary, enforced again by explicit server APIs.                                |
| Data access    | Explicit read-only investor endpoints with allow-listed inputs and outputs. Generic DocType REST is not the production screen contract. |
| Calculations   | Existing server services and reports remain authoritative. The client formats and presents returned values only.                        |
| Testing        | Playwright for the SPA; Cypress for Desk; server tests own finance and permission matrices.                                             |
| Design         | Functional parity first, with a clean responsive shell but no product redesign.                                                         |
| Retirement     | Cutover and legacy workspace removal are separate releases.                                                                             |

## Architecture

```mermaid
flowchart LR
    Investor[Investor browser] -->|Frappe session| Page[/bond-investor]
    Page --> SPA[Vue and Frappe UI SPA]
    SPA -->|allow-listed GET methods| API[Investor API]
    API --> Permission[Role and portfolio permissions]
    API --> Services[Existing financial and report services]
    Permission --> DB[(Frappe data)]
    Services --> DB

    Internal[Internal team] --> Desk[/desk]
    Desk --> DB
```

### Repository shape

```text
bond_management/
├── frontend/                              # Vue source and frontend dependencies
├── e2e/                                   # Playwright setup, helpers and specs
├── package.json                           # Delegates dev/build to frontend; owns E2E commands
├── playwright.config.ts
└── bond_management/
    ├── hooks.py
    ├── public/frontend/                   # Generated production assets
    ├── www/bond-investor.html             # Generated SPA entry
    ├── www/bond-investor.py               # Feature, session and role gate
    └── bond_management/api/investor.py    # Explicit read-only API
```

The compatibility phase may adjust generated-output locations to match the tested Frappe UI Vite plugin, but the frontend remains inside this app and `bench build --app bond_management` remains the production build entry point.

### Build and dependency rules

- The root package delegates application development and production builds to `frontend/`, following the app-owned frontend pattern used by ERPNext.
- Pin Frappe UI and Playwright to exact versions proven against Frappe v16, Python 3.14 and Node 24. Upgrade them through an explicit compatibility change.
- Prefer the official `frappe-ui/vite` plugin for proxying, boot data, asset paths and the generated website entry when its tested release supports the app baseline.
- Treat the generated HTML and assets as build output. Source changes belong in `frontend/`.
- Define TypeScript view models for investor API responses. Generated DocType types may assist implementation but do not become the public client contract.

## Route, session and rollout

### Pilot behaviour

1. `bond_investor_spa_enabled` is false by default.
2. A disabled site sends `/bond-investor` back to `/desk/bond-investor` without exposing SPA APIs.
3. An enabled site serves the SPA only to an authenticated investor, manager or Administrator.
4. The current investor login redirect and Apps screen route stay `/desk/bond-investor` during pilot.
5. Pilot users receive the direct `/bond-investor` link. The old workspace remains their fallback.

### Cutover behaviour

After pilot acceptance, change the investor login redirect and Apps screen route to `/bond-investor`. Keep `/desk/bond-investor` available for rollback until the separate retirement phase completes.

### Boot context

The website context exposes only the minimum shell data:

- CSRF token required by Frappe UI request handling.
- Current user identity and display name.
- Whether the user is an investor or support user.
- The enabled feature state.

Portfolio assignments and financial data come from authenticated APIs, not from trusted client boot state. Development uses the same-origin Vite proxy and a real CSRF/session path; `ignore_csrf` is not part of the setup.

## Investor API contract

Place cross-document investor queries in `bond_management.bond_management.api.investor`. Every endpoint must:

- use `@frappe.whitelist(methods=["GET"])` without guest access;
- verify the feature flag and allowed role;
- derive the current user from `frappe.session.user`;
- enforce existing portfolio query and document permissions;
- allow-list filters, sort fields, page size and returned fields;
- use existing financial/report services rather than duplicating calculations;
- expose permission-scoped statement and transaction file URLs only from document detail views;
- return deterministic, serializable view models with boundary tests.

Initial endpoint seams:

| Endpoint responsibility | Contract                                                                             |
| ----------------------- | ------------------------------------------------------------------------------------ |
| Bootstrap               | Allowed portfolio choices and non-financial shell options for the current user.      |
| Transactions            | Paginated list and one read-only detail, scoped to an allowed portfolio.             |
| Statements              | Paginated list and read-only detail with document-only PDF and report downloads.     |
| Bond reference data     | Bond Master, Market Date and Exchange Rate list/detail projections needed by the UI. |
| Portfolio performance   | Existing report output projected into a stable table/chart view model.               |
| Yield comparison        | Existing report output projected into a stable comparison view model.                |

Endpoints may be split into an `api/investor/` package when the first file would otherwise mix unrelated screen contracts. Keep the public methods shallow and move reusable query or projection logic into focused internal services.

### Permission acceptance matrix

Server tests must prove:

| Caller                                                   | Expected result                                        |
| -------------------------------------------------------- | ------------------------------------------------------ |
| Guest                                                    | Authentication failure.                                |
| Authenticated user without an allowed role               | Permission failure.                                    |
| Investor with no portfolio assignment                    | Successful empty bootstrap; no records or report data. |
| Investor with one assigned portfolio                     | Only that portfolio and its permitted records.         |
| Investor requesting another portfolio or record directly | Permission failure without existence leakage.          |
| Manager or Administrator                                 | Data allowed by their existing normal permissions.     |

The tests must also prove that arbitrary filter fields, unsupported sort keys,
excessive page sizes and unapproved file metadata cannot cross the API
boundary. Visible-column sorting and exact clicked-value filters are allowed
only through each endpoint's fixed field allowlist and remain subject to the
same normal Frappe permissions.

## UI behaviour

### Shell

- Persistent navigation for the eight included surfaces.
- Portfolio selector where the screen requires one, populated only from the bootstrap API.
- Loading, empty, failed and retry states for every network-backed view.
- Session-expiry handling that returns the user to login and preserves the intended SPA route.
- Visible read-only presentation: no disabled mutation controls that imply unsupported operations.
- Responsive layouts verified on desktop Chromium and a Pixel 7-sized viewport.
- Breadcrumbs use one compact, non-wrapping line with an accessible home icon,
  slash separators and the current hierarchy, such as
  `Home / Bond Investor / Bond Transactions`, and ellipsize long context labels.
- Normal list and report screens omit connection and assigned-portfolio status
  summaries; the authenticated account remains available in the shell header.
- The Desk-style breadcrumb is the single screen title for list and report
  routes, using the current hierarchy without a duplicate title row; detail
  surfaces retain their record identifier as the content heading.

### Desk-style list controls

- Record-list headers expose every visible column as an accessible sort control;
  clicking a title requests that column from the server and toggles ascending
  or descending order with a deterministic name tie-breaker.
- Visible cell values expose exact filters where the surface supports them.
  Date cells intentionally do not expose filter actions. The API accepts only
  endpoint-specific non-date visible-field keys and one exact clicked-value
  filter alongside the existing assignment/status filters; it does not expose
  an unrestricted arbitrary-field filter builder.
- Lists with a business date default to descending date order (latest first),
  with a deterministic name tie-breaker.
- List footers follow Desk's compact list treatment: they show the number of
  records currently loaded, allow the supported page sizes and load the next
  server page without client-side pagination of financial records.

### Reports

- Preserve the existing report filters, columns, currencies, percentages, dates and chart meaning.
- Bond Yield Comparison defaults From Date to the oldest permission-readable persisted yield date and To Date to the current site date. Its chart uses persisted market dates for horizontal positions, shows one x-axis label per year and renders line series without point markers.
- Preserve server-provided precision and financial conventions.
- Assert visible table labels, values and series names. Avoid tests tied to SVG geometry or internal chart-library objects.
- Keep clipboard/export actions out of scope unless they are confirmed as investor-visible parity before the report phase starts.

## Test ownership

| Risk                                              | Primary owner                                                | Browser coverage                                          |
| ------------------------------------------------- | ------------------------------------------------------------ | --------------------------------------------------------- |
| Financial calculations and report values          | Existing and new server tests                                | One representative visible value per report flow.         |
| Investor portfolio isolation and role permissions | Server integration tests                                     | One allowed-data smoke flow; denial remains server-owned. |
| SPA routing, loading and recovery                 | Playwright                                                   | Required on desktop and mobile.                           |
| Internal Desk form scripts and attachment parsing | Existing Cypress and server tests                            | Cypress remains unchanged.                                |
| Legacy investor Desk navigation                   | Existing workspace/server tests and Cypress where applicable | Retained until retirement.                                |

Current Cypress specs exercise Desk internals and internal mutations, including `cur_frm`, form triggers, PDF parsing and query-report objects. They are not replaced by investor Playwright tests. A Cypress spec is removed only when the Desk behaviour it owns is itself retired.

### Playwright baseline

- Root `playwright.config.ts` with an authentication setup project and ignored storage state.
- Chromium desktop and Pixel 7 mobile projects.
- One worker initially for deterministic Frappe fixtures; add sharding only when runtime justifies it.
- CI retries of two, trace on first retry, screenshot on failure and retained video on failure.
- Real `test_site`, real investor permissions and real investor APIs. Mocking is limited to third-party boundaries that cannot be made deterministic locally.
- Stable role/name locators first; stable `data-testid` values where accessible names are ambiguous.
- Idempotent test-data seeding through a dedicated server helper. Credentials remain in local environment or CI secrets, never repository files.

Frontend unit testing is deferred until non-trivial client logic exists. Financial and permission logic stays server-side; introducing a unit runner without such a seam would add maintenance without coverage value.

## Delivery phases

### Phase 0 — Decision record and baseline

Capture this specification, the progress tracker, current investor surfaces, current Cypress ownership and the verification commands.

Complete when both documents are linted and the progress tracker points to Phase 1 as the next slice.

### Phase 1 — Compatibility and toolchain

Prove the smallest production-shaped stack:

1. Root package delegation and `frontend/` scaffold.
2. Exact dependency pins.
3. Frappe UI Vite production build into app assets and `www` entry.
4. Same-origin session and CSRF request to a read-only ping/bootstrap endpoint.
5. Playwright authentication setup plus one desktop and mobile shell test.
6. A separate Playwright CI job and local verification mode; existing Cypress remains green.

Complete when the scaffold works on `test_site`, `bench build --app bond_management`, a fresh CI-shaped site, Playwright desktop/mobile and the existing full Cypress gate.

### Phase 2 — Coexistence shell

Add the feature-gated `/bond-investor` route, nested-route fallback, role gate, navigation, session-expiry handling and common loading/error states. Keep login and Apps screen redirects unchanged.

Complete when disabled, unauthorized, investor and manager route behaviours have server tests and Playwright coverage.

### Phase 3 — Transaction tracer bullet

Deliver one complete vertical slice: allowed portfolio bootstrap, transaction list, transaction detail, explicit APIs, server permission tests and Playwright desktop/mobile flows. Omit mutation controls.

Complete when an investor can browse only assigned transactions, direct cross-portfolio access is denied server-side, and visible fields match the recorded Desk parity inventory.

### Phase 4 — Remaining read-only records

Add statements, bond master, market dates and exchange rates in small screen-sized slices. Each slice includes its API projection, permission tests, responsive UI and one Playwright smoke flow. Statement detail exposes only its PDF and reconciliation-report URLs.

Complete when every record surface has a closed parity inventory and green server and Playwright tests.

### Phase 5 — Reports

Add Portfolio Performance, then Bond Yield Comparison. Reuse existing server calculations and lock response projections with regression tests before rendering tables and charts.

Complete when filters and representative output match Desk on desktop and mobile without client-side financial recalculation.

### Phase 6 — Parity and hardening

Close the full surface matrix; test loading, empty, error, retry, stale-session and deep-link refresh behaviour; complete accessibility and responsive checks; verify investor responses contain no unapproved file metadata.

Complete when all parity rows are accepted and all local/fresh-site server, Cypress and Playwright gates pass.

### Phase 7 — Pilot

Enable the site flag while retaining old redirects. Give pilot investors the direct link, collect defects and run both UI suites. Complete one full statement/reporting cycle with the pilot group.

Complete with internal-team acceptance, pilot acceptance, no open high-severity defects and a recorded rollback rehearsal.

### Phase 8 — Cutover

Change investor login and Apps screen routes to `/bond-investor`. Keep the old workspace reachable as a rollback path and keep all Desk/Cypress coverage.

Complete after production verification and an agreed observation period with no rollback condition triggered.

### Phase 9 — Legacy investor workspace retirement

In a separate release, remove the investor workspace/sidebar and obsolete redirect code only after confirming no supported investor path depends on them. Internal Desk forms, reports and their Cypress coverage remain until a later internal-UI migration retires those behaviours.

Complete when migration tests, route tests, fresh installation, full server suite, Cypress and Playwright all pass and rollback no longer requires the old workspace.

## Verification gates

Every implementation slice records the evidence required by `AGENTS.md`. At minimum:

- targeted server tests for changed permissions, API projections or report adapters;
- the complete affected server module and full server suite for shared backend changes;
- frontend lint/typecheck/build for frontend changes;
- the focused Playwright spec, followed by the complete Playwright suite;
- focused Cypress, followed by the complete Cypress suite, when Desk or shared runtime behaviour changes;
- `apps/bond_management/scripts/verify.sh pre-push`;
- `apps/bond_management/scripts/verify.sh pre-push-ui` for UI, metadata, hooks or shared runtime changes;
- fresh-site verification for dependencies, hooks, installation, build or CI changes.

Phase 1 must extend the shared verification script so `pre-push-ui` means all active UI suites while allowing CI to run Cypress and Playwright in separate jobs without repeating the full server suite.

## Rollback

- Pilot rollback: disable `bond_investor_spa_enabled`; users continue on the unchanged Desk route.
- Cutover rollback: restore login and Apps screen routes to `/desk/bond-investor`; the workspace remains installed.
- API rollback: explicit endpoints are additive until retirement and do not change existing DocType or report contracts.
- Data rollback: no migration phase changes investor financial data, so rollback requires no data transformation.

## References

- [Frappe UI Vite plugins](https://github.com/frappe/frappe-ui/blob/main/vite/README.md)
- [Frappe Wiki frontend](https://github.com/frappe/wiki/tree/develop/frontend)
- [Frappe Wiki Playwright workflow](https://github.com/frappe/wiki/blob/develop/.github/workflows/ui-tests.yml)
- [ERPNext v16 app-owned frontend package](https://github.com/frappe/erpnext/blob/version-16/package.json)
- [ERPNext v16 banking package](https://github.com/frappe/erpnext/blob/version-16/banking/package.json)
- [ERPNext Cypress UI tests](https://github.com/frappe/erpnext_ui_tests)
- [Playwright documentation](https://playwright.dev/docs/intro)
