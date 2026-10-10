# Bond Management verification

Read this file for changes, verification, CI failures, and completion evidence.
Commands below run from the bench directory unless stated otherwise.

## Verification evidence

Before committing or pushing, record local verification evidence. Before
reporting completion, include final CI results for any required remote checks.
Record:

- Risk classification:
- Required gates:
- Commands executed:
- Exit statuses:
- Tests passed:
- Tests failed:
- Tests not run:
- Blockers:
- Unverified local/CI differences:

For GitHub Actions, fresh-site bootstrap, Playwright setup, or other
environment-sensitive changes, document the remaining local-vs-CI platform
differences in the final field.

## Required gates

- Prefer the existing `bond-management-test.localhost` and configured bench for local verification.
  Routine server and UI gates migrate and reuse `bond-management-test.localhost`; do not create a
  separate local site for ordinary test runs. `bond-management-dev.localhost` and `bond-management-test.localhost` are
  Bond Management's persistent development/test pair; do not install another
  app on either site.
- Match verification to the risk of the change: documentation, agent-guidance,
  and test-only edits need formatting/lint plus the affected test; backend
  business, permission, migration, hook, or shared utility changes need the
  targeted test, complete affected module, and full server suite; client-only
  changes need lint plus the focused Playwright spec, with the full UI suite
  when they change a shared runtime or critical user journey.
- From the bench directory, run
  `apps/bond_management/scripts/verify.sh pre-push`. This shared gate runs
  pre-commit, migrates `bond-management-test.localhost`, and runs the complete server suite. GitHub
  Actions must call the same script so local and CI commands cannot drift.
- Changes to JavaScript, reports, DocType metadata, permissions, workspaces, or
  other Desk behavior must run
  `apps/bond_management/scripts/verify.sh pre-push-ui`. It includes the
  complete server gate, frontend lint/typecheck/build, test-site preparation,
  and the complete authenticated Playwright suite for investor and Desk flows.
  Browser tests require `FRAPPE_USER` and `FRAPPE_PASSWORD` for the seeded
  investor plus `FRAPPE_ADMIN_USER` and `FRAPPE_ADMIN_PASSWORD` for Desk. Set
  `BASE_URL` (or `PLAYWRIGHT_BASE_URL`) when the test server is not at its
  default address.
- Changes to patches, schema, hooks, dependencies, installation, or manual
  indexes must also pass a fresh-install check matching the GitHub Actions
  setup. A successful CI clean install on the exact commit satisfies this
  check. Create a local fresh site only when CI cannot cover it or local
  diagnosis needs one; keep it under the configured bench and use a unique
  temporary site name. After the check completes, capture the needed logs and
  results, then drop that temporary site with
  `bench drop-site <temporary-site> --no-backup`, including after a failed
  check. This returns the app to its two persistent sites. Obtain approval
  before recreating, dropping, or restoring either persistent site, or before
  dropping/restoring any other pre-existing local site.

## Completion and failure handling

- If a required command cannot run because a service, browser, dependency, site,
  or credential is unavailable, report the exact command, blocking condition,
  and remaining verification. Do not substitute an unrelated check.
- When GitHub Actions fails, inspect the traceback and reproduce the failing
  test in isolation and in the full suite before changing implementation or
  assertions. Do not weaken an assertion merely to make CI pass.
- Before implementing a multi-phase feature, record the intended slice and
  verification steps in the project documentation. For a small bug fix, a
  focused issue note and regression test are sufficient.

## Playwright browser setup and recovery

- Use `bond-management-test.localhost` for automated browser tests. The browser gate migrates it,
  enables the investor app, and runs the idempotent investor-data seed helper
  before Playwright. It does not create, drop, or restore a site.
- When bootstrapping a fresh site, enable the investor app and seed its browser
  user and fixtures before starting the web process. Frappe must load the site
  feature flag at process startup; the CI workflow does this explicitly.
- Install the Playwright browser when it is missing with
  `yarn playwright install chromium` from the app root. CI installs Chromium
  and its system dependencies in its run-scoped bench.
- Start the intended local site explicitly so the browser cannot land on a
  different default site: `bench --site bond-management-test.localhost serve --port 8001 --noreload`.
  Set `BASE_URL=http://localhost:8001` for the browser gate in that case.
- Keep investor credentials separate from Administrator credentials. The
  investor seed helper uses `FRAPPE_USER` and `FRAPPE_PASSWORD`; the Desk
  browser setup uses `FRAPPE_ADMIN_USER` and `FRAPPE_ADMIN_PASSWORD`. Never
  write either password to repository files. In CI, the fresh site uses
  `Administrator` with the one-run site password `admin`, while the investor
  password is generated and masked for that job.
- If login fails, verify each credential against `bond-management-test.localhost` and reset only the
  local test Administrator with `bench --site bond-management-test.localhost set-admin-password`.
  Never run destructive credential or cache recovery against `bond-management-dev.localhost` or a
  non-test site. Do not repeatedly rerun browser tests while an account is
  locked.
- Playwright preserves traces on the first CI retry, screenshots on failure,
  videos on failure, and the HTML report locally. Keep the exact command,
  browser logs, trace, screenshot, video, and server log when escalating a
  browser failure.

## CI bootstrap and job boundaries

- CI's fresh-site bootstrap must initialize an explicit bench root, assert that
  its `sites/common_site_config.json` exists before running `bench get-app`, and
  fetch the checked-out app through a local `file://` source. Keep the bench
  initialization path, step working directories, caches, and artifact paths in
  sync. Use a unique run-scoped directory under the runner's temporary folder;
  never reuse a fixed `/home/runner/frappe-bench` path or overwrite an existing
  bench. GitHub's `runner` context is unavailable in `jobs.<job_id>.env`; use
  it in step-level fields or the runner's `$RUNNER_TEMP` variable instead.
- Before starting the UI job's web server, set its disposable Administrator
  password, enable `bond_investor_spa_enabled`, and seed the investor browser
  user and fixture records. The web process must start after the feature flag
  is set. `scripts/verify.sh ui` repeats the idempotent seed before Playwright.
- The server CI job runs the shared lint and full server gate once. The UI job
  has its own run-scoped fresh bench/site and runs
  `apps/bond_management/scripts/verify.sh ui`, which prepares the site and runs
  the full Playwright suite without repeating the server suite.
