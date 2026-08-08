from decimal import Decimal

import frappe
from frappe.tests import IntegrationTestCase

from bond_management.bond_management.tests.factories import make_exchange_rate, make_portfolio
from bond_management.patches.add_bond_query_indexes import EXCHANGE_RATE_UNIQUE
from bond_management.patches.backfill_bond_exchange_reverse_rates import (
    execute as backfill_reverse_rates,
)


class TestBondExchangeRate(IntegrationTestCase):
    def test_manual_rate_is_stored_as_source_to_usd(self):
        portfolio = make_portfolio()
        rate = make_exchange_rate(portfolio)

        self.assertEqual(rate.to_currency, "USD")
        self.assertEqual(rate.source, "Manual")
        self.assertEqual(Decimal(str(rate.rate)), Decimal("0.00772499"))
        self.assertAlmostEqual(
            Decimal(str(rate.reverse_rate)),
            Decimal(1) / Decimal("0.00772499"),
            places=12,
        )

    def test_reverse_rate_can_be_used_as_manual_input(self):
        portfolio = make_portfolio()
        rate = make_exchange_rate(
            portfolio,
            rate=None,
            reverse_rate="129.45",
        )

        self.assertAlmostEqual(
            Decimal(str(rate.rate)),
            Decimal(1) / Decimal("129.45"),
            places=12,
        )
        self.assertEqual(Decimal(str(rate.reverse_rate)), Decimal("129.45"))

    def test_changing_reverse_rate_updates_canonical_rate(self):
        portfolio = make_portfolio()
        rate = make_exchange_rate(portfolio)

        rate.reverse_rate = "130"
        rate.save()
        rate.reload()

        self.assertAlmostEqual(
            Decimal(str(rate.rate)),
            Decimal(1) / Decimal("130"),
            places=12,
        )
        self.assertEqual(Decimal(str(rate.reverse_rate)), Decimal("130"))

    def test_reverse_rate_backfill_is_idempotent(self):
        portfolio = make_portfolio()
        rate = make_exchange_rate(portfolio)
        frappe.db.set_value(
            "Bond Exchange Rate",
            rate.name,
            "reverse_rate",
            0,
            update_modified=False,
        )

        backfill_reverse_rates()
        rate.reload()
        expected_reverse_rate = Decimal(1) / Decimal("0.00772499")
        self.assertAlmostEqual(Decimal(str(rate.reverse_rate)), expected_reverse_rate, places=12)

        backfill_reverse_rates()
        rate.reload()
        self.assertAlmostEqual(Decimal(str(rate.reverse_rate)), expected_reverse_rate, places=12)

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
            ({"rate": None, "reverse_rate": 0}, "Reverse Rate must be greater than zero"),
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
