# Local bench commands

Run these commands from the bench directory. For general bench CLI usage,
app/site creation, and installation, use the `frappe-app-dev` skill's
`references/bench-operations.md` and the relevant setup workflow.

## Interactive development

Use `dev.local` for interactive work; automated test-site rules live in
[AGENTS.md](../AGENTS.md).

```sh
bench --site dev.local migrate
bench --site dev.local backup --with-files
```

## Local service recovery

Start MariaDB when it is unavailable:

```sh
brew services start mariadb
```

Inspect this bench's processes before recovering a broken state:

```sh
pgrep -af "${PWD}/apps/frappe|${PWD}/Procfile"
bench restart
```

## Individual verification stages

Before verification or CI/Cypress diagnosis, read
[verification.md](../docs/verification.md) for mandatory gates, evidence,
startup diagnostics, and recovery order. The `ui` stage requires an already
prepared test site.

```sh
apps/bond_management/scripts/verify.sh lint
apps/bond_management/scripts/verify.sh server
apps/bond_management/scripts/verify.sh ui
```
