# Copyright (c) 2026, Deepak Patel and Contributors
# See license.txt

import frappe
from frappe.tests import IntegrationTestCase

from bond_management.bond_management.tests.factories import (
    make_bond,
    make_market_date,
    make_portfolio,
    make_transaction,
)


class TestBondStatementDetails(IntegrationTestCase):
    def test_statement_details_are_created_as_statement_children(self):
        bond = make_bond()
        portfolio = make_portfolio()
        make_transaction(bond, portfolio)
        make_market_date(bond)
        statement = frappe.get_doc(
            {
                "doctype": "Bond Statement",
                "portfolio_name": portfolio.name,
                "statement_date": "2025-12-31",
            }
        ).insert()

        detail = statement.bond_statement_details[0]
        self.assertEqual(detail.parent, statement.name)
        self.assertEqual(detail.parenttype, "Bond Statement")
        self.assertEqual(detail.parentfield, "bond_statement_details")
