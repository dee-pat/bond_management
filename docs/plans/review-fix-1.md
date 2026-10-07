# Review fix 1: transaction PDF value validation

## Goal and scope

Reject ambiguous bond identity and malformed financial/date values before a
transaction confirmation can populate or validate a Bond Transaction. This
change is confined to text parsing and its regression tests; attachment naming,
permissions, financial conventions, and document persistence stay unchanged.

## Contract and compatibility

The parser extracts the complete value between recognized field labels and
validates the whole token. Repeated conflicting labels, differing ISINs in the
bond name and explicit ISIN field, and malformed explicit ISINs are rejected.
Legacy confirmations may derive their ISIN from the bond name when the explicit
field is absent. A missing Trade Date still falls back to Settlement Date;
a present invalid or blank date is rejected. Missing Principal and Settlement
Amount remain optional; a present invalid or blank value is rejected rather
than disabling controller consistency checks. Blank and N/A commissions retain
the existing zero convention, and a valid commission percentage remains primary
over its valid amount. A malformed secondary commission amount is rejected.

Failures raise TransactionPdfError before financial values are returned. No
migration is required. Correctly formed current, legacy, encrypted, and
positioned PDFs retain the existing input/output contracts.

## Verification and progress

- Risk classification: backend shared parsing utility; financial validation.
- Required gates: targeted parser regressions, complete parser module, and
  `apps/bond_management/scripts/verify.sh pre-push` from the bench root.
- Commands executed: direct invocation of all parser test methods using the
  bench Python with this isolated copy and Frappe on PYTHONPATH; baseline probe
  loading the original parser and invoking the five rejection regression methods.
- Exit statuses: both pure probes exited zero. A standalone `python -m unittest
  bond_management.bond_management.utils.test_transaction_pdf` attempt exited 1
  because Frappe's UnitTestCase class setup requires an initialized local session.
- Tests passed: 22 pure parser test methods, including real generated PDF
  fixtures. All five rejection methods reproduced acceptance bugs in the
  unchanged baseline.
- Tests failed: no parser assertion failures against the implementation in the
  pure probe; standalone unittest failed before running tests.
- Coordinator commands: `bench --site test_site run-tests --app bond_management
  --module bond_management.bond_management.utils.test_transaction_pdf` (exit 0,
  22 tests); `apps/bond_management/scripts/verify.sh pre-push` after Ruff's
  formatting correction (exit 0, 330 server tests). Current full gate includes
  the complete parser module. Evidence: local `fix1-module.log` and
  `fix1-gate-final.log`.
- Coordinator failures: first shared gate exited 1 because Ruff reformatted one
  line; the corrected tree passed the repeated gate.
- Tests not run: browser and fresh-install gates are not applicable.
- Blockers: none.
- Unverified local/CI differences: macOS local runtime; Linux CI will execute
  the same shared gate.

Reviewed docs/domain-model.md: no DocType, field ownership, attachment
relationship, or data-flow edge changes are introduced.
