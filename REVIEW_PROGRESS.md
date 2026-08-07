# Codebase Review Progress

## Review scope

Review the bond-management app for maintainability, architecture, correctness,
security, performance, concurrency, API design, testing, and observability.
This is a review-only pass: do not modify production code unless the user
explicitly asks for implementation after findings are reported.

## Review method

- Keep each stage narrow enough to complete in one context window.
- Before each stage, reread this file and inspect only that stage's scope.
- After each stage, record commands, evidence, findings, and the next pending
  stage here before moving on.
- Treat findings as hypotheses until supported by the relevant code and tests.
- Prioritize correctness and security before performance and style.

## Active context handoff

- Current stage: Review complete after Stage 15 — synthesis of findings, risks,
  evidence, and recommended follow-ups.
- Active scope: None. All planned review stages are closed; do not reopen
  earlier stages without an explicitly agreed new review scope.
- Handoff state: Stage 15 is closed and this handoff records that no next stage
  is scheduled. If the review resumes, start a new scoped pass from this file
  and treat the findings index as historical context.

## Implementation follow-up

The review findings are now being implemented in small, explicitly verified
slices. The original Stage 0–15 notes remain historical review evidence.

### Slice 1 — Input, export, and authoritative-response hardening

- Status: Done
- Goal: Close the concrete correctness and security findings F-010, F-011,
  F-015, F-021, and F-024 without changing bond cash-flow or rounding
  conventions.
- Included:
  - Reject non-text transaction references and portfolio names at the
    multi-transaction PDF API boundary, and lock the complete target portfolio
    set in sorted order before creating documents.
  - Reject non-positive transaction quantity, price, principal, and settlement
    values, plus negative accrued interest and commission values, before any
    derived arithmetic. Zero remains valid only for the explicitly
    non-negative accrued-interest and commission fields.
  - Sanitize text cells in spreadsheet clipboard exports for control
    characters and formula-like prefixes while preserving numeric cell
    serialization.
  - Apply a server-normalized Bond Master first coupon date through the Frappe
    form setter and preserve stale-response checks.
- Non-goals: private attachment storage/concurrency redesign (F-013 and
  F-016–F-020), broad client-module decomposition (F-022–F-023), migration
  refactors, and performance optimization.
- Verification: focused parser and transaction tests passed; Bond Master,
  Bond Market Date, and Portfolio Performance Cypress specs passed; the
  complete post-formatting `pre-push-ui` gate passed lint, security scans,
  migration, 26 unit tests, 153 integration tests, 1 workspace test, and all
  6 Cypress tests across 5 specs.
- Remaining scope: fresh-site CI and remote-storage behavior remain outside
  this local slice. The next implementation slice should begin with the
  attachment persistence/storage findings only after their storage and
  concurrency contract is agreed.

## Context reset log

| Boundary | Closed stage | Next active scope | Durable handoff written | Review resumed in same turn |
|---|---|---|---|---|
| B-001 | Stage 9 | Stage 10 transaction PDF parser only | Yes | No |
| B-002 | Stage 10 | Stage 11 private-file/password and naming adapters only | Yes | No |
| B-003 | Stage 11 | Stage 12 background jobs, persistence side effects, and observability | Yes | No |
| B-004 | Stage 12 | Stage 13 Desk client scripts, workspaces, reports, and UI/server contracts | Yes | No |
| B-005 | Stage 13 | Stage 14 tests, fixtures, Cypress coverage, CI, and verification gates | Yes | No |
| B-006 | Stage 14 | Stage 15 synthesis: prioritize findings, risks, evidence, and recommended follow-ups | Yes | No |
| B-007 | Stage 15 | Review complete; no next stage scheduled | Yes | No |

## Plan

| Stage | Scope | Status |
|---|---|---|
| 0 | Establish scope, inventory, and review conventions | Done |
| 1 | Repository structure, package boundaries, and change hygiene | Done |
| 2 | Hooks, installation, after-migrate wiring, and manual indexes | Done |
| 3 | Data patches, permissions, ordering, idempotence, and migration safety | Done |
| 4 | Financial utilities, Decimal conversion, rounding, and numeric boundaries | Done |
| 5 | Accruals, coupon/principal schedules, XIRR, exchange rates, and ledgers | Done |
| 6 | Master, schedule, market-date, and exchange-rate controllers | Done |
| 7 | Transaction/statement controllers, APIs, writes, and validation boundaries | Done |
| 8 | Reports, performance, context loading, and response serialization | Done |
| 9 | Statement PDF parsing and identity extraction | Done |
| 10 | Transaction PDF parsing and identity extraction | Done |
| 11 | Private-file/password and attachment naming/sync adapters | Done |
| 12 | Background jobs, persistence side effects, and observability | Done |
| 13 | Desk client scripts, workspaces, reports, and UI/server contracts | Done |
| 14 | Tests, fixtures, Cypress coverage, CI, and verification gates | Done |
| 15 | Synthesis: prioritize findings, risks, evidence, and recommended follow-ups | Done |

## Stage notes

### Stage 15 — Synthesis: prioritize findings, risks, evidence, and recommended follow-ups

- Status: Done
- Commands: read the active context handoff, the Stage 15 plan scope, and the
  findings index from `REVIEW_PROGRESS.md`; read the requested `code-style` and
  `improve-codebase-architecture` skill instructions; `git diff --check`.
- Evidence: The findings index contains 27 historical findings. The highest
  consequence cluster is the private attachment and derived-persistence path:
  F-013, F-016, F-017, F-018, F-019, and F-020. The next correctness and
  security cluster is the request/export boundary: F-010, F-015, and F-021,
  with F-024 affecting server/client state consistency. Migration and data
  integrity risks are F-002, F-005, F-006, F-007, F-011, and F-027. Structural
  and testability candidates are F-001, F-014, F-022, F-023, F-025, F-026,
  F-003, and F-008. Performance candidates are F-004, F-009, and F-012.
  The index is the sole evidence used in this synthesis; no earlier-stage code
  or test findings were reopened.
- Findings: No new finding ID. The recommended order is:
  1. First, harden private attachment handling and derived persistence
     (F-013, F-016–F-020): preserve private-file semantics through the storage
     abstraction, make canonicalization safe under concurrency, prevent
     reconciliation-file accumulation, and add operational failure/retry
     visibility. This is the highest-risk cluster because it combines privacy,
     data integrity, and recoverability.
  2. Next, close input and export correctness gaps (F-010, F-015, F-021,
     F-024): reject malformed types, enforce numeric meaning before arithmetic,
     neutralize formula-like spreadsheet text, and keep server normalization
     visible to the form state. Add focused regression tests at each seam.
  3. Then, make migration behavior independent of interactive controller
     evolution (F-002, F-005, F-006, F-007, F-011, F-027): identify genuinely
     shared pure behavior, reduce broad document persistence in corrective
     patches, make lock ordering deterministic, and exercise representative
     legacy data with safe reruns. This is a data-integrity priority even when
     the immediate failure probability is uncertain.
  4. After the correctness work, deepen the shallow/high-change modules and
     their test surfaces (F-001, F-014, F-022, F-023, F-025, F-026, F-003,
     F-008). Use the deletion test before introducing a module, adapter, or
     seam; keep the interface smaller than the implementation and preserve
     locality in the tests. F-003 identifies missing architecture vocabulary,
     while F-008 and F-026 are coverage gaps rather than confirmed runtime
     defects.
  5. Measure before optimizing (F-004, F-009, F-012): capture index-bootstrap,
     non-batched ledger/XIRR, and historical-XIRR fallback behavior on
     representative data, then deepen only the measured hot seam.
- Tests: No application tests were run because this stage changed only the
  review artifact and did not modify production, test, metadata, or runtime
  files. `git diff --check` passed with exit status 0.
- Blockers: None for completing the synthesis. The findings remain review
  evidence and recommendations; implementation, new tests, and runtime
  measurements require a separate explicitly scoped change.
- Verification:
  - Risk classification: Documentation-only review synthesis; no runtime
    behavior changed.
  - Required gates: `git diff --check` for the review artifact; no server or UI
    gate is applicable to this non-code stage.
  - Commands executed: `git diff --check`.
  - Exit statuses: `git diff --check` — 0.
  - Tests passed: None applicable; whitespace check passed.
  - Tests failed: None.
  - Tests not run: Server, Cypress, migration, and fresh-site gates; no
    production or executable test files changed.
  - Unverified local/CI differences: None introduced by this documentation-only
    stage; historical findings still require their own implementation-time
    verification.

### Stage 0 — Establish scope, inventory, and review conventions

- Status: Done
- Commands: `git status --short`; `rg --files -g '!node_modules' -g '!.cache'`; read
  `.codex/context.md`, `.codex/commands.md`, `AGENTS.md`, `../../AGENTS.md`,
  `code-style/SKILL.md`, `quality-code-review/SKILL.md`, and
  `improve-codebase-architecture/SKILL.md`.
- Evidence: The app is a Frappe v16 custom app with DocTypes, utilities,
  patches, reports, Desk scripts, Cypress tests, and shared verification
  scripts. The worktree already has untracked `.agents/skills/` content; it
  predates this review and is preserved. The architecture skill's referenced
  `codebase-design` skill and `CONTEXT.md`/ADR files are not present in the
  visible repository.
- Findings: No code finding yet. Review artifacts are intentionally separate
  from production code.
- Follow-up: Inspect repository structure and package boundaries only.

### Stage 1 — Repository structure, package boundaries, and change hygiene

- Status: Done
- Commands: `git log --oneline -20`; file inventory and line-count scan;
  import scan; inspection of `pyproject.toml`, `README.md`, `hooks.py`,
  `modules.txt`, and representative patches; `git status --short`.
- Evidence: The package layout is consistent with the app guidance: outer
  `bond_management/` plus the Frappe module package
  `bond_management/bond_management/`. Recent history concentrates on
  statements, reporting, currency, and migrations. Large files include
  `bond_transaction.py` (561 lines), `statement_pdf.py` (581),
  `transaction_pdf.py` (488), `portfolio_performance.py` (508), `xirr.py`
  (397), and `bond_market_date.js` (546). The patch
  `backfill_transaction_principal_values.py` imports a calculation from the
  Bond Transaction controller; several other patches import runtime utility
  modules and other patches.
- Findings:
  - F-001, maintainability candidate: several high-change modules are shallow
    or over-broad candidates under the deletion test; their public interface
    and internal responsibilities should be examined before proposing splits.
  - F-002, architecture candidate: migration modules depend directly on
    runtime controller modules, reducing locality and making the patch seam
    sensitive to controller evolution. Confirm whether the imported function
    is pure and stable before recommending an adapter or deeper module.
  - F-003, process/documentation gap: the architecture skill references
    `CONTEXT.md`, ADRs, and a `codebase-design` vocabulary, but none is present
    in the visible repository. Review terminology will therefore use the
    architecture skill's available vocabulary and record uncertainty.
- Follow-up: Audit hook registration, fresh-install/migrate behavior, patch
  ordering and idempotence, permission ownership, and manual indexes.

### Stage 2 — Hooks, installation, after-migrate wiring, and manual indexes

- Status: Done
- Commands: reread `REVIEW_PROGRESS.md`; inspected `hooks.py`, `patches.txt`,
  `add_bond_query_indexes.py`, relevant DocType JSON, tests, and Frappe's
  MariaDB/Postgres index helpers; searched all patch side effects.
- Evidence: `after_install` bootstraps indexes and all owned permission rows;
  `after_migrate` reapplies the manual indexes and selected permissions.
  `patches.txt` orders duplicate statement cleanup before the unique attachment
  index. `add_bond_query_indexes.py` checks duplicates before adding indexes,
  and Frappe's database helpers avoid recreating existing definitions. Tests
  invoke the index bootstrap twice and assert both document- and database-level
  uniqueness.
- Findings:
  - F-004, performance candidate: every `after_migrate`/fresh-install index
    bootstrap groups and scans Bond Market Date, Bond Statement, and Bond
    Exchange Rate before DDL. This is safe for correctness but its cost grows
    with table size and is not bounded; measure on representative data before
    deciding whether to split validation from invariant installation.
- Follow-up: Inspect every registered data patch and owned permission update
  for safe reruns, complete operation sets, and correct service boundaries.

### Stage 3 — Data patches, permissions, ordering, idempotence, and migration safety

- Status: Done
- Commands: reread `REVIEW_PROGRESS.md`; inspected all 17 registered patch
  modules, `patches.txt`, permission DocPerm upserts, patch-related tests, and
  Frappe migration/index behavior.
- Evidence: Permission bootstrap patches update or create only their own
  `DocPerm` rows and avoid saving parent DocTypes. Duplicate cleanup precedes
  unique-index creation. Tests cover repeated investor/exchange permission
  setup, index setup, selected backfills, attachment standardization, and patch
  ordering. The corrective portfolio patch calls private methods on the Bond
  Transaction controller; reconciliation and corrective patches use full
  document save/insert operations.
- Findings:
  - F-005, architecture candidate: `correct_u0792275_mixed_portfolio.py`
    reaches into private controller methods, so the migration seam has low
    locality and can change when interactive transaction parsing changes.
    Prefer a stable pure module only if the behavior is genuinely shared.
  - F-006, migration-safety candidate: full `save()`/`insert()` calls in
    corrective/backfill patches re-enter current controller validation and can
    rewrite more state than the fields named by the patch. Confirm the exact
    controller side effects and add populated-legacy rerun tests before any
    refactor.
  - F-007, coverage gap: several registered patches have no visible direct
    legacy-data test, including the corrective portfolio repair and some
    permission/report/backfill combinations. The migration sequence is not
    fully tested against representative existing data in this repository.
- Follow-up: Review shared financial utilities and schedules, preserving all
  bond rounding, date, cash-flow, and maturity conventions.

### Stage 4 — Financial utilities, Decimal conversion, rounding, and numeric boundaries

- Status: Done
- Commands: reread `REVIEW_PROGRESS.md`; inspected `financial.py`, `validation.py`,
  all internal `float`/`Decimal`/quantization call sites, XIRR adapters, and
  numeric tests.
- Evidence: `to_decimal` constructs from `str`, rejects non-finite values, and
  has an explicit `None`/falsey-to-zero convention. Money and percent quantizers
  use documented half-even precision. Float conversions are confined to the
  named pyxirr adapter, XIRR guess adapter, and JSON/report serialization
  boundaries. Consumer tests cover selected non-finite and rounding behavior.
- Findings:
  - F-008, coverage gap: the shared numeric boundary has no focused test module
    covering malformed values, `None`/empty values, booleans, infinities, NaN,
    float inputs, and both exact half-even ties for money and percent. Because
    this helper is used by financial controllers and reports, direct tests would
    provide stronger leverage than relying only on consumer scenarios.
- Follow-up: Inspect accrual, schedule, XIRR, exchange-rate, and ledger
  composition for date boundaries, factor semantics, query shape, and Decimal
  preservation.

### Stage 5 — Accruals, coupon/principal schedules, XIRR, exchange rates, and ledgers

- Status: Done
- Commands: reread `REVIEW_PROGRESS.md`; inspected accrual, coupon schedule,
  portfolio, exchange-rate, statement exchange-rate, XIRR, performance, and
  related test modules; traced position/cash-flow call sites.
- Evidence: Date comparisons normalize through `getdate`; explicit
  pre-/post-payment flags are used for same-day coupon and repayment behavior;
  Kenya cadence and ICMA stub tests cover key schedule boundaries. Reporting
  filters exchange rates to USD and the statement exchange-rate sync uses
  row locks plus ownership cleanup.
- Findings:
  - F-009, performance candidate: the non-batched XIRR path calls database-backed
    position helpers inside coupon/principal loops, and `fetch_holdings` loops
    over bonds while each `get_position` performs multiple reads. The report's
    batch context avoids much of this, but other callers can still hit an N+1
    shape; measure and consider reusing a loaded ledger context at the seam.
- Follow-up: Audit DocType controller validation, whitelisted methods, writes,
  transaction boundaries, and server-authoritative derived fields.

### Stage 6 — Master, schedule, market-date, and exchange-rate controllers

- Status: Done
- Commands: reread `REVIEW_PROGRESS.md`; inspected master, coupon/principal
  schedule, market-date, market-price, and exchange-rate controllers; enumerated
  whitelisted methods and database writes; reviewed their tests.
- Evidence: Whitelisted methods validate object/list/string/numeric input types,
  check permissions, normalize dates, and return server-recomputed values.
  Bond Market Date and Bond Exchange Rate perform document-level duplicate
  checks while the manual indexes provide the final database guarantee. No
  controller commits, rollbacks, or client-trusted derived-field persistence
  were found in this slice.
- Findings: No additional finding in this stage.
- Follow-up: Inspect transaction and statement controllers, attachment ownership,
  derived fields, concurrency locks, and delete/update behavior.

### Stage 7 — Transaction/statement controllers, APIs, writes, and validation boundaries

- Status: Done
- Commands: reread `REVIEW_PROGRESS.md`; inspected the complete Bond Transaction
  and Bond Statement controllers, DocType metadata, whitelisted methods,
  attachment/derived-field hooks, lock queries, and related tests.
- Evidence: Transaction validation refreshes the authoritative Bond snapshot,
  recalculates monetary fields, locks the parent portfolio and ledger rows, and
  validates the complete position history. Statement fields derived from PDFs
  are overwritten/checked server-side; attachment uniqueness is checked with
  permissions bypassed for the global invariant and backed by a unique index.
  Normal request paths contain no manual commit or rollback.
- Findings:
  - F-010, API validation finding: `create_selected_pdf_transactions` converts
    `transaction_reference` and `portfolio_name` values from selection dicts to
    strings instead of rejecting lists, dictionaries, numbers, or other wrong
    types. This violates the trust-boundary type rule and can turn malformed
    input into an unintended reference or portfolio filter; add explicit string
    validation and a regression test.
  - F-011, concurrency candidate: multi-transaction PDF creation acquires
    portfolio locks one transaction at a time in transaction ordering. If
    overlapping requests select rows across portfolios in different effective
    orders, they can wait on each other; pre-locking the complete sorted
    portfolio set would make the lock seam deterministic.
- Handoff: Prepared the Stage 8 active-context block above; the next pass must
  begin from that block and the Stage 8 scope only.
- Follow-up: Review reports, PDF/file adapters, attachment privacy, background
  work, persistence side effects, performance, and observability.

### Stage 8 — Reports, performance, context loading, and response serialization

- Status: Done
- Commands: read the active handoff only; inspected the portfolio-performance
  report, its batch context loader, report-facing XIRR serialization, and
  query-count/performance tests.
- Evidence: The report loads transactions, bonds, child schedules, latest
  market rows, and exchange rates in bounded batch queries. It preserves
  Decimal values through calculations and converts to floats only for named
  report/clipboard serialization or the external XIRR adapter. A regression
  test asserts the batch query count does not grow per bond.
- Findings:
  - F-012, performance/serialization candidate: when a bond has no cached
    `future_xirr`, report generation can call `get_last_xirr_guess` once per
    bond; response sorting and quantity serialization also use float casts.
    Measure this fallback on large portfolios and keep any conversion at an
    explicit serialization adapter rather than in core arithmetic.
- Handoff: Reset the active context to Stage 9 PDF/file handling before further
  inspection.
- Follow-up: Inspect PDF content validation, private-file access, password
  secrecy, and attachment identity/filename adapters.

### Stage 9 — Statement PDF parsing and identity extraction

- Status: Done
- Commands: read `REVIEW_PROGRESS.md` handoff; inspected
  `bond_management/bond_management/utils/statement_pdf.py` in focused chunks;
  inspected its parser and Bond Statement integration tests; inspected the
  Frappe `File.get_content()` and `get_full_path()` implementation used by the
  direct attachment seam.
- Evidence: The parser enforces a size limit and PDF header, rejects missing
  and conflicting identity fields, separates statement confirmations from
  transaction confirmations, validates Decimal market/rate values, rejects
  ambiguous legacy bond names, supports encrypted PDFs without exposing the
  password in `repr`, and checks private-file ownership and path containment.
  Tests cover current/legacy formats, wrong passwords, malformed/conflicting
  identities, account hints, prices, rates, and private attachments.
- Findings:
  - F-013, storage-abstraction candidate: `_read_private_attachment()` reads
    `Path(file_doc.get_full_path()).read_bytes()` directly instead of using the
    Frappe File content/storage API. The current code has useful privacy,
    permission, containment, and size checks, so this is not presently a
    demonstrated path-traversal defect; it is a low-locality adapter seam that
    can bypass remote/object storage behavior and duplicates storage knowledge.
- Follow-up: Close this stage at the explicit context boundary B-001. The next
  pass is limited to transaction PDF parsing and its direct tests/seams.

### Stage 10 — Transaction PDF parsing and identity extraction

- Status: Done
- Commands: read the active Stage 10 handoff only; inspected
  `bond_management/bond_management/utils/transaction_pdf.py` in focused
  chunks; inspected `utils/test_transaction_pdf.py`; traced the account-number
  helper and direct attachment imports with `rg` and numbered source views.
- Evidence: The parser limits PDF size, verifies the PDF header, rejects
  missing/conflicting accounts and duplicate references with different values,
  supports encrypted and column-ordered confirmations, keeps financial values
  as `Decimal`, and excludes passwords from dataclass representations. The
  attachment resolver checks private files and read permission, resolves a
  unique accessible portfolio, verifies configured passwords, checks Bond
  Master ISINs, and validates the PDF-implied face value where principal is
  present. Tests cover current/legacy formats, encryption, layout fallback,
  blank commissions, malformed identity, and conflicting rows.
- Findings:
  - F-014, architecture/locality candidate: `transaction_pdf.py` imports
    `normalize_account_number` from `statement_pdf.py`; both attachment naming
    modules also depend on the statement parser for this shared identity
    operation. The helper is pure, but its ownership makes transaction and
    attachment seams depend on a statement-format module. A common identity
    utility would improve module locality if the repeated use is confirmed.
  - F-015, correctness/data-integrity finding: `NUMBER_PATTERN` accepts zero
    and negative financial values, while parsing performs no domain validation.
    In `get_transaction_attachment_details`, a zero quantity or price with a
    supplied principal reaches the division at line 229 and can raise a raw
    `decimal.DivisionByZero`; negative/zero commission, price, quantity, or
    principal values also lack a single explicit boundary rule. Add semantic
    bounds and regression cases for zero, negative, and valid equality cases.
- Follow-up: Close this stage at explicit context boundary B-002. The next pass
  is limited to private-file/password and attachment naming/sync adapters.

### Stage 11 — Private-file/password and attachment naming/sync adapters

- Status: Done
- Commands: Read the active handoff and findings index; inspected
  `bond_management/bond_management/utils/private_attachment.py`,
  `statement_attachment.py`, `transaction_attachment.py`, their direct
  statement/transaction integration-test attachment cases, and the Frappe
  `File`/rollback seams they call. Ran
  `bench --site test_site set-config allow_tests true && bench --site test_site migrate && bench --site test_site run-tests --module bond_management.bond_management.doctype.bond_statement.test_bond_statement && bench --site test_site run-tests --module bond_management.bond_management.doctype.bond_transaction.test_bond_transaction`.
- Evidence: `private_attachment.py:21-32` resolves candidate `File` rows with
  normal permissions, selects the current document's row when present, and
  checks `read`/`write` permission before changing it. Lines 58-67 require a
  local private file and constrain resolved source/target paths to the private
  files directory. Lines 69-97 copy a shared source into a new `File` row and
  update an owned row in place. Lines 103-124 handle same-content targets,
  shared copies, source renames, and rollback callbacks. Frappe's `File` seam
  confirms that `is_remote_file` identifies URL-backed files and that
  `get_full_path()` returns a local path for local URLs. The integration tests
  cover parser-backed statement/transaction attachments, canonical names,
  shared transaction PDFs, and idempotent standardization.
- Findings:
  - F-014 is corroborated: both naming adapters import
    `normalize_account_number` from `statement_pdf`, and both duplicate the
    safe-account regex and validation message. This leaves the naming seam
    shallow and reduces locality for account/file-name policy changes.
  - F-016, portability candidate: `private_attachment.py` performs
    `Path`/`shutil` operations after calling Frappe's `File.get_full_path()` and
    rejects `is_remote_file`. A remote/private storage deployment has no
    supported standardization path; confirm the deployment invariant before
    deepening this adapter around a storage seam.
  - F-017, concurrency candidate: the `File` query, target existence/content
    check, filesystem copy/rename, and `File` save/insert are not coordinated
    by a row or target lock. Concurrent standardization can race on the same
    canonical path, and rollback/after-commit callbacks have no ownership
    token to distinguish another operation's file.
  - F-018, contract/coverage candidate: the shared function checks privacy,
    locality, and path safety but does not inspect PDF bytes or structure. Its
    PDF contract is supplied by upstream parser callers; direct adapter tests
    do not cover malformed, non-PDF, remote, public, conflicting-target, or
    rollback cases.
- Tests passed: 30 statement integration tests and 27 transaction integration
  tests; all passed.
- Tests failed: None.
- Tests not run: The UI gate and deterministic concurrent/rollback adapter
  cases were not run during this review slice. The complete server gate ran
  separately below.
- Blockers: The first sandboxed Bench attempt exited 1 because Bench could
  not write its normal log at `frappe-bench/logs/bench.log`; the same command
  was rerun with the required escalation and exited 0. No review blocker
  remains. Remote-storage behavior remains unverified because the local test
  site uses local private files.
- Follow-up: Inspect registered background jobs, deferred persistence side
  effects, and observability only in Stage 12.

### Stage 12 — Background jobs, persistence side effects, and observability

- Status: Done.
- Scope completed: inspected registered scheduler/enqueue surfaces, deferred
  persistence callbacks, statement-derived persistence side effects, direct
  tests, and application logging/observability references. Attachment parsing
  and adapter behavior from Stage 11 was not reopened.
- Evidence: `hooks.py:175-191` contains only the commented Frappe scheduler
  template; repository-wide scoped search found no active `enqueue`, worker,
  scheduler, or application logging hook. `BondStatement.on_update`
  (`bond_statement.py:117-130`) synchronously updates statement-owned exchange
  rates, creates a private reconciliation `File`, persists its URL with
  `db_set`, and emits only an interactive mismatch message. The report helper
  (`statement_quantity_report.py:16-69`) generates a fresh timestamp/hash name
  when no fixed filename is supplied and does not remove the prior report.
- Architecture assessment: the statement persistence module has a shallow save
  interface over several side effects. A future deepening should create a
  focused side-effect seam with idempotent report replacement and explicit
  failure/observability behavior, preserving locality for the document
  lifecycle and improving the test surface.
- Findings:
  - F-019: Unchanged statement saves create a new private reconciliation report
    `File` without retiring the previous attached file. The existing
    `test_reports_quantity_mismatch_on_insert_and_unchanged_update` asserts a
    different report URL after an unchanged save, while the production path
    has no cleanup or replacement step. This can accumulate private files and
    leave multiple files attached to the same field.
  - F-020: Statement-derived persistence has no operational observability or
    retry seam. Exchange-rate synchronization, private report generation, and
    the URL write all run synchronously from `on_update`; failures surface only
    as request errors, with no structured log, durable status, or retry signal.
- Commands executed and exit statuses:
  - `bench --site test_site migrate` — initial sandbox attempt 1 (blocked by
    Bench log permissions); escalated retry 0.
  - `bench --site test_site set-config allow_tests true` — 0.
  - `bench --site test_site run-tests --app bond_management --module
    bond_management.bond_management.doctype.bond_statement.test_bond_statement`
    — 0; 30 tests passed.
  - `apps/bond_management/scripts/verify.sh pre-push` — 0; lint, formatting,
    security scans, migration, and full server suite passed.
  - `git diff --check` — 0; no whitespace errors.
  - `awk '/[[:blank:]]$/ {print NR ": trailing whitespace"; found=1} END
    {exit found}' REVIEW_PROGRESS.md` — 0; no trailing whitespace.
- Tests passed: 30 focused Bond Statement integration tests; shared gate
  counts of 24 unit, 152 integration, and 1 unspecified test.
- Tests failed: none.
- Tests not run: UI/Cypress suite; no Desk, metadata, or client code changed.
- Blockers: none.
- Unverified local/CI differences: CI was not run; the server gate ran locally
  against the existing `test_site` on the local macOS/Python 3.14 environment.

### Stage 13 — Desk client scripts, workspaces, reports, and UI/server contracts

- Status: Done
- Commands: `rg --files bond_management | rg '(^|/)(.*\\.js|.*\\.json|.*\\.html)$|report|workspace'`; `wc -l` on the scoped files; `rg -n` for client handlers, RPC calls, and named server methods; targeted `sed -n` inspection of all scoped client scripts, workspace/report metadata, and the exact server methods called by the client; `git status --short`.
- Evidence: Workspace and report role metadata is consistent across the visible Desk artifacts. Client/server response shapes align for schedule recalculation, market calculations, statement preview, transaction preview/selection, amount calculation, and report cash-flow copying. Stale-response request IDs are used in the asynchronous schedule, market, statement, and transaction flows. `bond_market_date.js` is 546 lines and combines market recalculation, cash-flow clipboard export, and an SVG yield-curve renderer. `bond_transaction.js` is 372 lines and combines PDF attachment parsing/selection, attachment field state, amount calculation, and accrued-interest defaulting. The portfolio and market-date clipboard adapters interpolate server-returned text directly into TSV. Bond Master applies a server-normalized `first_coupon_date` with direct `frm.doc` mutation rather than the form setter used for other returned values.
- Findings:
  - F-021, security/interoperability finding: `portfolio_performance.js` and `bond_market_date.js` build spreadsheet clipboard TSV by interpolating server-returned text fields without neutralizing tabs, newlines, or formula-like prefixes. A user-controlled ISIN or currency can corrupt columns or be interpreted as a spreadsheet formula when pasted into Excel. Keep financial Decimal serialization at the external clipboard adapter, and add a text-sanitization contract and negative cases before changing the UI.
  - F-022, architecture candidate: `bond_market_date.js` is a shallow, over-broad module whose interface spans three distinct concerns—server recalculation, cash-flow export, and SVG chart rendering—while event handlers directly coordinate each concern. The deletion test says removing the chart renderer would leave a coherent market-data module, so a chart module and a clipboard adapter could deepen the seams and improve locality. Recommendation: Worth exploring.
  - F-023, architecture candidate: `bond_transaction.js` combines the PDF attachment workflow and selection dialog with live transaction amount calculation and accrued-interest defaulting, using separate server interfaces and state machines. The deletion test says removing the attachment workflow leaves a coherent calculation module. A deepened attachment adapter and calculation module could give future changes more leverage without coupling their UI state. Recommendation: Worth exploring.
  - F-024, UI/server contract finding: `bond_master.js` directly assigns the server-normalized `first_coupon_date` and only refreshes the field, bypassing Frappe's form setter and its dirty/change notifications. This weakens locality at the authoritative-response seam and can show a value that is not tracked as a field change; the next test stage should establish the dirty-state behavior before any refactor.
- Tests: No focused UI tests were run during the review scan; the required
  shared server gate was run after the scan and passed. No production code,
  tests, metadata, or client scripts were modified. Stage 14 owns the broader
  existing server/UI test and CI coverage review.
- Blockers: None for Stage 13. The architecture skill references a separate `codebase-design` vocabulary skill and `CONTEXT.md`/ADR files, which remain absent as already recorded in F-003; this stage used the available architecture vocabulary without reopening that historical finding.
- Follow-up: Review only test modules, fixtures, Cypress specs, CI, and verification gates in Stage 14.

### Stage 14 — Tests, fixtures, Cypress coverage, CI, and verification gates

- Status: Done
- Commands: `rg --files` and line-count inventory for test, fixture, Cypress,
  CI, and verification artifacts; `rg -n` for test classes, fixtures, skips,
  assertions, and test setup; line-numbered inspection of `factories.py`,
  `pdf_factory.py`, all Cypress specs, `cypress.config.js`, both GitHub
  Actions workflows, `scripts/verify.sh`, and `scripts/cypress-runtime.sh`;
  inspection of Frappe's `IntegrationTestCase` rollback behavior; the full
  server command `bench --site test_site set-config allow_tests true && bench
  --site test_site migrate && bench --site test_site run-tests --app
  bond_management`; UI prerequisite and Cypress diagnostic commands; and
  `bash -n apps/bond_management/scripts/verify.sh
  apps/bond_management/scripts/cypress-runtime.sh`.
- Evidence: The app has 24 unit, 152 integration, and 1 unspecified-category
  server test, with focused coverage for financial rules, permissions,
  attachment-driven persistence, and patch behavior. The CI server job
  bootstraps a unique fresh bench and invokes the shared `pre-push` gate; the
  UI job bootstraps a separate fresh site and invokes the shared `ui` gate.
  Cypress dependencies are pinned to 13.17.0 in the runtime script and match
  the CI cache key. The browser specs log in to a live Desk site but replace
  report and whitelisted-method responses with intercepts or stubs, and three
  specs invoke `script_manager.trigger` directly. PDF tests use only generated
  Helvetica text PDFs; no checked-in real or sanitized bank PDF fixture exists.
  Frappe's `IntegrationTestCase` rolls back at class cleanup, while
  `make_market_date` reuses the first parent found for a date and appends a new
  child row, so repeated calls share mutable parent state inside and across
  test classes.
- Findings:
  - F-025, coverage/architecture finding: the Cypress interface is mostly a
    shallow client-hook seam: server responses are replaced in
    `bond_market_date.js`, `portfolio_performance.js`, and the attachment
    specs, while `script_manager.trigger` is called directly. This gives good
    locality for client formatting and state transitions, but no browser test
    proves the real attachment upload, save, report response, or server-method
    seam together. Keep the focused adapter tests and add one real
    server-backed smoke flow for each critical surface. Recommendation: Worth
    exploring.
  - F-026, fixture coverage finding: `make_text_pdf` and
    `make_positioned_text_pdf` exercise parser-shaped text but not the font,
    positioning, encoding, metadata, or layout variation of a real bank
    document. Parser tests can therefore pass while a source-document change
    breaks extraction. Add a small sanitized fixture corpus and retain the
    generated PDFs for focused malformed/password cases.
  - F-027, test-isolation finding: `make_market_date` queries by date only,
    takes an arbitrary existing parent, and appends a child row. Because the
    Frappe integration test transaction is class-scoped, test methods can
    observe and mutate a market-date parent created by another test. This
    weakens deterministic locality and can increase validation/query cost as
    the shared parent accumulates rows. Make the factory's parent ownership
    explicit or create an isolated parent per test; add an order-independent
    regression check.
- Tests passed: the escalated server command passed all 24 unit, 152
  integration, and 1 unspecified-category tests. Cypress runtime diagnostics
  passed and reported Node 24.18.0, Yarn 1.22.22, and Cypress 13.17.0; shell
  syntax checks passed.
- Tests failed: none.
- Tests not run: Cypress specs and the `ui` gate; `test_site:8000` was not
  running and the configured hostname did not resolve. No fresh-site CI run,
  browser run, or real-document fixture run was substituted for that gate.
- Blockers: The UI gate remains outstanding for a future verification pass or
  CI run because the local web server/hostname is unavailable. No production
  code was changed.
- Follow-up: Synthesize F-001 through F-027 in Stage 15 only; do not reopen
  test, fixture, Cypress, CI, or verification files unless synthesis requires
  a direct evidence check.

## Findings index

- F-001: Large/high-change modules are maintainability candidates.
- F-002: Runtime/controller coupling from migration modules.
- F-003: Missing `CONTEXT.md`, ADRs, and referenced `codebase-design` skill.
- F-004: Unbounded duplicate scans during index bootstrap.
- F-005: Migration reaches into private controller methods.
- F-006: Full document persistence inside corrective/backfill patches.
- F-007: Uneven registered-patch legacy-data coverage.
- F-008: Shared numeric boundary lacks focused edge-case coverage.
- F-009: Non-batched ledger/XIRR paths can produce N+1 reads.
- F-010: Multi-transaction selection coerces wrong input types.
- F-011: Per-row portfolio locking may create avoidable deadlocks.
- F-012: Report historical-XIRR fallback and float serialization need measurement.
- F-013: Statement attachment parsing reads a resolved local path instead of
  the Frappe File content/storage abstraction.
- F-014: Transaction and attachment modules import account normalization from
  the statement parser, reducing module locality.
- F-015: Transaction PDF numeric parsing lacks explicit semantic bounds and can
  expose a raw Decimal division error for zero quantity or price.
- F-016: Private attachment standardization is local-filesystem-bound and has
  no remote/private storage seam.
- F-017: Attachment standardization has an uncoordinated filesystem/`File`
  metadata race for concurrent canonicalization.
- F-018: The private PDF naming seam lacks direct content and failure-path
  coverage and relies on upstream parser callers for its PDF contract.
- F-019: Unchanged statement saves create a new private reconciliation report
  `File` without retiring the previous attached file.
- F-020: Statement-derived persistence has no operational observability or
  retry seam; failures surface only through the synchronous save request.
- F-021: Spreadsheet clipboard exports do not neutralize control characters or
  formula-like text fields.
- F-022: Market-date client script combines recalculation, clipboard export, and
  SVG rendering without deep seams.
- F-023: Transaction client script combines attachment workflow and amount
  calculation without deep seams.
- F-024: Bond Master server-normalized first coupon date bypasses form dirty/change
  notifications.
- F-025: Cypress coverage mostly replaces server responses and invokes client
  hooks directly, leaving the real browser/server seam untested.
- F-026: PDF parser fixtures are generated text-only documents with no
  sanitized real-world bank samples.
- F-027: `make_market_date` shares a mutable parent by date across
  class-scoped integration tests.

## Verification

- Risk classification: Review-only documentation change; no production code,
  tests, metadata, dependencies, or CI configuration changed.
- Required gates: Direct attachment integration tests; `git diff --check` for
  the review artifact; and the shared `apps/bond_management/scripts/verify.sh
  pre-push` gate.
- Commands executed: The two module-specific Bench commands recorded in
  Stage 11; `git diff --check`; `awk '/[[:blank:]]$/ {print NR ": trailing whitespace"; found=1} END {exit found}' REVIEW_PROGRESS.md`; and
  `apps/bond_management/scripts/verify.sh pre-push` from the bench directory.
- Exit statuses: The initial sandboxed Bench command exited 1 due its log-file
  permission error; the escalated combined setup/migrate/test command exited
  0. `git diff --check` exited 0. The shared pre-push gate exited 0.
- Tests passed: 57 targeted integration tests (30 statement, 27 transaction),
  plus the shared gate's 24 unit, 152 integration, and 1 unspecified-category
  server test.
- Tests failed: None.
- Tests not run: UI gate; fresh-site validation; concurrency and negative
  adapter cases.
- Blockers: None for this review-only stage. The full server/UI gates are
  represented by the server gate result above; the UI gate was not applicable
  because no UI or production code changed.
- Unverified local/CI differences: The local test site uses local MariaDB,
  local private-file storage, and the local macOS Bench environment; CI
  storage, database, and fresh-site behavior were not exercised.

### Stage 13 verification

- Risk classification: Review-only documentation change; no production code,
  tests, metadata, dependencies, or CI configuration changed.
- Required gates: `git diff --check`; trailing-whitespace check for
  `REVIEW_PROGRESS.md`; and `apps/bond_management/scripts/verify.sh pre-push`
  from the bench directory. The UI gate was not required because no production
  Desk artifact was changed.
- Commands executed: `git diff --check` and
  `awk '/[[:blank:]]$/ {print NR ": trailing whitespace"; found=1} END {exit found}' REVIEW_PROGRESS.md`; `apps/bond_management/scripts/verify.sh pre-push` from the bench directory, first sandboxed and then retried with host execution.
- Exit statuses: Review-artifact checks exited 0. The initial sandboxed
  `pre-push` exited 1 before tests because Semgrep could not create its X509
  trust store and the required binary was unavailable. The identical host
  retry exited 0.
- Tests passed: The successful shared gate passed all pre-commit hooks,
  blocking/advisory/Bond Management Semgrep scans (0 findings), Semgrep rule
  tests (2/2), 24 unit tests, 152 integration tests, and 1 unspecified-category
  workspace test.
- Tests failed: None in the successful gate; the first attempt was an
  environment failure before tests, not a test failure.
- Tests not run: Focused UI/Cypress tests, the UI gate, fresh-site validation,
  and concurrency/negative clipboard cases remain for Stage 14 or follow-up.
- Blockers: None for this review-only stage after the host retry.
- Unverified local/CI differences: The local test site, browser, MariaDB, and
  macOS Bench environment remain different from CI. The successful server gate
  used the existing local `test_site`; CI, fresh-site bootstrap, browser, and
  UI behavior remain unverified.

### Stage 14 verification

- Risk classification: Review-only documentation change; no production code,
  tests, metadata, dependencies, or CI configuration changed.
- Required gates: `git diff --check`; trailing-whitespace check for
  `REVIEW_PROGRESS.md`; `apps/bond_management/scripts/verify.sh pre-push`
  from the bench directory; and the scoped server test command. The UI gate
  was inspected but not run because the local `test_site:8000` endpoint was
  unavailable and no UI artifact changed.
- Commands executed: The initial sandboxed server command exited 1 because
  Bench could not write `logs/bench.log`; the identical command was retried
  with host execution and exited 0. `scripts/cypress-runtime.sh diagnose`
  exited 0; `bash -n` for both verification scripts exited 0. The initial
  sandboxed `apps/bond_management/scripts/verify.sh pre-push` exited 1 because
  Semgrep could not create its CA trust store; the identical host retry exited
  0. `git diff --check` and the review-artifact whitespace check exited 0.
- Exit statuses: Initial sandboxed server attempt 1; escalated server test 0;
  Cypress diagnostics 0; shell syntax 0; initial sandboxed pre-push 1;
  escalated pre-push 0; review-artifact checks 0. The UI gate was not run.
- Tests passed: 24 unit, 152 integration, and 1 unspecified-category server
  test in the scoped server run; the shared pre-push gate passed pre-commit,
  Frappe Semgrep, Bond Management Semgrep, Semgrep rule tests (2/2), and the
  complete server suite.
- Tests failed: None. The two sandboxed command failures were environment
  failures before their respective checks could run.
- Tests not run: Cypress/UI suite, fresh-site validation, and real-document
  fixture coverage.
- Blockers: The UI gate is unverified locally because `test_site:8000` was not
  running/resolvable. This is an environment blocker, not a failing test.
- Unverified local/CI differences: Local verification used macOS, the existing
  `test_site`, local MariaDB, and local private-file storage. CI's Linux fresh
  bench/site bootstrap, browser setup, and UI artifacts remain unverified.
