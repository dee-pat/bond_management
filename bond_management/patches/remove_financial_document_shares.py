"""Delete existing shares of financial documents and their Files (decision 0012)."""

from bond_management.bond_management.utils.investor_shares import delete_financial_shares


def execute():
    delete_financial_shares()
