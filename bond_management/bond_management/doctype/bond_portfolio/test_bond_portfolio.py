# Copyright (c) 2026, Deepak Patel and Contributors
# See license.txt

from frappe.tests import IntegrationTestCase

from bond_management.bond_management.tests.factories import make_portfolio


class TestBondPortfolio(IntegrationTestCase):
    def test_creates_portfolio_with_account_number(self):
        portfolio = make_portfolio()

        self.assertTrue(portfolio.name)
        self.assertEqual(portfolio.account_no, "TEST-ACCOUNT")
