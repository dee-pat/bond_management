# Security review checklist

Bond Management's attack surfaces, with what a reviewer checks on each. Use it
alongside §2 Security of the `frappe-code-review` skill
(`.agents/skills/frappe-code-review/SKILL.md`) whenever a diff touches one of
these surfaces. Findings use the format in [code-review.md](code-review.md).

## Whitelisted methods

Entry points: `api/investor.py`, `api/investor_reports.py`,
`utils/investor_shares.py`, the Bond Transaction, Statement, Master, and Market
Date controllers, and every Script Report under `report/` (Portfolio
Performance, Bond Yield Comparison, and Interest Difference by Portfolio).

- Every argument is type-checked before it reaches a read or a filter, so a
  list or dict cannot become a Frappe filter. Reuse the helpers in
  `api/investor.py` (`optional_string`, `_integer_argument`).
- Investor endpoints return the fixed projection their spec defines, never a
  generic DocType read, and accept only allow-listed filters and sort keys
  (`_list_controls`).
- Desk methods that parse, post, or reconcile check `write` on an existing
  document, or `create` for a new one, before reading the attachment or input.
- No method is `allow_guest`. Adding one needs an explicit reason in the PR.

## Portfolio scope

- A new financial DocType is in `_financial_doctypes` in `hooks.py`. That
  list only wires the investor-mutation rejection and share cleanup; it does
  not scope reads.
- A portfolio-owned DocType is also registered explicitly in both
  `permission_query_conditions` and `has_permission` in `hooks.py`, backed by
  functions in `utils/investor_permissions.py`. A DocType left out of either
  map states why in the PR (for example, shared reference data such as
  Bond Master).
- Exchange rates are shared, but the representative statement link is
  permission level 1 and returned only when the caller can read that statement
  ([PR #19](https://github.com/dee-pat/bond_management/pull/19)).

## Shares and User Permissions

- Investor mutations stay rejected by `utils/investor_shares.py`, wired through
  `extend_doctype_class`, `doc_events`, and the `clear_user_permissions`
  override.
- DocShare and User Permission changes stay consistent under concurrency;
  changes here run the share-race helper described under _Temporary sites_ in
  `docs/verification.md`.

## `ignore_permissions=True`

Allowed only in the cases below. Every use stays narrowly scoped to the records
it governs and carries a comment naming the boundary it relies on or owns.

Request-path services sit behind a caller whose permission was checked first,
and the comment names that check, as `delete_statement_exchange_rates` does:

- Generated reports and derived statement writes.
- System-wide invariant checks, such as the ledger and uniqueness validations
  in `BondTransaction._validate_ledger_group`,
  `BondStatement._validate_unique_attachment`, and
  `BondMarketDate._validate_unique_date`. They must read every row; filtering
  them by the caller's permissions would let hidden rows allow a negative
  ledger or a duplicate record.

Services with no prior permission check to rely on are allowed without one:

- Migrations and install/migrate invariant bootstraps in
  `bond_management/patches/`.
- Permission-boundary and share-maintenance internals, which establish the
  boundary rather than sit behind it. `get_allowed_portfolios` and the
  investor-role lookup in `utils/investor_permissions.py` read Has Role and
  User Permission rows an investor cannot read, and `utils/investor_shares.py`
  locks and repairs DocShare rows to keep shares consistent.

## Attachments

- Financial PDFs stay private and are read through Frappe's File API
  (`utils/private_attachment.py`), never a filesystem path built from input.
- Parsers validate actual content, size (`MAX_PDF_BYTES` in
  `utils/pdf_common.py`), and identity fields, rejecting missing or conflicting
  identity instead of guessing. Extension, MIME type, filename, and
  client-extracted values are untrusted.
- A documented legacy fallback is allowed only when the primary identity
  source is absent, and the primary source wins when both exist. For example,
  `utils/statement_pdf.py` uses the original filename's account hint only for
  legacy statements whose PDF body omits the account number; keep its
  regression coverage when changing it. When neither the body nor the filename
  names an account, the portfolio selected on a new statement may supply it,
  but only for a PDF unlocked with that portfolio's own password. The selection
  is a client value, so an unencrypted accountless PDF is rejected.
- Filenames are standardized only after the document is identified, and stay
  private.

## Secrets

- PDF passwords live in the Bond Portfolio `Password` field and are read with
  `get_decrypted_password`. The credential dataclass keeps `repr=False`.
- A configured password never appears in a log, an exception message, a
  response, a test fixture, or a file. Synthetic passwords in test fixtures
  (for example in `tests/factories.py`) are allowed and required for the
  encrypted and invalid-password parser cases.

## Rendering

- The investor SPA renders through Vue templates; `v-html` and `innerHTML` with
  data are findings.
- Desk scripts that build HTML or SVG strings escape every data value (for
  example `escape_svg` in the Bond Yield Comparison report); only numbers and
  fixed strings are interpolated raw.
- `/bond-investor` (`www/bond_investor.py`) serves only when
  `bond_investor_spa_enabled` is set and the user is signed in, and redirects
  without caching otherwise.

## Automated coverage

`scripts/verify.sh lint` runs Frappe's Semgrep rules plus
`semgrep/bond_management.yml` (no manual transaction boundaries, no `Decimal`
from float literals). A recurring finding above that a pattern can catch belongs
there as a new rule with a test in `semgrep/tests/`. For a PR review,
`scripts/semgrep-pr.sh <base>` lists only the Frappe findings the change
introduces.
