# Bond Management Architecture Spec

## Goal

Make financial-document ingestion, derived persistence, and Desk workflows
portable, retryable, and easy to test without changing bond cash-flow,
rounding, permission, or file-privacy semantics.

This is a follow-up specification. It records work that still needs an
explicit implementation slice; it does not restore or replace deleted review
progress files.

## Current data model

The source-derived DocType relationships and key runtime dependencies are
documented in [docs/domain-model.md](docs/domain-model.md). This is an
implementation map rather than a proposed schema; update it when DocType
metadata or relationship-owning services change.

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
- Exchange rates use one global canonical row per date/from/to currency and a
  separate `Bond Exchange Rate Source` row for each statement provenance. A
  statement may share an equal-valued canonical rate with another statement;
  differing values fail the save atomically. The legacy canonical `statement`
  link remains a deterministic display projection, while source rows own
  replacement and trash cleanup. Manual canonical rows remain as fallback data
  after their last PDF source is removed.
- Most Desk Playwright specs cover client state and serialization with
  focused test doubles. `e2e/desk/bond-statement-server.spec.ts` is the
  server-backed smoke path: it uploads a generated statement PDF through the
  Desk dialog, recovers from a rejected PDF, saves, and checks the canonical
  private attachment and generated reconciliation report.
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

Current slice (2026-10-18): simplify transaction PDF selection in place by
extracting normalization from atomic creation. Preserve string/list inputs,
messages, blank handling, first-reference order and last-portfolio wins; leave
permissions, attachment parsing, locks, creation order and rollback unchanged.
No schema, dependency or API change; the domain model was reviewed. Acceptance:
characterization and existing transaction tests pass, full `pre-push-ui` passes,
and runtime/total line deltas are reported. Verified locally: the expanded
32-test transaction module passes with both original and refactored normalization.
The initial characterization corrected its dict/int error expectations against
Frappe's existing type-validation wrapper; runtime behavior was not changed.
`BASE_URL=http://localhost:8001 apps/bond_management/scripts/verify.sh pre-push-ui`
passed (exit 0): lint/Semgrep, 424 server tests, frontend lint/typecheck, 80 unit
tests, build and 61 Playwright tests. Scoped pre-commit, doc links and diff checks
also passed. No fresh-install/opt-in run applies (no schema, hooks or permission
changes); remote CI evidence is recorded on the PR for the published revision.

Report chart cleanup (2026-10-18): share non-null point projection within Bond
Yield Comparison and reduce the hover fallback to its single-point case.
Preserve gap bridging, singleton rendering, interpolation, axes, selection and
clipboard behavior; no API, permission, schema or dependency change. The domain
model was reviewed and needs no update. Acceptance: compare original/refactored
SVG and hover outputs, preserve browser coverage, pass `pre-push-ui`, and report
runtime and total line deltas. Verified: 209 SVG and 66,880 hover outputs match
the original; `pre-push-ui` exited 0 (lint, 424 server, 80 frontend unit and 61
browser tests, typecheck and build). Scoped lint, doc links and diff checks pass.
Fresh-install/opt-in checks do not apply; remote CI evidence for the published
revision is recorded on [PR #92](https://github.com/dee-pat/bond_management/pull/92).

Synthetic PDF fixture cleanup (2026-10-19): both builders share page/font setup,
stream installation, encryption and serialization. Public signatures and 39
generated PDFs match the originals byte for byte; all existing tests are intact.
`pre-push` passed (exit 0): lint/Semgrep and 424 server tests. Domain model
reviewed; runtime unchanged. Doc/diff checks passed; line deltas in the handoff.

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

### Desk browser coverage (Playwright)

`e2e/desk/bond-statement-server.spec.ts` is the focused server-backed smoke
spec. It covers, for Bond Statement:

1. private PDF attachment;
2. server extraction of portfolio/date or transaction values;
3. save with server-authoritative fields;
4. generated private report/file visibility for the owning record; and
5. failed extraction recovery without losing newer form input.

Keep focused API and clipboard test doubles for deterministic client formatting,
stale-response, and export behavior. Do not duplicate the full financial matrix
in browser tests.

## Acceptance criteria

- No parser or controller reads a private attachment through a raw local path.
- Remote-storage support is either tested through the configured Frappe storage
  adapter or explicitly rejected before any rename/write attempt.
- Same logical request can be retried without duplicate rates, reports, or
  canonical files.
- A concurrent canonicalization cannot publish conflicting metadata or leave a
  partial target.
- Focused server tests, complete server gate, and (for UI changes) complete UI
  gate pass on `bond-management-test.localhost` and CI fresh-site setup.
- The spec's unresolved deployment/storage decisions are approved before the
  next implementation slice starts.

## Rollout and compatibility

Keep existing `File` rows, URLs, DocTypes, and public method signatures
backward-compatible. Use normal schema migration for schema-only changes. Add
an idempotent data patch only when transforming existing data. Validate local
and fresh-site behavior before enabling any remote-storage or async path.
