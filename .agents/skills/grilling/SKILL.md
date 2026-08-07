---
name: grilling
description: Grill the user one decision at a time to stress-test an ambiguous plan or design before implementation. Use when the user explicitly asks to grill, stress-test, or interview them, or when a change has unresolved high-impact decisions involving bond financial rules, dates, permissions, data integrity, migrations, transaction boundaries, attachments, public APIs, or cross-cutting architecture. Do not use for routine fixes, lint or formatting cleanup, mechanical edits, documentation-only changes, or a clear implementation request with no material decisions left.
---

Interview me about every unresolved decision until we reach a shared understanding. Walk down each branch of the decision tree, resolving dependencies one at a time. For each question, provide a recommended answer.

Ask exactly one question at a time and wait for the answer. If a fact can be found in the repository or through available read-only tools, look it up instead of asking. Decisions remain with the user.

Trigger automatically only for ambiguous, high-impact, hard-to-reverse, or cross-cutting work, especially changes involving:

- monetary calculations, rounding, cash-flow signs, financial dates, coupon schedules, maturity, or settlement behavior;
- permissions, server-authoritative financial state, attachments, private data, or security boundaries;
- migrations, schema changes, manual indexes, transaction boundaries, public APIs, or hooks;
- multiple viable architecture, rollout, or user-visible workflow designs.

Do not trigger for a routine implementation whose acceptance criteria are already clear, a single warning or test failure with an evident fix, formatting or lint cleanup, fixture-only changes, or a mechanical refactor. An explicit user request to implement a settled plan also takes precedence over an unnecessary grilling session.

Keep the grilling session read-only. Do not edit files, migrate sites, mutate external systems, commit, or start implementation until the user confirms that shared understanding has been reached. Existing project and Frappe safety rules remain binding throughout.
