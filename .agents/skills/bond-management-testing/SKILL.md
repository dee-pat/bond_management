---
name: bond-management-testing
description: Use when choosing, adding, or reviewing tests in this app, including Python/Frappe business-rule, permission, API, migration, and data-invariant coverage or Playwright checks for visible SPA and Desk behavior.
---

# Bond Management Testing

## Sources of truth

For test work, load the app's [AGENTS.md](../../../AGENTS.md), [testing matrix](../../../docs/testing-matrix.md), [verification guide](../../../docs/verification.md), and [browser test guide](../../../e2e/README.md). They own app rules and site safety, existing coverage, required gates, and browser-test scope.

## Workflow

1. Find the rule or user-visible behavior in the testing matrix, then inspect the nearest implementation, test, fixture, and browser example before choosing a test location.
2. Put financial rules, permissions, API validation, migrations, and persisted data invariants in Python `IntegrationTestCase` tests. Use Playwright for visible SPA or Desk routes, rendering, navigation, and browser-to-Frappe wiring. Keep browser coverage to focused user journeys; Python tests own the complete business and permission matrices.
3. Write a small, deterministic regression that captures the failure with fixed inputs and stable expectations. Follow nearby fixture patterns; test outcomes must not depend on generated record names or wall-clock timing.
4. Put Playwright specs, fixtures, helpers, and authentication setup under the surface folders `e2e/investor/` or `e2e/desk/`. Keep the shared Playwright configuration at the app root.
5. Protect the canonical `test_site`: follow `AGENTS.md` before running tests, reuse the existing site, and do not recreate, drop, or restore it without approval. Use the browser guide's seeded fixture lifecycle for Playwright.
6. Select every required verification mode from `docs/verification.md` and run it through `scripts/verify.sh`. Record commands and observed exit statuses, and report any required gate that could not run.
