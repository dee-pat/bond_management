"""Superseded by remove_financial_document_shares; kept registered so reruns stay valid."""

from bond_management.bond_management.utils.investor_shares import delete_financial_shares


def execute():
    delete_financial_shares()
