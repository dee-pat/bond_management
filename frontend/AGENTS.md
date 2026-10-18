# Investor SPA

Vue 3 + frappe-ui, read-only, served at `/bond-investor` by
`bond_management/www/bond_investor.py` and a `website_route_rules` entry. The
Vite build is served from `/assets/bond_management/frontend/`. The root
`AGENTS.md` still applies; `CLAUDE.md` here is a symlink to this file.

- Before changing the SPA, Playwright setup, investor APIs, investor redirects
  or the legacy investor workspace, read
  [investor-ui-migration.md](../docs/specs/investor-ui-migration.md) and update
  [the progress note](../docs/plans/investor-ui-migration-progress.md) for the
  current slice.
- The SPA calls only `api/investor.py` and `api/investor_reports.py`. It never
  creates, edits, deletes, submits, uploads or parses; that is Desk's job.
- The `frappe-ui` skill is pinned in `skills.lock` to an upstream frappe-ui
  commit that may not match the `frappe-ui` version in `package.json`. Before
  using a component, export or token, check that version and the installed
  `node_modules/frappe-ui` source. Apply the skill's `SETUP.md` to
  fresh projects only; keep this app's dependency pins and Vite config unless a
  dependency change is requested.
- Financial values and durable status come from the server. Show pending and
  failed states; no optimistic updates.
- Load `frappe-spa-client` for API client and unit-test work. Any new non-GET
  investor call must send the CSRF token and get a unit test.

Commands, from the app root: `yarn dev`, `yarn build`, `yarn lint`,
`yarn typecheck`, `yarn test:unit` (Vitest for `src/lib`; from `frontend/`,
`yarn test`).
