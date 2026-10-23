# Preserve blocking kit rules

PR [#104](https://github.com/dee-pat/bond_management/pull/104), finding F1:
the merged ERROR-only scan silently skips kit rules whose severity becomes
WARNING or INFO after a vendor update.

Restore a separate blocking kit scan without a severity filter. Keep Frappe
ERROR rules blocking, Frappe WARNING rules advisory, and vendored rule fixtures
excluded from app scans. No YAML parser or dependency is needed.

The implementation and regression coverage are complete for PR #104.
Publication and verification evidence are tracked in the PR.
Acceptance requires Decimal float literals to block at ERROR, WARNING and INFO,
with the existing transaction and Frappe advisory behavior preserved. The shared
lint gate exercises these cases against copied rules in temporary apps.

The domain model was reviewed: no mapped relationships, runtime data flows,
financial conventions, permissions or private-file behavior change.
