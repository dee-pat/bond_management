# Codex project context

The repository-wide implementation and quality rules live in `AGENTS.md`.
Use this file for local environment context and troubleshooting notes.

## Environment

- Frappe Framework v16
- Python 3.14
- Node 24
- MariaDB 11.8 or 12.3
- Redis 6 or newer

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

## Reference commands

See `.codex/commands.md` for common bench, service, build, and backup commands.

## Repository rules

See `AGENTS.md` for the mandatory Frappe API, architecture, testing, and
JavaScript rules.
