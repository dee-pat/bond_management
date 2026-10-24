# Share cleanup migration coverage

PR [#104](https://github.com/dee-pat/bond_management/pull/104), review F2.

Before F2, the lifecycle contained no legacy shares, and the direct-call test
ran older cleanup wrappers alongside the new patch. Neither proved cleanup
on an existing site where those older patches are already complete.

Seed synthetic financial-document and attached-File shares plus unrelated
shares in the guarded temporary-site fixture. Keep older cleanup Patch Logs
through the first migration so the new patch alone must remove financial
shares. Verify unrelated grants, File metadata and contents survive, then run
the existing forced full rerun and ordinary migration phases.

Acceptance: disabling the new patch makes the first verification fail;
restoring it passes the lifecycle and applicable lint/server gates. No runtime
or migration implementation changes are intended. Domain-model review found
no mapped relationship or runtime-flow changes.

Status: lifecycle coverage implemented for PR #104. Verification and
publication evidence are tracked in the PR.
