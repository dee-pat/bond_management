# Copyright (c) 2026, Deepak Patel and Contributors
# See license.txt

from frappe.tests import IntegrationTestCase

from bond_management.bond_management.tests.factories import make_portfolio


class TestBondPortfolio(IntegrationTestCase):
    def test_creates_portfolio_with_account_number(self):
        portfolio = make_portfolio()

        self.assertTrue(portfolio.name)
        self.assertTrue(portfolio.account_no.startswith("TEST-ACCOUNT-"))
        self.assertEqual(portfolio.transaction_account_no, portfolio.account_no)
        self.assertEqual(portfolio.get_password("statement_pdf_password"), "test-password")

        meta = portfolio.meta
        self.assertTrue(meta.get_field("account_no").unique)
        self.assertTrue(meta.get_field("transaction_account_no").unique)
        self.assertEqual(meta.get_field("statement_pdf_password").fieldtype, "Password")
