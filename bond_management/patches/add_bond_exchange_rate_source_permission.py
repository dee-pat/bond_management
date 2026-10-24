"""Superseded by decision 0012: investors have no Source access and Source rows are never shared."""

from bond_management.bond_management.utils.investor_shares import delete_financial_shares


def execute():
    delete_financial_shares()
