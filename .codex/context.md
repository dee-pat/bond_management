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

## Active multi-phase work

- Investor UI migration: before changing the Frappe UI SPA, Playwright setup,
  investor APIs, investor redirects, or legacy investor workspace, read
  `docs/specs/investor-ui-migration.md` and update
  `docs/plans/investor-ui-migration-progress.md` for the current slice.

## Troubleshooting checklist

- MySQLdb connection errors: check the MariaDB service and credentials.
- Redis connection failures: confirm Redis is running and its configured
  connection details are correct.
- `DocType not found`: verify the app is installed on the site, then run the
  applicable migration.
- JavaScript field updates: check form triggers and `frm.refresh_field`.
- Bench build failures: check the Node and Yarn versions.
- For Cypress startup/login failures or CI bootstrap issues, read
  [verification.md](../docs/verification.md) for runtime diagnostics, recovery,
  and the required rerun sequence.

## Reference commands

See [commands.md](commands.md) for local development, service recovery, and
individual verification commands.
