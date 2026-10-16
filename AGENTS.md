# Bond Management

Custom Frappe Framework v16 app for bond portfolios, accruals, coupon schedules,
and statement/transaction PDF attachments. ERPNext is not installed. `CLAUDE.md`
is a symlink to this file.

This file covers what the code cannot tell you. Nested `AGENTS.md` files in
`frontend/` and `e2e/` add rules for those areas.

## Before you report done

- Read [verification.md](docs/verification.md) before running gates, diagnosing
  CI or Playwright, or reporting completion. It owns the gates, evidence format,
  site rules, and recovery steps.
- Run the applicable gates before committing or pushing, and wait for required
  CI before reporting completion. A green CI clean install on the exact commit
  satisfies the fresh-install check.
- Keep [domain-model.md](docs/domain-model.md) in sync with any change to a
  DocType, `Link`/`Table` field, child-table ownership, attachment or derived
  data, or a report/API/service data flow. Otherwise record that you reviewed it.
- Skills live in `.agents/skills/`; never install skills globally. Upstream and
  kit skills are pinned in `skills.lock` and vendored unmodified by
  `scripts/sync-skills.sh`; only the `bond-management-*` skills are edited
  here. The same lock vendors Frappe's Semgrep rules into `semgrep/frappe/`.
- The _Shared Frappe rules_ block below is generated from
  [frappe-agent-kit](https://github.com/dee-pat/frappe-agent-kit). Never edit it
  here: change the kit, then bump the pin in `skills.lock` and run
  `scripts/sync-skills.sh sync`.
- This file also wins over pinned skills: judge access-control review findings
  by [security-review.md](docs/security-review.md).

## Layout

- App root is `<bench>/apps/bond_management`. The Python package
  `bond_management/` holds the Frappe module package
  `bond_management/bond_management/`. There is no third nested package. Inspect
  the tree and nearby imports before adding an absolute import.
- Controllers stay thin and own only their DocType. Shared logic lives in
  `bond_management/bond_management/utils/`: accrual, coupon schedules, XIRR and
  performance math; PDF parsing (`statement_pdf.py`, `transaction_pdf.py`)
  behind `private_attachment.py`; statement-derived writes.
- Tests sit beside their code (`utils/test_*.py`, `api/test_*.py`,
  `doctype/*/test_*.py`). Factories: `tests/factories.py`, `tests/pdf_factory.py`.
  Playwright seed: `tests/investor_ui_seed.py`. Rule-to-test index:
  [testing-matrix.md](docs/testing-matrix.md).
- Open work and invariants: `ARCHITECTURE_SPEC.md`, `docs/specs/`, `docs/plans/`.
  Accepted business and architecture decisions:
  [docs/decisions/](docs/decisions/README.md).

## Architecture

- Two surfaces share one Frappe session:
  - **Desk** (`/desk/bond-investor` workspace, form JS, script reports) is where
    every financial mutation, PDF parse, reconciliation and market-data change
    happens.
  - **Investor SPA** (`frontend/`, served at `/bond-investor`) is read-only and
    gated by site config `bond_investor_spa_enabled`. Its only backend is
    `api/investor.py` and `api/investor_reports.py`, which return fixed,
    permission-scoped projections, never generic DocType reads. Before
    changing the SPA, these APIs, investor redirects, the legacy investor
    workspace or Playwright setup, read
    [investor-ui-migration.md](docs/specs/investor-ui-migration.md) and update
    [the progress note](docs/plans/investor-ui-migration-progress.md) for the
    current slice.
- Investor isolation is centralized in `hooks.py`:
  - `permission_query_conditions` and `has_permission`
    (`utils/investor_permissions.py`) scope Portfolio, Transaction, Statement,
    Exchange Rate (and its Source) and File to portfolios assigned through User
    Permission.
  - `utils/investor_shares.py` (via `extend_doctype_class`, `doc_events` and a
    `clear_user_permissions` override) rejects investor mutations and keeps
    DocShare and User Permission consistent.
  - Add every new financial DocType to `_financial_doctypes` in `hooks.py`.
- Statement save synchronously writes derived data: canonical
  `Bond Exchange Rate` rows plus one `Bond Exchange Rate Source` provenance row
  per statement, market prices on `Bond Market Date`, and the reconciliation
  report file. Equal rates may be shared across statements; a conflicting value
  fails the whole save.

## Bond financial conventions

- [docs/decisions/](docs/decisions/README.md) records some of these
  conventions with their reasons and consequences. Read the matching record
  before changing a convention it covers. Changing any convention below,
  recorded or not, needs the user's approval and a new or superseding record.
- Build monetary values, accrued interest, yields and quantities as `Decimal`
  from strings. Keep `Decimal` through calculations and quantize only at the
  business-rule boundary with an explicit rounding mode and documented
  precision. Convert to float only inside a named external-library adapter or a
  JSON/clipboard serialization boundary, with precision regression tests.
- Keep the existing rounding, cash-flow sign, commission and bank-price
  conventions. Changing one needs an explicit business decision and boundary
  tests.
- Normalize financial dates with `frappe.utils.getdate` at system boundaries.
  Issue, coupon, trade, settlement, repayment and maturity rules use calendar
  dates unless a timestamp is explicitly required.
- Coupon schedules run from issue date to maturity under the configured
  day-count convention; keep their period boundaries and coupon-date semantics.
- Principal repayment rows are positive and unique. The latest contractual
  repayment date is maturity, and repayment dates align with coupon dates under
  the current Bond Master rule.
- Amortisation changes outstanding principal or the principal factor, not
  transaction quantity, unless an explicit business rule says so.
- Ledger position is effective on `settlement_date`. Maturity-day and same-day
  coupon/repayment behaviour use explicit pre- and post-payment rules, not
  generic date comparisons.
- Market prices are per 100 of original face value. Never apply the principal
  factor to market-price cash flows a second time.
- Transaction, posting, accrual, reconciliation and attachment mutations are
  server-authoritative. Show pending/failed state until the server confirms; no
  optimistic UI for financial values or durable status.

## Attachments and secrets

- Uploaded financial documents stay private. Read them through Frappe's File
  APIs and storage abstraction, never an assumed filesystem path.
- Validate actual file content and document structure; do not trust extensions,
  MIME types, filenames or client-extracted values. Attachment-managed statement
  fields are server-authoritative; Desk `read_only` is not protection.
- Never return, log, persist in plain text, or put in an exception a configured
  PDF password. Standardize filenames only after identifying the document, and
  keep files private.
- Parsers reject missing or conflicting identity fields instead of guessing. A
  documented legacy fallback applies only when the primary source is absent;
  the primary source wins when both exist.

## App migrations and tests

- Patches live in `bond_management/patches/`, registered in `patches.txt`;
  install and migrate invariants are also wired into `after_install` and
  `after_migrate` in `hooks.py`.
- Renames, removals, retypes, staged constraints and patch retirement: use the
  `frappe-migration` skill together with `bond-management-migration`.
- Tests are deterministic and rerunnable; outcomes never depend on factory
  name suffixes or wall-clock timing. Playwright owns visible SPA and Desk
  wiring; see `e2e/AGENTS.md`.
- Attachment parsers cover current, supported legacy, malformed, conflicting,
  encrypted, wrong-password and non-PDF cases.

<!-- BEGIN synced-rules: dee-pat/frappe-agent-kit/rules/frappe.md@9f1d0fce815615c7b261bb553572c0d1c421c987 -->
## Shared Frappe rules

Frappe v16 rules shared across apps; the app's own rules win on conflict. Use
`frappe-app-dev` for Frappe work, `code-style` when writing code,
`frappe-migration` for patches, indexes, DocPerms and schema changes,
`frappe-code-review` as the review checklist, and `frappe-pr-review` to review a
PR, branch or diff, including your own before opening a PR. Review is read-only
unless the user asks for fixes.
These rules and the app's own rules win over examples and checklists in the
pinned upstream skills, some of which read records with `get_all`/`get_list`.

- The installed framework at `<bench>/apps/frappe` is the authority on Frappe
  behaviour: when correctness depends on a lifecycle, permission, transaction or
  hook detail, search it and read the relevant function rather than relying on
  memory or upstream `develop`.
- Use v16 APIs and supported hooks; never monkey-patch core.
- User-facing multi-record reads use `frappe.qb.get_query` with
  `ignore_permissions=False`. Use `ignore_permissions=True` only in reports,
  migrations, admin invariant checks whose caller's permission is verified
  separately and documented, permission-boundary internals that establish the
  boundary rather than sit behind it (for example, reads of role or
  user-permission rows the caller cannot see), and deterministic test or seed
  setup. Each use names the check or boundary it relies on in a comment, and an
  externally invocable helper still needs an administrative boundary.
- At every whitelisted boundary, check runtime types with `isinstance` before
  any read, existence or permission check; reject lists and dicts where a string
  is expected.
- Permission-query hooks build SQL only from fixed identifiers and values
  escaped with Frappe's database API.
- No `frappe.db.commit()` or `rollback()` in controllers, hooks, request
  handlers or shared services.
- Normalize dates with `frappe.utils.getdate`; never compare date strings with
  date objects.
- Async form handlers return their Promise and carry a per-form request token so
  a stale response cannot overwrite newer state.
- When a backend field or permission reaches the UI, update the client and one
  browser assertion in the same change; server tests own the full matrix.
- Background jobs and patches are idempotent and safe to rerun.
- For `>`, `>=`, `<`, `<=` rules, test greater, less and equal.
- A gate passes only when run on the current change with an observed zero exit
  status. Report an unavailable gate as a blocker, and never weaken an assertion
  to make CI pass.
<!-- END synced-rules: dee-pat/frappe-agent-kit/rules/frappe.md -->

## Sites

- `bond-management-dev.localhost` is for interactive work and
  `bond-management-test.localhost` for automated tests. Both are exclusive to
  this app. Reuse the test site for routine gates; never recreate, drop or
  restore either without approval.
- Temporary sites and credentials: follow
  [verification.md](docs/verification.md#sites-and-credentials).

## Commands

Run gates from the bench root (`../..`). `TEST_SITE` overrides the default
test site.

```bash
apps/bond_management/scripts/verify.sh lint         # pre-commit + skills.lock check + Semgrep + rule tests
apps/bond_management/scripts/verify.sh server       # migrate test site + full server suite
apps/bond_management/scripts/verify.sh frontend     # yarn lint + typecheck + bench build
apps/bond_management/scripts/verify.sh ui           # seed fixtures + full Playwright suite
apps/bond_management/scripts/verify.sh pre-push     # lint + server
apps/bond_management/scripts/verify.sh pre-push-ui  # lint + server + frontend + ui
bench --site bond-management-test.localhost run-tests --module bond_management.bond_management.utils.test_accrual [--test <method>]
bench --site bond-management-test.localhost run-tests --doctype "Bond Transaction"
```

## Review guidelines

- Before reviewing a PR, commit, or uncommitted diff, read the
  [review output contract](docs/code-review.md#review-output-contract). Include
  a merge-readiness score from **0/5 to 5/5**, revision and verification
  evidence, 5-hour usage when measurable, and one ready-to-copy fix prompt,
  usable in Codex and Claude Code alike, populated with the actionable
  findings. For GitHub PR reviews, publish the summary on the PR when posting
  is authorized; a chat-only summary is insufficient. Follow the contract's
  companion-comment procedure when the native review restricts the output
  format.
- Review changed APIs, controllers, metadata, hooks, reports and Desk/SPA
  projections together against the rules above.
- For a diff touching an entry point, permission scope, shares, attachments,
  secrets, or rendered HTML, apply [docs/security-review.md](docs/security-review.md).
- Check [domain-model.md](docs/domain-model.md) relationships and the evidence
  that [verification.md](docs/verification.md) requires.
- Follow the `frappe-pr-review` skill for the review procedure; the output
  contract in [code-review.md](docs/code-review.md) wins on conflict.
- Process and GitHub thread handling: [code-review.md](docs/code-review.md).
