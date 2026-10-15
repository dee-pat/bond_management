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

Root and nested `AGENTS.md` files supply review guidance. The root file's
**Review guidelines** section applies the app's Frappe, financial, attachment,
and migration rules to the diff. The domain model and verification guide remain
the source of truth for relationships and required checks. For a local agent
review, the `frappe-code-review` skill is the general Frappe checklist.

Reviews are advisory. Existing tests, CI checks, and human review still determine
whether a change is ready to merge. If no review appears, check the repository
connection, code review access, subscription usage limits, and exact mention.

## GitHub review conversations

As part of a requested GitHub PR review or review-fix workflow, resolve existing
review conversations whose findings are verified as addressed by subsequent
changes; include this reconciliation in completion rather than leaving it for a
separate user request.

- Fetch the current PR head and every page of unresolved review threads. Read
  each finding and its replies, then check the current code and relevant change
  history. An outdated marker or a reply claiming a fix is not proof.
- Resolve only findings fully addressed at the current head. Leave partial
  fixes, regressions, unanswered questions, and still-applicable findings open.
  Check each conversation independently, including older duplicates of a newer
  finding; a fix that was later lost does not qualify.
- When implementing fixes, run the applicable verification gates and wait for
  required CI on the pushed revision before resolving its conversations. If
  the head changes during reconciliation, recheck affected findings against it.
- Use the platform's resolve-thread operation, preserving the discussion and
  other reviewers' comments. Resolution alone does not authorize posting replies
  or changing review approvals.
- Read back thread states and report the resolved count and remaining open
  issues, with links when useful. If permissions or tools prevent resolution,
  report the exact blocker and which verified conversations remain open.
