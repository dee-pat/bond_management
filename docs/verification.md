# Bond Management verification

Read this file for changes, verification, CI failures, and completion evidence.
Commands below run from the bench directory unless stated otherwise.

## Definition of done

A change is done when its own acceptance criteria are met and every applicable
item below holds. Record any item that does not apply, with the reason, in the
evidence.

- **Proven:** new or changed behavior has a test that fails without the change
  and passes with it; a bug fix adds its regression test first.
- **Conventions held:** the financial, attachment, and investor-isolation rules
  in `AGENTS.md` (_Architecture_, _Bond financial conventions_, _Attachments
  and secrets_) still hold, or changed only with an explicit business decision
  and boundary tests.
- **Install and migrate:** a data patch is idempotent and registered; an
  invariant it creates is also bootstrapped in `after_install`; the
  fresh-install check below passed.
- **Docs in step:** `docs/domain-model.md` is updated, or its review is
  recorded; the testing matrix, specs, and agent guidance describe the new
  behavior.
- **Clean diff:** nothing outside the task's scope; no debug output, dead code,
  or commented-out blocks; no secrets, PDF passwords, or site credentials.
- **Verified:** every required gate below exited zero on the final commit, and
  required CI checks passed on it.

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

- Match verification to the risk of the change: documentation, agent-guidance,
  and test-only edits need formatting/lint plus the affected test; backend
  business, permission, migration, hook, or shared utility changes need the
  targeted test, complete affected module, and full server suite; client-only
  changes need lint plus the focused Playwright spec, with the full UI suite
  when they change a shared runtime or critical user journey.
- From the bench directory, run
  `apps/bond_management/scripts/verify.sh pre-push`. This local combined gate
  runs the `lint` stage (pre-commit and the other lint checks), migrates
  `bond-management-test.localhost`, and runs the complete server suite. GitHub
  Actions runs the same script's stages separately (`lint` in the Linters
  workflow, `server` and `ui` in CI) so local and CI commands cannot drift.
- Changes to JavaScript, reports, DocType metadata, permissions, workspaces, or
  other Desk behavior must run
  `apps/bond_management/scripts/verify.sh pre-push-ui`. It includes the
  complete server gate, frontend lint/typecheck/build, test-site preparation,
  and the complete authenticated Playwright suite for investor and Desk flows.
  Browser tests require `FRAPPE_USER` and `FRAPPE_PASSWORD` for the seeded
  investor plus `FRAPPE_ADMIN_USER` and `FRAPPE_ADMIN_PASSWORD` for Desk. Set
  `BASE_URL` (or `PLAYWRIGHT_BASE_URL`) when the test server is not at its
  default address.
- The individual stages are `lint`, `server`, `frontend`, `ui` and
  `playwright`. `ui` and `playwright` prepare the configured test site
  themselves (migrate, enable the investor SPA, seed fixtures) before running
  Playwright; no manual setup is needed.
- The opt-in stages `lifecycle` and `share-race` each create a uniquely named
  temporary site, run every phase of their helper, and drop the site whether
  the run passed or failed. Set `DB_ROOT_PASSWORD` when the bench has no
  `root_password`; `share-race` also needs the `BOND_SHARE_LOCK_*` observer
  variables. The _Opt-in suites_ workflow runs both nightly, on
  `workflow_dispatch`, and on PRs that change its harness; run them locally for changes to patches, install hooks,
  or share and User Permission consistency.
- CI pins Frappe to the exact tag in `FRAPPE_VERSION` (in `ci.yml` and
  `opt-in.yml`). Bump both together, deliberately, after checking the release.
- Changes to patches, schema, hooks, dependencies, installation, or manual
  indexes must also pass a fresh-install check matching the GitHub Actions
  setup. A successful CI clean install on the exact commit satisfies this
  check. Create a local fresh site only when CI cannot cover it or local
  diagnosis needs one, following _Temporary sites_ below. The migration
  lifecycle uses `bond-management-lifecycle-<32-hex-id>.localhost`; follow its
  specification for the opt-in and phase sequence.

## Completion and failure handling

- If a required command cannot run because a service, browser, dependency, site,
  or credential is unavailable, report the exact command, blocking condition,
  and remaining verification. Do not substitute an unrelated check.
- When GitHub Actions fails, inspect the traceback and reproduce the failing
  test in isolation and in the full suite before changing implementation or
  assertions.
- Before implementing a multi-phase feature, record the intended slice and
  verification steps in the project documentation. For a small bug fix, a
  focused issue note and regression test are sufficient.

## Sites and credentials

### Environment baseline

Local and CI development use Python 3.14, Node 24, MariaDB 11.8 or 12.3, and
Redis 6 or newer. Check deployment compatibility against the target Frappe v16
release and hosting environment.

Use the existing configured bench for all development and verification. Keep
every site under that bench; do not create temporary or copied bench
directories. Do not record site credentials or machine-specific database
configuration in repository files.

### Persistent site pair

`bond-management-dev.localhost` (interactive development) and
`bond-management-test.localhost` (automated server and UI tests) are Bond
Management's persistent pair. Do not install another app on either site; each
other installable app in the bench owns its own sites. Routine gates migrate and
reuse the test site; do not create a separate local site for ordinary test runs.
Obtain approval before recreating, dropping, or restoring either persistent
site, or before dropping/restoring any other pre-existing local site.

Prepare the test site once before routine testing:

```bash
bench --site bond-management-test.localhost install-app bond_management
bench --site bond-management-test.localhost set-config allow_tests true
bench --site bond-management-test.localhost migrate
```

Interactive development:

```bash
DEV_SITE="${DEV_SITE:-bond-management-dev.localhost}"
bench --site "$DEV_SITE" migrate
bench --site "$DEV_SITE" backup --with-files
```

### Temporary sites

When a test genuinely needs an additional local site (including local
fresh-install checks), create a uniquely named temporary site under the
configured bench. After the test finishes, capture its required logs and
results, then drop it with `bench drop-site <temporary-site> --no-backup`,
whether the test passed or failed. This keeps the persistent pair at two sites.
Never drop the persistent pair under this rule. The opt-in migration lifecycle
helper follows the site naming and opt-in steps in
[migration-lifecycle.md](specs/migration-lifecycle.md).

The opt-in investor share-race helper
(`bond_management/bond_management/tests/investor_share_concurrency.py`) runs
on a uniquely named `bond-management-race-<32-hex-id>.localhost` site with Bond
Management installed and `allow_tests` enabled. Set `BOND_SHARE_RACE_BENCH` to
the configured bench path and provide the observer credentials privately as the
module docstring describes. Run its `seed` and then `run` phases, capture the
results, and drop the site even when a phase fails; `verify.sh share-race` does
all of this. The helper rejects both persistent sites and sites outside the
configured bench.

For Claude Code, `.claude/settings.json` runs `scripts/claude_guard.py` before
each Bash or Read call. It splits commands the way Bash does (quotes,
separators, redirections, `$( )` and backticks) and fails closed: drop, trim,
restore, reinstall and forced new-site commands need a literal
`bond-management-<name>-<32-hex-id>.localhost` temporary site. `bench` and
`printenv` are recognised by basename in any position in a segment; `env` is
also checked after wrapper commands and their options. Any command naming the
credential file or a site configuration file (literally or by a wildcard) is
blocked except `source` of the credential file. Environment dumps and any real
expansion of a secret-named variable are blocked, whatever the program;
single-quoted and escaped references remain literal. Heredoc bodies are checked
like commands, so put text that quotes these forms in a file. A path built from
a variable or a bare `*` cannot be checked before the command runs: the hook
rejects variable sites for destructive commands, but not variable paths. It
backs up these rules; it does not replace them, since code that runs other code
can always get past it.

### Credentials

Local browser-test credentials live outside the app in
`$HOME/.config/bond_management/test-browser.env`. Load them with
`set -a; source "$HOME/.config/bond_management/test-browser.env"; set +a`.
Never copy the file contents into repository files or logs.

## Local runtime recovery

- Start MariaDB when it is unavailable: `brew services start mariadb`. For
  Redis connection failures, confirm Redis is running with its configured
  connection details.
- Inspect this bench's processes before recovering a broken state:
  `pgrep -af "${PWD}/apps/frappe|${PWD}/Procfile"`, then `bench restart`.
- `DocType not found`: verify the app is installed on the site, then migrate.
- Bench build failures: check the Node and Yarn versions.

## Playwright browser setup and recovery

- Use `bond-management-test.localhost` for automated browser tests. The browser
  gate migrates it, enables the investor app, and runs the idempotent
  investor-data seed helper before Playwright. It does not create, drop, or
  restore a site.
- When bootstrapping a fresh site, enable the investor app and seed its browser
  user and fixtures before starting the web process. Frappe must load the site
  feature flag at process startup; the CI workflow does this explicitly.
- Install the Playwright browser when it is missing with
  `yarn playwright install chromium` from the app root. CI installs Chromium
  and its system dependencies in its run-scoped bench.
- Start the intended local site explicitly so the browser cannot land on a
  different default site:
  `bench --site bond-management-test.localhost serve --port 8001 --noreload`.
  Set `BASE_URL=http://localhost:8001` for the browser gate in that case.
- Keep investor credentials separate from Administrator credentials. The
  investor seed helper uses `FRAPPE_USER` and `FRAPPE_PASSWORD`; the Desk
  browser setup uses `FRAPPE_ADMIN_USER` and `FRAPPE_ADMIN_PASSWORD`. Never
  write either password to repository files. In CI, the fresh site uses
  `Administrator` with the one-run site password `admin`, while the investor
  password is generated and masked for that job.
- If login fails, verify each credential against
  `bond-management-test.localhost` and reset only the local test Administrator
  with `bench --site bond-management-test.localhost set-admin-password`. Never
  run destructive credential or cache recovery against
  `bond-management-dev.localhost` or a non-test site. Do not repeatedly rerun
  browser tests while an account is locked.
- Playwright preserves traces on the first CI retry, screenshots on failure,
  videos on failure, and the HTML report locally (`playwright-report/`). Keep
  the exact command, browser logs, trace, screenshot, video, and server log
  when escalating a browser failure.

## CI bootstrap and job boundaries

- The Linters workflow runs `scripts/verify.sh lint`. The CI Server job builds a
  fresh bench and site under `$RUNNER_TEMP` (emptied per job), installs the
  checked-out app through a local `file://` source, and runs
  `scripts/verify.sh server`. The UI job builds its own fresh bench and site and
  runs `scripts/verify.sh ui`. Each gate runs once per revision.
- Before starting the UI job's web server, set its disposable Administrator
  password, enable `bond_investor_spa_enabled`, and seed the investor browser
  user and fixture records. The web process must start after the feature flag
  is set. `scripts/verify.sh ui` repeats the idempotent seed before Playwright.
