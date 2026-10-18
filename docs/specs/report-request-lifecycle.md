# Investor report request lifecycle

## Goal and scope

Share the request lifecycle used by Portfolio Performance, Bond Yield Comparison
and Interest Difference so fixes to loading, failures and stale responses have
one owner. This is a behavior-preserving frontend refactor; it changes no API,
financial calculation, permission, report projection, chart or clipboard format.

## Contract

`frontend/src/lib/report.ts` exposes `useReportRequest<T>(fetcher, errorMessage)`.
The fetcher returns the existing `{ report: T }` API response. Each instance owns
its report, loading, has-run and error refs, and a monotonically increasing
request token. It does not fetch on mount or watch filters itself.

- `load()` clears the previous report/error, marks the request pending and
  displays only the latest request's result. Empty reports remain successful.
- A current 401 redirects through the existing login helper. Other failures
  show the page's existing generic message, never server error text.
- Stale success, failure, authentication failure and completion cannot change
  the current state or redirect the user.
- `invalidate()` makes all outstanding requests stale and restores the initial
  state without cancelling their underlying network requests.
- Pages retain their existing filter watches, guards and `nextTick()` timing.
  Yield default-date loading remains separate. Performance and yield pages
  retain their independent clipboard request tokens and reset them on each
  accepted report run and filter change.

Server APIs remain authoritative and permission-scoped. Public endpoint paths,
request arguments and response shapes are unchanged. Reviewing
`docs/domain-model.md` found no relationship or service-flow change.

## Verification and rollout

Build a tracer slice with the helper, deferred-promise unit tests and Interest
Difference, then migrate the two clipboard-enabled pages. Unit tests cover
initial/success/empty/failure/retry state, synchronous failures, latest-request
ordering, stale authentication errors, invalidation and independent instances.
Extend the existing Performance browser recovery flow to retry successfully;
existing report/browser tests cover date edits, clipboard actions and responsive
pending requests. Run lint, frontend lint/typecheck/unit/build and the complete
authenticated UI suite because the helper is shared runtime.

Acceptance: all three pages use one lifecycle owner, existing observable
behavior and regression checks pass, and the final diff contains no unrelated
changes. No migration, dependency or feature flag is needed. Rollback is a
source revert and rebuild. Publish only with explicit user authorization and
inspect the PR checks on the published revision. Follow-ups: none required;
list/detail and clipboard lifecycles remain separate.
