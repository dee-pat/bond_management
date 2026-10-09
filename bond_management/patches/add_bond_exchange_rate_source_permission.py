"""Scope investor access to explicitly shared exchange-rate provenance rows."""

from bond_management.bond_management.utils.investor_shares import (
    SOURCE_DOCTYPE,
    cleanup_incompatible_shares,
)
from bond_management.patches.add_bond_investor_read_only_access import ensure_investor_read_only_docperm


def execute():
    ensure_investor_read_only_docperm(SOURCE_DOCTYPE)
    cleanup_incompatible_shares(doctype=SOURCE_DOCTYPE)


def ensure_permission():
    ensure_investor_read_only_docperm(SOURCE_DOCTYPE)
