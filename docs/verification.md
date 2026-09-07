# Bond Management verification

Read this file for changes, verification, CI failures, and completion evidence.
Commands below run from the bench directory unless stated otherwise.

## Verification evidence

Before committing, pushing, or reporting completion, record:

- Risk classification:
- Required gates:
- Commands executed:
- Exit statuses:
- Tests passed:
- Tests failed:
- Tests not run:
- Blockers:
- Unverified local/CI differences:

For GitHub Actions, fresh-site bootstrap, Cypress runtime setup, or other
environment-sensitive changes, document the remaining local-vs-CI platform
differences in the final field.

## Required gates

- Match verification to the risk of the change: documentation, agent-guidance,
  and test-only edits need formatting/lint plus the affected test; backend
  business, permission, migration, hook, or shared utility changes need the
  targeted test, complete affected module, and full server suite; client-only
  changes need lint plus the focused Cypress spec, with the full UI suite when
  they change a shared runtime or critical user journey. A targeted pass is
  not evidence that a required broader gate passes.
- From the bench directory, run
  `apps/bond_management/scripts/verify.sh pre-push`. This shared gate runs
  pre-commit, migrates `test_site`, and runs the complete server suite. GitHub
  Actions must call the same script so local and CI commands cannot drift.
- Changes to JavaScript, reports, DocType metadata, permissions, workspaces, or
  other Desk behavior must run
  `apps/bond_management/scripts/verify.sh pre-push-ui`, which adds the complete
  headless UI suite. Set `CHROME_BIN` when `chrome` is not on `PATH`.
- Changes to patches, schema, hooks, dependencies, installation, or manual
  indexes must also be validated against a freshly installed site matching the
  GitHub Actions setup. Obtain approval before recreating or dropping a local
  site.

## Cypress runtime and recovery

- For Cypress startup failures, run
  `apps/bond_management/scripts/cypress-runtime.sh diagnose`. If macOS Electron
  aborts after verification, check host/Cypress compatibility before changing tests.
- The UI gate uses Frappe's Cypress runner with a bench-local cache under
  `.cache/Cypress`. `scripts/cypress-runtime.sh` pins the Frappe v16 Cypress
  dependency set, verifies package/binary compatibility, and repairs cache
  failures before the test run. Host-level Electron launch failures are
  reported without repeatedly downloading the same binary. It also clears
  Electron-as-Node and custom-binary environment overrides that make Cypress
  start incorrectly. Do not rely on a machine-global Cypress cache or bypass
  this preflight.
- On macOS in the local development environment, Chrome is installed at
  `/Applications/Google Chrome.app/Contents/MacOS/Google Chrome`; set
  `CHROME_BIN` to this path when `chrome` is not on `PATH`.
- The headless gate defaults `CYPRESS_NO_COMMAND_LOG=1`: Cypress 13.17.0's
  command-log display triggered a runner-frame `ResizeObserver` loop during
  report navigation on Chrome 152. The unchanged spec passes with that display
  disabled. Application errors and assertions remain fatal; screenshots/videos
  omit the command log, while terminal results remain available. Set the value
  to `0` to investigate the runner display. See Cypress's
  [command-log troubleshooting](https://docs.cypress.io/app/references/troubleshooting#disable-the-command-log).
- Cypress failure learnings: run the server explicitly for the tested site:
  `bench --site test_site serve --port 8001 --noreload`. Running `bench serve`
  without `--site` can serve a different site and produce misleading login
  failures. Frappe's `run-ui-tests` command injects `CYPRESS_adminPassword`
  from the selected site's config, so a shell password override may be
  ignored. If login fails, verify the credential directly against `test_site`,
  reset the local test Administrator with `bench --site test_site
  set-admin-password`, and clear stale failed-login cache before retrying;
  never write test credentials to the repository. Do not repeatedly rerun
  Cypress while the account is locked.
- After resolving a Cypress failure, rerun the named spec with `CYPRESS_SPEC`,
  then the complete UI gate. Preserve videos, screenshots, browser logs, and
  the exact command when escalating a runtime failure.
- `CYPRESS_VERSION` in `scripts/cypress-runtime.sh` and the GitHub Actions
  cache key must be updated together when Frappe v16 changes its supported
  Cypress release. Do not override the version in CI or reuse a cache for a
  different binary.

## CI bootstrap and job boundaries

- CI's fresh-site bootstrap must initialize an explicit bench root, assert that
  its `sites/common_site_config.json` exists before running `bench get-app`, and
  fetch the checked-out app through a local `file://` source. Keep the bench
  initialization path, step working directories, caches, and artifact paths in
  sync. Use a unique run-scoped directory under the runner's temporary folder;
  never reuse a fixed `/home/runner/frappe-bench` path or overwrite an existing
  bench. GitHub's `runner` context is unavailable in `jobs.<job_id>.env`; use it
  in step-level fields or the runner's `$RUNNER_TEMP` variable instead.
- The server CI job runs the shared lint and full server gate once. The UI CI
  job runs only the headless Cypress gate against its fresh site; do not make
  the UI job repeat the full server suite unless the failure requires it.
