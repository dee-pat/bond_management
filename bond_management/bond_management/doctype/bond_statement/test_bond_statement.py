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


class TestBondStatement(IntegrationTestCase):
    def test_populates_holdings_from_portfolio_position(self):
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

        self.assertEqual(len(statement.bond_statement_details), 1)
        detail = statement.bond_statement_details[0]
        self.assertEqual(detail.isin, bond.name)
        self.assertEqual(detail.quantity, 10)
        self.assertEqual(detail.market_price, 100)

    def test_missing_market_price_is_blank_instead_of_zero(self):
        bond = make_bond()
        portfolio = make_portfolio()
        make_transaction(bond, portfolio)

        statement = frappe.get_doc(
            {
                "doctype": "Bond Statement",
                "portfolio_name": portfolio.name,
                "statement_date": "2025-12-31",
            }
        ).insert()

        self.assertIsNone(statement.bond_statement_details[0].market_price)

    def test_clearing_an_input_clears_previously_generated_rows(self):
        statement = frappe.get_doc(
            {
                "doctype": "Bond Statement",
                "portfolio_name": make_portfolio().name,
                "statement_date": "2025-12-31",
                "bond_statement_details": [{"isin": make_bond().name, "quantity": 10, "market_price": 100}],
            }
        )

        statement.portfolio_name = None
        statement.populate_holdings()

        self.assertEqual(statement.bond_statement_details, [])

    def test_portfolio_and_statement_date_are_required(self):
        with self.assertRaises(frappe.MandatoryError):
            frappe.get_doc({"doctype": "Bond Statement", "statement_date": "2025-12-31"}).insert()

        with self.assertRaises(frappe.MandatoryError):
            frappe.get_doc({"doctype": "Bond Statement", "portfolio_name": make_portfolio().name}).insert()
