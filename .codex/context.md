# Codex project context

Shared bench-wide rules live in `../../AGENTS.md`; bond-management-specific
architecture, invariants, environment, sites, and verification policy live in
`AGENTS.md`. Use this file only for active work and troubleshooting notes.

## Troubleshooting checklist

- MySQLdb connection errors: check the MariaDB service and credentials.
- Redis connection failures: confirm Redis is running and its configured
  connection details are correct.
- `DocType not found`: verify the app is installed on the site, then run the
  applicable migration.
- JavaScript field updates: check form triggers and `frm.refresh_field`.
- Bench build failures: check the Node and Yarn versions.
- Cypress startup failures: run
  `apps/bond_management/scripts/cypress-runtime.sh diagnose`; the UI gate uses
  a bench-local Cypress cache and repairs a missing or stale binary. If a
  macOS Electron process aborts after verification, confirm the installed
  Cypress version supports the host macOS release before replacing test code.

## Reference commands

See `.codex/commands.md` for bond-management verification and runtime
diagnostic commands.
