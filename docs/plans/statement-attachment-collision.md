# Statement attachment filename collisions

## Problem

Statement files are named from product account and statement date. A second,
different PDF for the same account and date collides with the first file. The
standardizer correctly protects existing bytes, but its rejection prevents the
new statement from being saved.

## Change and contract

Keep the account/date name for the first file. When that path already contains
different bytes, save the incoming private PDF under the same name with its full
SHA-256 digest appended. Never overwrite the canonical file. Identical-content
duplicates keep the existing collision and duplicate-attachment protections.
The legacy filename account-number fallback must recognize the digest suffix.

Versioned names must fit Frappe's 140-character `File.file_name` field. When
the full account/date/hash name exceeds that limit, use `PS-<full-account>-<hash>.pdf`.
Keep the full hash when it fits, otherwise retain as many hash characters as
the limit permits (at least 24 for account numbers whose canonical name fits).
The compact name preserves the full account for legacy PDF identity; the
content hash identifies the revision. Existing names remain unchanged.

## Verification

- Regression test saves two different PDFs with the same account and date and
  verifies both file contents remain intact under separate private URLs.
- Filename parsing test verifies a versioned name still yields the account
  number for supported legacy statements.
- Cover account lengths below, at, and above the full-hash filename boundary,
  plus the longest account whose canonical filename fits; save and reparse
  long-account legacy revisions through real File records.
- Pass preview method names as explicit `page.evaluate` arguments in both
  Desk PDF smoke tests, since browser callbacks do not inherit module scope.
- Run the app server verification gate and review `docs/domain-model.md` for
  relationship changes; this fix changes attachment naming only.

## Completion evidence (2026-10-11)

- Risk classification: backend attachment naming and legacy identity parsing,
  with Desk browser-test wiring corrections.
- Required gates: affected server modules, full `pre-push-ui`, and fresh install
  for the uncommitted hook change.
- Commands executed from the existing bench:
  - `bench --site bond-management-test.localhost migrate`.
  - `bench --site bond-management-test.localhost run-tests --app bond_management --module bond_management.bond_management.utils.test_statement_pdf`.
  - `bench --site bond-management-test.localhost run-tests --app bond_management --module bond_management.bond_management.doctype.bond_statement.test_bond_statement --test test_long_account_statement_revisions_save_and_keep_legacy_filename_identity`.
  - Complete modules `bond_management.bond_management.doctype.bond_statement.test_bond_statement`,
    `bond_management.bond_management.doctype.bond_transaction.test_bond_transaction`,
    and `bond_management.bond_management.utils.test_private_attachment` via the same
    `run-tests --app bond_management --module` command.
  - `BASE_URL=http://localhost:8001 apps/bond_management/scripts/verify.sh pre-push-ui`,
    with browser credentials loaded from the external local configuration.
  - `bench new-site "$REVIEW_TEMP_SITE"` with a generated disposable Administrator
    password, then `set-config allow_tests true`,
    `set-config bond_migration_lifecycle_test true`, `install-app bond_management`,
    and `execute bond_management.bond_management.tests.migration_lifecycle.fresh`,
    each with `--site "$REVIEW_TEMP_SITE"`. Finally,
    `bench drop-site "$REVIEW_TEMP_SITE" --no-backup`.
- Final exit statuses: all commands above exited 0. The temporary site was
  removed from the bench's active sites after logs were captured.
- Tests passed: 19 statement PDF unit tests, the targeted long-account regression,
  37 statement tests, 36 transaction tests, 6 private-attachment tests;
  the full gate passed 417 server tests and 55 authenticated browser tests,
  including both corrected Desk PDF smoke tests. Formatting, lint, Semgrep,
  frontend typecheck, and build passed. Fresh installation verified all 28
  registered patches and the required indexes and permissions.
- Tests failed during diagnosis: Redis was initially stopped, blocking migration
  and integration tests; services were started before rerunning. The first lint
  run applied Python formatting/import fixes. Two preview input-rejection tests
  expected the old document-method exception; they now assert the actual typed
  API `FrappeTypeError` and both pass. No final test failures remain.
- Tests not run: remote CI, since this working tree remains uncommitted/unpushed.
- Blockers: none for local verification.
- Domain-model review: no mapped relationship changes from these two fixes;
  the existing preview API graph remains accurate.
- Unverified local/CI differences: local macOS with MariaDB 12.3 versus CI Linux
  with MariaDB 11.8; the fresh check used the configured local bench.

## Review follow-up (2026-10-11)

- Risk classification: Investor File-list permission scope; an independent review
  found that unrelated and unattached private File metadata remained visible.
- Change: private File queries now include only files attached to an assigned
  Bond Portfolio, Bond Statement, or Bond Transaction, while preserving public,
  owner, and explicit DocShare access. Added an integration regression covering
  assigned, unrelated-DocType, and unattached files.
- Required gate: `pre-push-ui` because the change touches permission hooks,
  Python tests, and Desk JavaScript.
- Command: from the bench, source the external browser credential file and run
  `SSL_CERT_FILE=/etc/ssl/cert.pem XDG_CONFIG_HOME=/tmp/bond-management-semgrep-config SEMGREP_LOG_FILE=/tmp/bond-management-semgrep.log SEMGREP_SETTINGS_FILE=/tmp/bond-management-semgrep-settings.yml SEMGREP_VERSION_CACHE_PATH=/tmp/bond-management-semgrep-version SEMGREP_SEND_METRICS=off SEMGREP_BIN=/Users/deepakpatel/frappe-dev/frappe-bench/env/bin/semgrep BASE_URL=http://localhost:8001 apps/bond_management/scripts/verify.sh pre-push-ui`.
- Exit status: `0`.
- Tests passed: pre-commit hooks; blocking and advisory Frappe Semgrep scans;
  Bond Management Semgrep scan and 2 rule tests; 50 fast tests, 351 integration
  tests, 12 unspecified-category tests, and 55 authenticated Playwright tests;
  frontend lint, typecheck, and production build.
- Tests failed: the first sandboxed run stopped before migration because it
  could not write the bench log; the rerun with access to the configured bench
  passed. The first Semgrep invocation also lacked the host CA bundle; the
  successful command sets `SSL_CERT_FILE` and the isolated Semgrep cache paths.
- Tests not run: remote CI for the PR commit.
- Blockers: none for local verification.
- Domain-model review: no mapped relationship changes; the existing preview
  API graph remains accurate.
- Unverified local/CI differences: local macOS with MariaDB 12.3 versus CI
  Linux with MariaDB 11.8. The registered-patch clean-install check remains for
  CI on the exact PR commit.
