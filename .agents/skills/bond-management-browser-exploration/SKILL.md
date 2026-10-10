---
name: bond-management-browser-exploration
description: Explore Bond Management's investor SPA or Desk in a live browser, reproduce visible behavior, and gather focused evidence. Use bond-management-testing when the work becomes committed test authoring or execution.
---

# Explore Bond Management in a browser

Use the `playwright-cli` skill for browser command syntax. From this app root, invoke its project-local executable with a named, in-memory session and an explicit local URL, for example:

```sh
yarn playwright-cli -s=bond-management open http://bond-management-dev.localhost --headed
```

Follow [docs/verification.md](../../../docs/verification.md) for site startup, test-site setup, and credentials. Use `bond-management-dev.localhost` for read-only interactive development. Use `bond-management-test.localhost` or a disposable test site for an exploration that must save, submit, post, reconcile, delete, upload, or otherwise mutate financial or attachment data. Keep those actions within a repeatable test flow.

Do not browse production data, save browser profiles or storage state, or put credentials and sensitive financial details in commands, screenshots, notes, or repository files. Prefer visible controls; refresh the accessibility snapshot after interactions and use current element references.

Record the route, user role, viewport, steps, observed result, and relevant console or network errors. Capture a screenshot only when it helps explain the finding. If the finding needs regression coverage, follow [bond-management-testing](../bond-management-testing/SKILL.md) and the app's existing test conventions.
