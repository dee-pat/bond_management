from decimal import Decimal
from types import SimpleNamespace

import frappe
from frappe.tests import IntegrationTestCase

from bond_management.bond_management.tests.factories import make_exchange_rate, make_portfolio, make_statement
from bond_management.bond_management.utils.statement_exchange_rates import sync_statement_exchange_rates
from bond_management.patches.add_bond_query_indexes import (
    EXCHANGE_RATE_SOURCE_EXCHANGE_RATE_INDEX,
    EXCHANGE_RATE_SOURCE_STATEMENT_INDEX,
    EXCHANGE_RATE_UNIQUE,
)
from bond_management.patches.backfill_bond_exchange_reverse_rates import (
    execute as backfill_reverse_rates,
)


class TestBondExchangeRate(IntegrationTestCase):
    def test_statement_derived_rate_cannot_be_changed_or_deleted_directly(self):
        exchange_rate = make_exchange_rate()
        statement = make_statement(make_portfolio(), statement_date=exchange_rate.rate_date)
        sync_statement_exchange_rates(
            statement,
            [
                SimpleNamespace(
                    from_currency=exchange_rate.from_currency,
                    to_currency=exchange_rate.to_currency,
                    rate=exchange_rate.rate,
                )
            ],
        )
        exchange_rate.reload()

        exchange_rate.rate = "0.00800000"
        with self.assertRaisesRegex(frappe.ValidationError, "managed from the source PDF"):
            exchange_rate.save()

        with self.assertRaisesRegex(frappe.ValidationError, "derived from"):
            exchange_rate.delete()

        self.assertTrue(
            frappe.db.has_index(
                "tabBond Exchange Rate Source",
                EXCHANGE_RATE_SOURCE_EXCHANGE_RATE_INDEX,
            )
        )
        self.assertTrue(
            frappe.db.has_index(
                "tabBond Exchange Rate Source",
                EXCHANGE_RATE_SOURCE_STATEMENT_INDEX,
            )
        )

    def test_statement_derived_rate_cannot_be_reassigned_to_another_currency(self):
        exchange_rate = make_exchange_rate()
        statement = make_statement(make_portfolio(), statement_date=exchange_rate.rate_date)
        sync_statement_exchange_rates(
            statement,
            [
                SimpleNamespace(
                    from_currency=exchange_rate.from_currency,
                    to_currency=exchange_rate.to_currency,
                    rate=exchange_rate.rate,
                )
            ],
        )
        exchange_rate.reload()

        exchange_rate.from_currency = "EUR"
        with self.assertRaisesRegex(frappe.ValidationError, "managed from the source PDF"):
            exchange_rate.save()

        exchange_rate.reload()
        self.assertEqual(exchange_rate.from_currency, "KES")

    def test_statement_derived_rate_preserves_stored_manual_fallback(self):
        statement = make_statement(make_portfolio(), statement_date="2025-12-30")
        sync_statement_exchange_rates(
            statement,
            [SimpleNamespace(from_currency="EUR", to_currency="USD", rate="0.91")],
        )
        derived_name = frappe.db.get_value(
            "Bond Exchange Rate",
            {
                "rate_date": statement.statement_date,
                "from_currency": "EUR",
                "to_currency": "USD",
            },
            "name",
        )
        derived_rate = frappe.get_doc("Bond Exchange Rate", derived_name)
        self.assertEqual(derived_rate.manual_fallback, 0)

        derived_rate.manual_fallback = 1
        derived_rate.save()
        derived_rate.reload()
        self.assertEqual(derived_rate.manual_fallback, 0)

        fallback_rate = make_exchange_rate()
        fallback_statement = make_statement(make_portfolio(), statement_date=fallback_rate.rate_date)
        sync_statement_exchange_rates(
            fallback_statement,
            [
                SimpleNamespace(
                    from_currency=fallback_rate.from_currency,
                    to_currency=fallback_rate.to_currency,
                    rate=fallback_rate.rate,
                )
            ],
        )
        fallback_rate.reload()
        self.assertEqual(fallback_rate.manual_fallback, 1)

        fallback_rate.manual_fallback = 0
        fallback_rate.save()
        fallback_rate.reload()
        self.assertEqual(fallback_rate.manual_fallback, 1)

    def test_manual_rate_is_stored_as_source_to_usd(self):
        rate = make_exchange_rate()

        self.assertEqual(rate.to_currency, "USD")
        self.assertEqual(rate.source, "Manual")
        self.assertEqual(Decimal(str(rate.rate)), Decimal("0.00772499"))
        self.assertAlmostEqual(
            Decimal(str(rate.reverse_rate)),
            Decimal(1) / Decimal("0.00772499"),
            places=12,
        )

    def test_reverse_rate_can_be_used_as_manual_input(self):
        rate = make_exchange_rate(
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
        rate = make_exchange_rate()

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
        rate = make_exchange_rate()
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
        rate = make_exchange_rate()

        duplicate = frappe.get_doc(
            {
                "doctype": "Bond Exchange Rate",
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
                "rate_date": rate.rate_date,
                "from_currency": rate.from_currency,
                "to_currency": "USD",
                "rate": "0.0078",
            }
        )
        with self.assertRaises(frappe.UniqueValidationError):
            database_duplicate.db_insert()

    def test_rejects_non_positive_and_usd_rates(self):
        for values, message in (
            ({"rate": 0}, "greater than zero"),
            ({"rate": None, "reverse_rate": 0}, "Reverse Rate must be greater than zero"),
            ({"from_currency": "USD"}, "not required"),
        ):
            with self.subTest(values=values):
                rate = frappe.get_doc(
                    {
                        "doctype": "Bond Exchange Rate",
                        "rate_date": "2025-12-30",
                        "from_currency": "KES",
                        "rate": "0.0077",
                        **values,
                    }
                )
                with self.assertRaisesRegex(frappe.ValidationError, message):
                    rate.insert()

    def test_portfolio_is_not_part_of_exchange_rate_metadata(self):
        self.assertIsNone(frappe.get_meta("Bond Exchange Rate").get_field("portfolio_name"))
