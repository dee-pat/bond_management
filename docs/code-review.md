# Code reviews

This guide covers manual Codex PR reviews and the
[review output contract](#review-output-contract) shared by Codex and Claude
Code reviews.

## Codex review setup

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

## Review output contract

Apply this contract to reviews of PRs, commits, and uncommitted changes by
Codex or Claude Code. Keep findings grounded in the changed code and follow the
app's Code Review Rules for technical checks.

### Summary and score

Start the review summary with `Merge readiness: N/5`, or
`Merge readiness: N/5 (provisional)` when the score is provisional, then the
reviewed head commit and base revision, and a short rationale tied to the
findings and verification.
For uncommitted changes, identify the base commit and the staged/unstaged scope;
the score applies only to that inspected snapshot. Reassess after fixes rather
than carrying the previous score forward.

Assign each actionable finding one priority:

- **P0**: immediate, broad risk such as unrestricted financial-data exposure,
  destructive data corruption, or a broken critical operation.
- **P1**: critical security, financial-correctness, or data-loss defect below
  the P0 threshold.
- **P2**: major correctness or regression defect that requires changes before
  merge.
- **P3**: other actionable defect that needs a fix.

Choose the lowest applicable score from this rubric; the highest-priority
finding sets the defect ceiling. Do not average defects away or assign scores
from finding counts:

| Score   | Meaning                                                                                                                   |
| ------- | ------------------------------------------------------------------------------------------------------------------------- |
| **0/5** | A confirmed P0 finding remains. Stop merge and address it immediately.                                                    |
| **1/5** | A P1 finding remains.                                                                                                     |
| **2/5** | A P2 finding remains.                                                                                                     |
| **3/5** | A P3 finding remains, or a required check failed for the reviewed revision.                                               |
| **4/5** | No actionable findings, but required verification is missing, stale, or blocked, or a specific residual concern remains.  |
| **5/5** | No actionable findings, required verification passed for the reviewed revision, and no specific residual concern remains. |

Report review scope and residual concerns explicitly. Distinguish an established
defect from a question needing investigation; uncertainty alone does not justify
a defect finding or 0/5. Scores express an evidence-based assessment, not a
guarantee that the code is bug-free or authorization to merge.

Include verification commands and observed exit statuses, required CI results
for the exact revision, and checks not run or blocked. Cite existing CI evidence
as such rather than claiming to have executed it. Mark the score **provisional**
when required verification is missing, stale, or blocked; the maximum then is
**4/5**. A failed required check caps the score at **3/5** even when no defect
is identified; report the failure separately and use a lower score when a
confirmed finding warrants one. Verification requirements come from
[verification.md](verification.md).

### Weekly usage estimate

When the review environment exposes an authenticated usage tool for the
reviewing agent's own subscription (Codex or Claude), capture the weekly
window's used percentage, limit/bucket identity, window duration,
reset timestamp, and observation time immediately before reviewing and again
after the review work. Use the matching weekly bucket from both snapshots and
report `after used percentage - before used percentage` in **percentage points
of the weekly allowance**. For example: `Weekly usage: estimated account-wide
increase of 2 percentage points (27% to 29% used).`

Label this an account-wide estimate: concurrent work on the same account,
reporting delays, and rounded percentages prevent exact attribution to the
review. A zero delta
means no visible change, not proof of zero consumption. Include the observation
times and reset timestamp so the measurement interval is clear. Never convert
tokens, elapsed time, or a model's price into a subscription-usage percentage.

If either snapshot is missing, the bucket/window/reset changes, the percentage
decreases, or the review environment lacks usage access, report `Weekly review
usage: unavailable` with the reason. A current account percentage alone is not
review consumption. Repository guidance cannot grant GitHub's native reviewer
access to account usage tools; include this field in the companion summary when
needed. Report only the reviewing agent's subscription; a Claude Code review
reports Codex usage only when it actually invokes Codex and captures matching
Codex snapshots, and the reverse applies to Codex reviews. Usage availability
does not change the merge-readiness score or block the review.

### Estimated cost in USD

Convert a valid weekly usage delta into a **proportional subscription-cost
estimate**, using a user-supplied or verified subscription price in USD. State
the price and billing period used. For a monthly price `M` and usage increase
`D` in percentage points:

```text
Estimated allocated cost (USD) = M × 12 ÷ 52 × D ÷ 100
```

For annual billing, use `annual USD price ÷ 52 × D ÷ 100`. This convention
allocates the subscription evenly across 52 weeks and proportionally across
the weekly allowance. It does not measure actual provider cost, API token
charges, or an additional bill. The subscription also covers other features;
this is a budgeting proxy rather than an official provider cost conversion.

For example, a hypothetical $20/month subscription and a 2-percentage-point
increase give `20 × 12 ÷ 52 × 2 ÷ 100 = $0.0923`, reported as about **$0.09**.
Show the usage delta beside the estimate and retain its account-wide attribution
and rounding caveats. For positive estimates below one cent, report `<$0.01`.

If the price is unknown, provide the formula and report `Estimated allocated
cost: unavailable (subscription price not supplied or verified)`. If the usage
delta is unavailable, the cost estimate is unavailable too. A plan name alone
does not establish the user's billed price. Keep credits, paid resets, and other
charges separate; include them only when directly attributable billing evidence
exists. Cost availability does not change the score or block the review.

### Findings

List actionable findings in priority order. Give each a review-local ID (`F1`,
`F2`, and so on), priority, file and tight line range, concrete trigger, affected
user or data, and evidence connecting the changed code to the impact. Include
the intended correction and a meaningful regression check. Keep questions and
optional suggestions separate from findings and fix prompts.

### Ready-to-copy fix prompts

When actionable findings exist, end the summary with separate fenced text
blocks labeled **Codex fix prompt** and **Claude Code fix prompt**. Generate one
consolidated prompt per agent covering all findings, ordered by priority and
dependencies. Populate the template below with the actual repository/PR,
reviewed revision, finding IDs, locations, triggers, impacts, suggested fixes,
and regression checks. Replace `[guidance]` with `applicable AGENTS.md files`
for Codex or `CLAUDE.md and applicable parent/directory guidance` for Claude
Code. Include the complete finding details in both prompts so each works in a
fresh chat without the review transcript. Leave no placeholders in the
generated prompts and include no credentials or private financial data.

```text
In [repository/PR], resolve findings [IDs] from the review of [revision and base/scope].
Read [guidance] and docs/verification.md first.
Check the current revision and independently verify each finding against the
affected callers and data flows. Implement the smallest complete root-cause fixes
in priority/dependency order, preserving unrelated changes and existing financial,
permission, private-file, and transaction conventions. Add meaningful regression
coverage for each defect. Review docs/domain-model.md and update it if mapped
relationships change. Run every applicable verification gate and inspect required
CI for the final revision. Review the final diff and report each finding as fixed,
not applicable with evidence, or blocked; include commands, observed results,
remaining verification, and the domain-model review.
Do not commit, push, or merge without explicit user authorization.

Findings:
[Full details for every actionable finding, including priority, intended correction, and regression check.]
```

When no actionable findings exist, state `No actionable findings; no fix prompts
needed.` Report outstanding verification separately instead of inventing fixes.

### Review surfaces with restricted output

Preserve any required review schema and inline-finding format. Put the score
and prompts in the summary field when supported; never disguise them as a bug
finding. If the surface cannot carry the summary, provide a companion summary
in the review chat using the same revision and evidence. Native GitHub review
may restrict findings to high-priority issues; state that scope explicitly and
use a follow-up review chat for a broader assessment. Repository instructions
guide review behavior but cannot configure the integration's output schema.

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
  - From the setup worktree, the configured bench's `env/bin/pre-commit run --files AGENTS.md README.md docs/code-review.md`: **0**.
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
