# PR 18 review: scope exchange-rate provenance shares

## User outcome

An investor can read a `Bond Exchange Rate Source` row only when its linked
statement belongs to an assigned portfolio, even when the row is explicitly
shared.

## Root cause and change

The investor share allowlist omitted this standalone DocType. Add it to the
share validation, repair, and document permission hooks, and derive its
portfolio through the linked statement. Keep Desk list queries limited to
explicitly shared source rows, and repair legacy shares during migration,
fresh installation, statement portfolio changes, and assignment updates.

## Regression coverage

Verify assigned source shares remain readable, unassigned and global shares are
rejected, unshared rows stay hidden, legacy shares cannot expose rows through
direct or list reads, and cleanup removes those legacy shares idempotently.
