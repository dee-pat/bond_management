# 0012: Financial documents are never shared

- Status: Accepted
- Date: 2026-10-23

## Context

Investor access comes from the investor role plus Bond Portfolio User
Permissions. Frappe DocShare grants are a second, per-user path to the same
documents. Until now the app allowed read shares inside an investor's
portfolios, so it had to keep every share consistent with role, assignment,
portfolio and attachment changes under concurrent saves: lock ordering,
deferred retries, cleanup hooks and an opt-in share-race harness. The app
itself never creates a share, and no workflow depends on one. Read and write
boundaries are already enforced without shares: the permission hooks and
`InvestorBoundaryMixin` in `utils/investor_permissions.py` and
`utils/investor_shares.py` deny out-of-scope reads, and
`reject_investor_mutation` denies investor writes.

## Decision

- The financial DocTypes are `_financial_doctypes` in `hooks.py`: Bond
  Portfolio, Bond Transaction, Bond Statement, Bond Master, Bond Market Date,
  Bond Exchange Rate and Bond Exchange Rate Source.
- No role has the `share` permission on a financial DocType.
- A DocShare of a financial document, or of a File attached to one, is
  rejected for every user, Administrator and server callers included
  (`utils/investor_shares.py:reject_financial_share`).
- Attachments are unaffected. When a File becomes attached to a financial
  document, its existing shares are deleted in the same save.
- The registered patch `remove_financial_document_shares` deletes existing
  shares of financial documents and their Files; it is safe to rerun.
- Investor list queries fail closed when the investor holds any share of a
  portfolio-scoped DocType or of a File attached to a financial document.
- Investors have no access to Bond Exchange Rate Source.

## Consequences

- Desk "Assign To" a user without access to a financial document fails
  instead of sharing the document with the assignee.
- Managers grant access through roles and portfolio User Permissions only.
- The share-race harness, lock ordering and deferred share cleanup are gone.
  Reintroducing shares would need a new record and a consistency design.
