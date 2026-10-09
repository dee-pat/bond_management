# Review fix 8: transaction confirmation filename collisions

Different confirmation PDFs for one product account and settlement date currently
compete for one private filename. New canonical names append the SHA-256 of the
uploaded PDF bytes, read through Frappe's private File API after confirmation
parsing. Long account numbers use a bounded readable filename component, with the
full account number included in the digest so truncation cannot merge accounts.
Identical bytes share one canonical URL, including multiple transaction rows from
the same PDF. A legacy account/date URL is reused only when it is already the
persisted attachment of that transaction. No new data migration will rename
historical canonical files.

File read/write permissions, private storage, locking, and rollback behavior stay
in the existing standardization service. A different file cannot overwrite an
existing canonical target. Server regressions will save two distinct valid PDFs
for the same account/date, verify their bytes/privacy, retain multi-row sharing,
and verify legacy URL reuse.

Required verification: targeted regressions, the Bond Transaction module, and
`scripts/verify.sh pre-push` (lint, migration, full server suite). No DocType,
Desk behavior, or installation hook changes require an additional UI/fresh-site
gate. The domain graph was reviewed: attachment ownership and derived-data flows
are unchanged, so no graph update is needed.

Implementation integrated and verified on the canonical test site. Preparation
checks below are retained separately from coordinator evidence.

## Preparation evidence

- Risk classification: backend attachment naming and persistence.
- Required gates: targeted regressions, complete Bond Transaction module,
  `apps/bond_management/scripts/verify.sh pre-push` from the bench.
- Commands executed: cached `ruff check` and `ruff format --check` for both
  changed Python files; bench-environment Python deterministic filename probe.
- Exit statuses: final lint 0, final format check 0, filename probe 0.
  The first Ruff invocation used an unavailable `env/bin/ruff` and exited 127;
  cached pre-commit Ruff was used subsequently. Initial format check exited 1,
  files were formatted, and the current-file format check passed.
- Tests passed: deterministic filename identity/legacy-format probe only.
- Tests failed: none executed against a site.
- Tests not run: both added integration regressions; existing multi-row sharing;
  complete Bond Transaction module; full server suite/shared pre-push gate.
- Blockers: the isolated implementation copy is not attached to a bench/site;
  coordinating agent must integrate before running site gates.
- Unverified local/CI differences: no site or CI execution in this slice.

Targeted commands after integration:

```sh
bench --site test_site run-tests --module bond_management.bond_management.doctype.bond_transaction.test_bond_transaction --test test_distinct_same_day_confirmation_pdfs_keep_separate_private_content
bench --site test_site run-tests --module bond_management.bond_management.doctype.bond_transaction.test_bond_transaction --test test_saving_legacy_canonical_pdf_reuses_existing_url
bench --site test_site run-tests --module bond_management.bond_management.doctype.bond_transaction.test_bond_transaction --test test_multi_transaction_pdf_creates_selected_documents_with_same_attachment
bench --site test_site run-tests --module bond_management.bond_management.doctype.bond_transaction.test_bond_transaction
apps/bond_management/scripts/verify.sh pre-push
```

## Coordinator evidence

- Risk classification: backend attachment naming and persistence.
- Required gates: complete transaction module with targeted regressions; shared
  pre-push gate.
- Commands executed: focused runs for
  `test_long_account_confirmation_filename_fits_file_limit_without_account_collisions`
  and `test_new_transaction_does_not_reuse_an_existing_legacy_attachment_url`;
  `bench --site test_site run-tests --module bond_management.bond_management.doctype.bond_transaction.test_bond_transaction`;
  `apps/bond_management/scripts/verify.sh pre-push`.
- Exit statuses: both focused runs, the 35-test transaction module, and the final
  pre-push run exited 0. The first pre-push attempt exited 1 on an unused test
  variable; after correcting it, lint and formatting passed.
- Tests passed: both new regressions; 35 transaction tests; full gate: 38 unit,
  287 integration, and 3 unspecified-category tests (328 total).
- Tests failed: no test failures.
- Tests not run: browser and fresh-install gates are not applicable.
- Blockers: none.
- Unverified local/CI differences: local verification used macOS; CI uses Linux.
  The domain graph was reviewed and attachment ownership/data flow are unchanged.
