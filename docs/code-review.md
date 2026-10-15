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

Root and nested `AGENTS.md` files supply review guidance. The root file's
**Review guidelines** section applies the app's Frappe, financial, attachment,
and migration rules to the diff. The domain model and verification guide remain
the source of truth for relationships and required checks. For a local agent
review, the `frappe-code-review` skill is the general Frappe checklist.

Reviews are advisory. Existing tests, CI checks, and human review still determine
whether a change is ready to merge. If no review appears, check the repository
connection, code review access, subscription usage limits, and exact mention.

## GitHub review conversations

During a requested PR review or review-fix workflow, resolve review
conversations whose findings are verified as fixed at the current head. The
`pr-review-threads` skill owns the steps and the `gh` commands.

## Review output contract

Apply this contract to reviews of PRs, commits, and uncommitted changes by
Codex or Claude Code. Keep findings grounded in the changed code and follow the
_Review guidelines_ in the root `AGENTS.md` for technical checks.

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

### 5-hour usage estimate

When the review environment exposes an authenticated usage tool for the
reviewing agent's own subscription (Codex or Claude), capture the 300-minute
window's used percentage, limit/bucket identity, window duration,
reset timestamp, and observation time immediately before reviewing and again
after the review work. Use the matching 5-hour bucket from both snapshots and
report `after used percentage - before used percentage` in **percentage points
of the 5-hour allowance**. For example: `5-hour usage: 27% → 29% used;
estimated account-wide increase: 2 percentage points; 71% remaining.`

Label this an account-wide estimate: concurrent work on the same account,
reporting delays, and rounded percentages prevent exact attribution to the
review. A zero delta means no visible change, not proof of zero consumption.
Include the observation
times and reset timestamp so the measurement interval is clear. Never convert
tokens, elapsed time, or a model's price into a subscription-usage percentage.

If either snapshot is missing, the bucket/window/reset changes, the percentage
decreases, or the review environment lacks usage access, report `5-hour review
usage: unavailable` with the reason. If a current snapshot is available, report
its used/remaining percentages and reset time separately as current account
status; a current percentage alone is not review consumption. Repository guidance
cannot grant GitHub's native reviewer access to account usage tools. An agent
coordinating a native review may capture snapshots around that review and report
the account-wide delta, explicitly including its own activity in the measurement.
Report only the reviewing agent's subscription; a Claude Code review
reports Codex usage only when it actually invokes Codex and captures matching
Codex snapshots, and the reverse applies to Codex reviews. Usage availability
does not change the merge-readiness score or block the review. Report usage
percentages only; omit weekly usage and USD cost conversions.

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

### Publish GitHub review summaries

For a GitHub PR review, publish the summary as a PR conversation comment when
the user has authorized posting. The comment must contain the score and rationale,
reviewed head/base revisions, verification evidence, 5-hour usage or its
unavailability reason, and both populated fix prompts when actionable findings
exist. With no findings, explicitly state that no fix prompts are needed.
Identify the summary's author/source; a coordinating agent's score is its own
assessment, not a score supplied by the native reviewer. Link to the native
review when one exists and state its reviewed revision and scope.

Start each companion comment with a marker that names the reviewing agent and
the full reviewed head SHA, for example
`<!-- bond-management-review-summary agent=claude-code rev=<head SHA> -->`;
use `agent=codex` for Codex. Codex and Claude Code may post from the same GitHub
account, so the account alone does not identify a summary's author. Update an
existing companion comment only when its account, `agent`, and `rev` all match
the current review; otherwise create a new one. Never edit another agent's
summary or a comment without an agent-specific marker. Preserve native bot
comments. Post a new summary for a new revision, and retain the old revision's
evidence. For CLI posting, write the exact Markdown to a
temporary file and use `gh pr comment <PR> --repo <owner/repo> --body-file <file>`;
use the returned comment URL to confirm publication. Read back an updated comment
to verify its body. If posting lacks authorization or fails, prepare the complete
comment and report the blocker; a local answer does not satisfy publication.

### Review surfaces with restricted output

Preserve any required review schema and inline-finding format. Put the score
and prompts in the summary field when supported; never disguise them as a bug
finding. If the native GitHub surface cannot carry the summary, the coordinating
agent must publish the companion comment above using the same revision and
evidence. For local-only reviews, provide the summary in the review chat.
Native GitHub review
may restrict findings to high-priority issues; state that scope explicitly and
use a follow-up review for a broader assessment. The native integration has
been observed to omit custom scores and usage fields. Repository instructions
cannot configure its output schema or schedule companion posting: a supervising
agent must perform the publication step. A standalone native review may therefore
need an explicit follow-up request to publish the companion comment.
