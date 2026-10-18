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
review, the `frappe-pr-review` skill owns the procedure, including untrusted PR
content and `scripts/semgrep-pr.sh`.

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

### Summary, score and blocking

The vendored
[`frappe-pr-review` report format](../.agents/skills/frappe-pr-review/references/report.md)
owns the merge-readiness rubric, the provisional and failed-check caps,
confirmed-only scoring, and the rule for when a finding blocks merge. This app
adds:

- Start the summary with the score, then the reviewed head commit and base
  revision. For uncommitted changes, also name the staged/unstaged scope.
- Required verification comes from [verification.md](verification.md).
- A finding blocks merge only inside the changed component's documented
  guarantee: its spec, or the rules in `AGENTS.md` when no spec narrows them.

### Domain examples that win on conflict

These examples of each priority are this app's, and win over the generic
severity descriptions in the report format:

- **P0**: immediate, broad risk such as unrestricted financial-data exposure,
  destructive data corruption, or a broken critical operation.
- **P1**: critical security, financial-correctness, or data-loss defect below
  the P0 threshold.
- **P2**: major correctness or regression defect that requires changes before
  merge.
- **P3**: other actionable defect that needs a fix.

### Findings

Use the finding format of `frappe-pr-review`'s report, and prefix each heading
with a review-local ID (`F1`, `F2`, and so on). Each finding's trigger names the
affected user or data, and its fix includes a meaningful regression check. Keep
questions and optional suggestions separate from findings and the fix prompt.

### Ready-to-copy fix prompt

When actionable findings exist, end the summary with one fenced text block
labeled **Fix prompt**, covering all findings in priority and dependency order.
The same prompt must work unchanged in a fresh Codex or Claude Code chat. Both
agents follow the same guidance, because every `CLAUDE.md` in this repository
is a symlink to the `AGENTS.md` beside it, so the prompt names repository files
and steps only, never one agent's tools, commands or skills. Populate the template below with
the actual repository/PR, reviewed revision, finding IDs, locations, triggers,
impacts, suggested fixes, and regression checks. Include the complete finding
details so the prompt works without the review transcript. Leave no
placeholders and include no credentials or private financial data.

```text
In [repository/PR], resolve findings [IDs] from the review of [revision and base/scope].
Read AGENTS.md, the AGENTS.md of each directory you change, and
docs/verification.md first.
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

When no actionable findings exist, state `No actionable findings; no fix prompt
needed.` Report outstanding verification separately instead of inventing fixes.

### Publish GitHub review summaries

For a GitHub PR review, publish the summary as a PR conversation comment when
the user has authorized posting. The comment must contain the score and rationale,
reviewed head/base revisions, verification evidence, and the populated fix
prompt when actionable findings exist. With no findings, explicitly state that no fix prompt is needed.
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
been observed to omit custom scores. Repository instructions
cannot configure its output schema or schedule companion posting: a supervising
agent must perform the publication step. A standalone native review may therefore
need an explicit follow-up request to publish the companion comment.
