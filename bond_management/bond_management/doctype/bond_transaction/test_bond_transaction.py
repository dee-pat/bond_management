# Copyright (c) 2026, Deepak Patel and Contributors
# See license.txt

import frappe
from frappe.exceptions import ValidationError
from frappe.tests import IntegrationTestCase

from bond_management.bond_management.tests.factories import (
    make_bond,
    make_portfolio,
    make_transaction,
    unique_name,
)


class TestBondTransaction(IntegrationTestCase):
    def test_calculates_transaction_amounts(self):
        transaction = make_transaction(make_bond(), make_portfolio())

        self.assertEqual(transaction.principal, 1000)
        self.assertEqual(transaction.commission_amount, 20)
        self.assertEqual(transaction.settlement_amount, 1051)

    def test_rejects_sale_larger_than_position(self):
        bond = make_bond()
        portfolio = make_portfolio()
        make_transaction(bond, portfolio)

        sale = frappe.get_doc(
            {
                "doctype": "Bond Transaction",
                "transaction_reference": unique_name("TEST-SALE"),
                "trade_date": "2025-12-30",
                "settlement_date": "2025-12-31",
                "isin": bond.name,
                "portfolio_name": portfolio.name,
                "transaction_type": "Sale",
                "quantity_face_value": 11,
                "price": 105,
                "accrued_interest_paid": 0,
                "commission": 0,
                "face_value_per_unit": bond.face_value_per_unit,
                "currency": bond.currency,
                "issue_date": bond.issue_date,
                "maturity_date": bond.maturity_date,
            }
        )

        self.assertRaises(ValidationError, sale.insert)
