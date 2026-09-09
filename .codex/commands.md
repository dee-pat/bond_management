# Bond Management commands

Run these commands from the bench root. Generic Frappe lifecycle, site
creation, and installation commands live in
`apps/bond_management/.agents/skills/frappe-app-dev/references/bench-operations.md`.

## Interactive development

Use `dev.local` for interactive work; automated test-site rules live in
`apps/bond_management/AGENTS.md`.

```bash
bench --site dev.local migrate
bench --site dev.local backup --with-files
```

## Local service recovery

Start MariaDB when it is unavailable:

```bash
brew services start mariadb
```

Inspect this bench's processes before recovering a broken state:

```bash
pgrep -af "${PWD}/apps/frappe|${PWD}/Procfile"
bench restart
```

## Verification

Before verification or CI/Cypress diagnosis, read
`apps/bond_management/docs/verification.md` for mandatory gates, evidence,
startup diagnostics, and recovery order. The `ui` stage requires an already
prepared test site.

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
