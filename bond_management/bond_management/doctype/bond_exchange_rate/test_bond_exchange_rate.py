from decimal import Decimal

import frappe
from frappe.tests import IntegrationTestCase

from bond_management.bond_management.tests.factories import make_exchange_rate, make_portfolio
from bond_management.patches.add_bond_query_indexes import EXCHANGE_RATE_UNIQUE


class TestBondExchangeRate(IntegrationTestCase):
    def test_manual_rate_is_stored_as_source_to_usd(self):
        portfolio = make_portfolio()
        rate = make_exchange_rate(portfolio)

        self.assertEqual(rate.to_currency, "USD")
        self.assertEqual(rate.source, "Manual")
        self.assertEqual(Decimal(str(rate.rate)), Decimal("0.00772499"))

    def test_rejects_duplicate_rows_at_document_and_database_boundaries(self):
        portfolio = make_portfolio()
        rate = make_exchange_rate(portfolio)

        duplicate = frappe.get_doc(
            {
                "doctype": "Bond Exchange Rate",
                "portfolio_name": portfolio.name,
                "rate_date": rate.rate_date,
                "from_currency": rate.from_currency,
                "to_currency": "USD",
                "rate": "0.0078",
            }
        )
        with self.assertRaisesRegex(frappe.UniqueValidationError, "already exists"):
            duplicate.insert()

        self.assertTrue(frappe.db.has_index("tabBond Exchange Rate", EXCHANGE_RATE_UNIQUE))
        database_duplicate = frappe.get_doc(
            {
                "doctype": "Bond Exchange Rate",
                "portfolio_name": portfolio.name,
                "rate_date": rate.rate_date,
                "from_currency": rate.from_currency,
                "to_currency": "USD",
                "rate": "0.0078",
            }
        )
        with self.assertRaises(frappe.UniqueValidationError):
            database_duplicate.db_insert()

    def test_rejects_non_positive_and_usd_rates(self):
        portfolio = make_portfolio()
        for values, message in (
            ({"rate": 0}, "greater than zero"),
            ({"from_currency": "USD"}, "not required"),
        ):
            with self.subTest(values=values):
                rate = frappe.get_doc(
                    {
                        "doctype": "Bond Exchange Rate",
                        "portfolio_name": portfolio.name,
                        "rate_date": "2025-12-30",
                        "from_currency": "KES",
                        "rate": "0.0077",
                        **values,
                    }
                )
                with self.assertRaisesRegex(frappe.ValidationError, message):
                    rate.insert()
