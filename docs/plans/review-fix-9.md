# Currency changes invalidate pending schedule previews

Changing a ready Bond Master from KES to USD could leave a pending KES
schedule preview active. Its later response restored `quantity_change` and
the old schedules after the currency change.

Currency and day-count changes now invalidate pending previews before awaiting
the quantity setter, then request schedules from the current document when it
is ready. The value-only schedule API, read-only quantity field, and
server-side save validation remain the authority for financial rules.

The focused Desk regression holds the KES response, applies a newer USD
response, and releases the KES response last. It checks that quantity and
schedule fields retain the newer response. The existing incomplete-form
derivation test remains applicable.

Risk classification: client-only schedule preview race. Required verification:
lint, focused `e2e/desk/bond-master.spec.ts`, and the shared `pre-push-ui` gate.
The coordinator ran `apps/bond_management/scripts/verify.sh pre-push-ui`
against the integrated tree: exit 0, 323 server tests and all 50 browser tests,
including all four tests in `e2e/desk/bond-master.spec.ts`. Frontend lint,
typecheck, build, pre-commit and Semgrep also passed. Local evidence is
`fix9-gate.log`.

Tests failed: none. Tests not run: fresh installation is not applicable because
this change adds no schema, patch or hook. Blockers: none in local verification.
Unverified local/CI differences: macOS local runtime versus Linux CI; both use
the shared gate.

The domain model graph and notes were reviewed. No mapped relationship or
data-flow change is introduced; the existing schedule preview API is reused.
