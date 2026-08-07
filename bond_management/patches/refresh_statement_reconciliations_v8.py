from bond_management.patches.backfill_statement_reconciliation_statuses import (
    execute as refresh_reconciliations,
)


def execute(statement_names=None):
    """Run the v8 reconciliation refresh under a new Patch Log identity."""
    refresh_reconciliations(statement_names)
