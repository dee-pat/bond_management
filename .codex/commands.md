# Bond Management commands

Run these from the bench root. Generic Frappe lifecycle and site commands live
in `apps/bond_management/.agents/skills/frappe-app-dev/references/bench-operations.md`.

## Verification

```bash
apps/bond_management/scripts/verify.sh lint
apps/bond_management/scripts/verify.sh server
apps/bond_management/scripts/verify.sh frontend
apps/bond_management/scripts/verify.sh ui
apps/bond_management/scripts/verify.sh playwright
apps/bond_management/scripts/verify.sh pre-push
apps/bond_management/scripts/verify.sh pre-push-ui
```

`ui` expects an already prepared `test_site`; the combined gates prepare the
site as needed. Use `pre-push` for the shared lint/server gate and
`pre-push-ui` when frontend or browser behavior is in scope.

## Focused UI diagnosis

```bash
CYPRESS_SPEC="cypress/integration/portfolio_performance.js" \
    apps/bond_management/scripts/verify.sh ui

apps/bond_management/scripts/cypress-runtime.sh diagnose
apps/bond_management/scripts/cypress-runtime.sh prepare

bench --site test_site serve --port 8001 --noreload
```
