# Copyright (c) 2026, Deepak Patel and Contributors
# See license.txt

import frappe
from frappe.tests import IntegrationTestCase

from bond_management.bond_management.tests.factories import make_bond, make_market_date


class TestBondMarketPrices(IntegrationTestCase):
    def test_market_price_rows_receive_bond_derived_values(self):
        bond = make_bond()
        market_price = make_market_date(bond).bond_market_prices[-1]

        self.assertEqual(market_price.parenttype, "Bond Market Date")
        self.assertEqual(market_price.currency, "USD")
        self.assertEqual(market_price.maturity_date, bond.maturity_date)
        self.assertEqual(market_price.weighted_avg_repayment_date, bond.maturity_date)
        self.assertIsNotNone(market_price.weighted_avg_repayment_years)

    def test_market_price_field_documents_bank_quote_convention(self):
        description = frappe.get_meta("Bond Market Prices").get_field("market_price").description

        self.assertIn("original full unit", description)
        self.assertIn("50% principal remaining", description)

    def test_replaces_copy_button_with_weighted_repayment_fields(self):
        meta = frappe.get_meta("Bond Market Prices")

        self.assertIsNone(meta.get_field("copy_cashflows"))
        self.assertEqual(meta.get_field("weighted_avg_repayment_date").fieldtype, "Date")
        self.assertTrue(meta.get_field("weighted_avg_repayment_years").hidden)
