from bond_management.patches.access import MANAGER_ROLE, ensure_report_role


def execute():
    """Allow the app manager role to run the Portfolio Performance report."""
    ensure_report_role("Portfolio Performance", MANAGER_ROLE)
