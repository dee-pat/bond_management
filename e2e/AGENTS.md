# Browser tests and exploration

Playwright specs for the investor SPA (`investor/`) and Desk (`desk/`). Read
[README.md](README.md) for layout, Python-vs-Playwright ownership and the seeded
fixture lifecycle. The root `AGENTS.md` still applies; `CLAUDE.md` here is a
symlink to this file.

## Writing specs

1. Find the rule or visible behaviour in
   [testing-matrix.md](../docs/testing-matrix.md), then read the nearest spec,
   fixture and helper before choosing where the test goes.
2. Add Playwright coverage only for visible form, report, workspace and routing
   behaviour that server tests do not already cover. Keep one focused smoke flow
   per critical surface; do not mirror the financial or permission matrix.
3. Select by stable routes, labels, roles and data attributes. Do not assert CSS
   layout, SVG geometry or formatter registration. Prefer visible controls; use
   `window.cur_frm` or `script_manager.trigger` only for a justified
   client-script hook, such as deterministic PDF attachment parsing.
4. Add delayed, failed, stale-response, retry or duplicate-request cases only
   for a demonstrated browser regression or a risk no lower layer can test.
   Keep each one deterministic and focused on visible recovery.

## Running

Serve the test site explicitly, load credentials, then run one spec from the
app root. Projects: `investor-desktop`, `investor-mobile`, `desk`.

```bash
bench --site bond-management-test.localhost serve --port 8001 --noreload
set -a; source "$HOME/.config/bond_management/test-browser.env"; set +a
BASE_URL=http://localhost:8001 yarn playwright test e2e/investor/bonds.spec.ts --project=investor-desktop
```

Never copy the credentials file contents into the repo or logs. Login failures,
browser install and CI bootstrap: [verification.md](../docs/verification.md).

## Exploring in a browser

Use the `playwright-cli` skill for command syntax, with a named in-memory
session and an explicit local URL:

```sh
yarn playwright-cli -s=bond-management open http://bond-management-dev.localhost --headed
```

- Read-only exploration may use the dev site. Anything that saves, submits,
  posts, reconciles, deletes or uploads runs on the test site or a disposable
  site, inside a repeatable flow.
- Never browse production data or save browser profiles or storage state. Keep
  credentials and real financial details out of commands, screenshots and
  notes.
- Refresh the accessibility snapshot after each interaction and use current
  element references.
- Record route, role, viewport, steps, observed result, and relevant console or
  network errors. Take a screenshot only when it explains the finding. A
  finding that needs regression coverage becomes a spec under _Writing specs_.
