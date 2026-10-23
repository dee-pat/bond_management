# Sharing and yield chart simplification

Status: In progress on `chore/simplify-and-speed-up-tests`; PR pending.
Decision: [0012](../decisions/0012-financial-documents-are-never-shared.md).

## Goal

Remove code that exists only to keep DocShare grants consistent with investor
scope, remove investor access to exchange-rate provenance, and stop drawing the
Bond Yield Comparison chart twice.

## Non-goals

No change to portfolio scope, investor read projections, financial values,
attachments or the investor SPA's chart.

## Design

- Sharing: see decision 0012. `utils/investor_shares.py` keeps the investor
  read/write boundary (`InvestorBoundaryMixin`, `reject_investor_mutation`)
  and gains `reject_financial_share` and the File relink cleanup. Locking,
  deferred retries, assignment and role cleanup, the `clear_user_permissions`
  override and the share-race harness are removed.
- Exchange Rate Source: the investor DocPerm row leaves the DocType JSON;
  migrate removes it from deployed sites. The Source hooks deny investors.
- Bond Yield Comparison in Desk: filters, the standard report table and an
  "Open chart" button to `/bond-investor/yield-comparison`. The SPA keeps the
  only chart.

## Rollout and recovery

`remove_financial_document_shares` runs once on migrate and is safe to rerun.
Rolling back the code restores the old hooks; deleted shares are not restored,
and none are needed because roles and User Permissions grant all access.

## Acceptance

- Sharing a financial document or its attached File fails for every user,
  including Administrator; attaching files still works.
- Investors cannot read Exchange Rate Source rows.
- The Desk report shows its table and opens the SPA chart.
- `verify.sh pre-push-ui` and `verify.sh lifecycle` pass.
