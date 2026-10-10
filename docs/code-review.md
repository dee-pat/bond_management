# Manual Codex PR reviews

Codex reviews this repository through its GitHub integration. When connected
with a ChatGPT account, reviews use that account's eligible subscription usage
and limits. An OpenAI Platform API key is not needed.

## Connect and keep reviews manual

1. Sign in to ChatGPT with the account whose subscription should cover reviews.
2. Open Codex's code review settings and connect `dee-pat/bond_management` to
   the GitHub integration. Grant access to this repository if it is not already
   connected.
3. Enable access to code review for this repository. Keep **Automatic review**
   off in both repository settings and personal preferences. Keep any automatic
   security-review policy off too. Confirm the displayed settings before
   requesting a review; a repository file cannot configure these account options.

See the official [GitHub review guide](https://learn.chatgpt.com/docs/third-party/github)
and [subscription authentication guide](https://learn.chatgpt.com/docs/auth#openai-authentication).

## Request a review

Post a conversation comment on an open pull request:

```text
@codex review
```

For a focused pass, include the area to examine:

```text
@codex review for Frappe permission boundaries and migration safety
```

Codex reacts while reviewing and posts its findings on the PR. Confirm that a
review appeared for the intended revision. A reaction alone is not evidence
that the review completed. Request another review manually after relevant fixes.

Root and nested `AGENTS.md` files supply review guidance. This app's **Code
Review Rules** cover runtime API validation, portfolio/document permissions,
framework transactions, migrations, concurrency, financial precision, private
attachments, and Desk/SPA integration. The domain model and verification guide
remain the source of truth for relationships and required checks.

Reviews are advisory. Existing tests, CI checks, and human review still determine
whether a change is ready to merge. If no review appears, check the repository
connection, code review access, subscription usage limits, and exact mention.

## Migration from PR-Agent

The PR-Agent workflow, configuration, and API setup guide have been removed.
The old `/review` comment and Actions workflow are replaced by `@codex review`.
Remove the obsolete `OPENAI_KEY` repository Actions secret and `PR_AGENT_MODEL`
variable if present. Revoke the dedicated provider key in OpenAI settings.
GitHub's stored secret and the provider key are separate objects.

## Verification evidence — 2026-10-09

The command evidence below records the site names in use at the time
(`dev.local` and `test_site`). The current Bond Management pair is
`bond-management-dev.localhost` and `bond-management-test.localhost`; use
`docs/verification.md` for current commands.

- Risk classification: review configuration and agent guidance only; no app
  runtime, schema, or financial behavior change.
- Required gates: scoped formatting, diff checks, and the shared pre-push gate.
- Commands executed / exit statuses:
  - From the configured bench, `apps/bond_management/scripts/verify.sh pre-push`:
    **0**, including migration of the existing `test_site`.
  - From the setup worktree, the configured bench's `env/bin/pre-commit run
    --files AGENTS.md README.md docs/code-review.md`: **0**.
  - From the setup worktree, `git diff --check`: **0**.
- Tests passed: 391 app server tests (48 unit, 334 integration, 9 uncategorized),
  4 verification-script tests, and 2 Semgrep rule tests.
- Tests failed: none.
- Tests not run: a live Codex review; account connection/settings must be
  verified first. Playwright and fresh app installation are not applicable to
  this review configuration change.
- Blockers: ChatGPT sign-in is required to inspect account-side review settings.
- Unverified local/CI differences: repository files do not prove the GitHub
  integration is connected, that automatic review is off, or that a subscription
  review completed. Local gates use the existing macOS bench and `test_site`.
- Domain-model review: graphs and notes reviewed; no mapped DocType, ownership,
  attachment, report, API, or service relationship changes.
