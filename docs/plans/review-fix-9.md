# Currency changes invalidate pending schedule previews

Changing a ready Bond Master from KES to USD could leave a pending KES
schedule preview active. Its later response restored `quantity_change` and
the old schedules after the currency change.

Currency and day-count changes now invalidate pending previews before awaiting
the quantity setter, then request schedules from the current document when it
is ready. The value-only schedule API, read-only quantity field, and
server-side save validation remain the authority for financial rules.

The focused Desk regression holds a KES response, starts a USD currency
change, and suspends the quantity setter after it writes the derived USD
value. It releases KES while the USD handler is waiting, checks that stale
quantity and preview fields remain ignored, then releases the setter and
confirms the USD schedules apply. The incomplete-form derivation test remains.

Risk classification: client-only schedule preview race. Required verification:
lint, focused `e2e/desk/bond-master.spec.ts`, and the shared `pre-push-ui` gate.
The local `apps/bond_management/scripts/verify.sh pre-push-ui` run exited 0:
290 server tests and all 50 browser tests passed, including all four tests in
`e2e/desk/bond-master.spec.ts`. Pre-commit, Semgrep scans and rule tests,
frontend lint, typecheck and build passed. It used the local test site on port
8001 and temporary browser credentials. The local checkout was
`codex/simplify-shared-bond-workflows`; the Bond Master JavaScript and spec
under verification matched this PR's updated files.

Tests failed: One intermediate assertion expected the quantity to retain its
KES value even though the USD setter had already written zero; the assertion was
corrected. Earlier attempts also stopped on local Semgrep trust and browser
setup. The final gate passed. Tests not run: fresh installation is not
applicable because this change adds no schema, patch or hook. Blockers: none.
Unverified local/CI differences: the local macOS checkout noted above differs
from the Linux CI checkout, where the updated PR head will run.

The domain model graph and notes were reviewed. No mapped relationship or
data-flow change is introduced; the existing schedule preview API is reused.
