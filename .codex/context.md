# Codex project context

Shared Frappe v16 implementation and quality rules live in the parent bench
`../../AGENTS.md`; bond-management-specific rules live in this app's
`AGENTS.md`. Use this file for local environment context and troubleshooting
notes.

## Environment

- Frappe Framework v16
- Python 3.14
- Node 24
- MariaDB 11.8 or 12.3
- Redis 6 or newer

## Local bench sites

- `dev.local`: interactive development site.
- `test_site`: automated server and UI test site. The repository-wide usage
  and safety rules for this site are defined in `AGENTS.md`.

## Project focus

- Custom Frappe apps only; do not assume ERPNext unless specified.
- Financial domain: bonds, accruals, and schedules.

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

See `.codex/commands.md` for common bench, service, build, and backup commands.

## Repository rules

See `AGENTS.md` for the mandatory Frappe API, architecture, testing, and
JavaScript rules.
