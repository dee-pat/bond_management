# Manual Frappe PR reviews

PR-Agent runs in an isolated GitHub Actions container. The workflow uses
PR-Agent v0.47.0, pinned to its Docker image digest. It retrieves pull request
data through GitHub's API and posts an advisory review comment. It requires no
installation in the Frappe bench or on an app site.

## Activate

1. Add an Actions repository secret named `OPENAI_KEY` in
   [Bond Management's Actions settings](https://github.com/dee-pat/bond_management/settings/secrets/actions).
   Enter the provider API key directly in GitHub. Keep it out of source files,
   command history, PR comments, and chat.
2. Optionally set the Actions repository variable `PR_AGENT_MODEL` to an OpenAI
   API model ID available to that key. The workflow otherwise uses `gpt-5.6`,
   the pinned PR-Agent release's default model. Fallback models are disabled so
   a review uses the selected model or reports a failure.
3. Merge `.github/workflows/pr-agent.yml`, `.pr_agent.toml`, and this guide into
   the repository's default branch (`main`). GitHub loads comment-triggered
   workflows from that branch, and PR-Agent reads its configuration and context
   from the default branch.

The model API has usage charges separate from GitHub Actions. PR diffs and the
configured repository context are submitted to that provider. Use a key and
provider policy appropriate for the repository.

## Request a review

On an open pull request, post a new conversation comment containing exactly:

```text
/review
```

Only repository owners, organization members, and collaborators can trigger
the comment flow. Ordinary comments, commands with extra arguments, edited
comments, issue comments, and comments from bots do not request a review.

Alternatively, open **Actions → PR Agent (manual) → Run workflow**, select the
default branch, and enter the pull request number. The equivalent CLI command is:

```bash
gh workflow run pr-agent.yml --repo dee-pat/bond_management -f pr_number=123
```

Replace `123` with an open pull request number. Requesting another review
updates the persistent review comment. Opening a PR or pushing commits does not
automatically invoke PR-Agent. Reviews of the same PR run serially.

## Review guidance

`.pr_agent.toml` supplies a Frappe v16 checklist covering runtime API type
validation, permissions, Query Builder reads, framework transactions, document
hooks, child tables, migrations, fresh-install invariants, concurrency, indexes,
and Desk/SPA integration. It also includes this app's financial and attachment
rules. The prompt prioritizes concrete defects with a trigger and consequence.
DocType/workspace JSON and `patches.txt` remain in the review; built frontend
bundles, vendor directories, and package lock files are excluded.

Trusted context comes from the default branch:

- `AGENTS.md`: app policies and financial conventions.
- `docs/domain-model.md`: relationships and processing flows.
- `docs/verification.md`: verification requirements.

The review has at most five findings. Large diffs may use up to three review
chunks; the coverage footer reports omitted files. Review comments include run
details and available cost estimates to help evaluate the pilot. PR-Agent does
not execute app tests. Existing verification gates and human review determine
whether a change can merge.

## Workflow permissions and failures

The job has `contents: read`, `issues: write`, and `pull-requests: write`. It
fetches code through the API and executes a fixed `review` command. It does not
check out, install, build, or execute pull request code. Comments cannot supply
runtime configuration overrides or request other PR-Agent tools. Automatic
approval and review labels are disabled.

If a review does not appear, inspect the workflow run:

- Missing `OPENAI_KEY`, an invalid number, or a closed PR fails validation.
- Provider authentication, model access, quota, or review failures fail the run.
- An unauthorized comment or a comment other than exact `/review` skips the job.
- If no run appears, confirm the workflow is on `main`, Actions is enabled, and
  organization policy allows the pinned Docker action.

Fix the cause and post a new `/review` comment or run the workflow again.
PR-Agent's manual review is advisory and should not be a required branch check.

## Update PR-Agent

Review the upstream release notes, resolve the selected release image's digest,
and update the workflow's pinned digest and version comment together. Review
configuration changes against that release and validate the workflow locally.
The relevant upstream references are the
[GitHub integration guide](https://docs.pr-agent.ai/installation/github/),
[configuration guide](https://docs.pr-agent.ai/usage-guide/configuration_options/),
and [releases](https://github.com/The-PR-Agent/pr-agent/releases).

## Setup verification — 2026-10-09

- Risk classification: CI integration; no Frappe runtime, schema, or financial
  behavior changes. Model access and GitHub execution need activation checks.
- Required gates: workflow validation, scoped formatting/configuration checks,
  and the shared `pre-push` gate.
- Commands executed and exit statuses:
  - From the app root,
    `/tmp/bond-pr-agent-tools/actionlint .github/workflows/pr-agent.yml`: **0**.
    The temporary actionlint v1.7.12 binary matched its official release checksum.
  - From the app root,
    `../../env/bin/pre-commit run --files .github/workflows/pr-agent.yml .pr_agent.toml docs/pr-agent.md README.md`:
    **0**. The existing pre-commit exclusion skips `.github`; actionlint validated
    the new workflow's YAML and GitHub expressions separately.
  - From the bench root,
    `apps/bond_management/scripts/verify.sh pre-push`: **0** on the final workflow
    and configuration. This included migration of the existing `test_site`.
  - From the app root, `git diff --check`: **0**.
  - `gh attestation verify oci://index.docker.io/pragent/pr-agent@sha256:31b9aac6ab067bada9a0c1b001d30ebc500ea4487e00a93c18c59b9ef5fa66db --repo The-PR-Agent/pr-agent --format json`:
    **0**. Provenance identifies the upstream `v0.47.0` release workflow and
    source commit `8e5a9295973b24af4b70cafd0b660a230811ef9e`.
- Tests passed: 391 app server tests (48 unit, 334 integration, 9 uncategorized),
  4 verification-script tests, and 2 Semgrep rule tests. TOML settings were also
  checked against the pinned upstream configuration and ignore definitions.
- Tests failed: none.
- Tests not run: a live model review/GitHub workflow invocation; the first
  provider call awaits an explicit manual request. Playwright and fresh Frappe
  installation checks are not applicable to this isolated reviewer.
- Blockers: none for the local setup. The `OPENAI_KEY` Actions repository secret
  was verified present on 2026-10-09; publication to `main` activates the triggers.
- Unverified local/CI differences: app checks used the existing macOS bench and
  `test_site`; the new reviewer runs on Ubuntu in its pinned Linux container.
  Container imports, GitHub comment publishing, and model access need the first
  manual run after activation.
- Domain-model review: the graphs and notes were reviewed; this setup changes no
  mapped DocType, ownership, attachment, report, API, or service relationship.
