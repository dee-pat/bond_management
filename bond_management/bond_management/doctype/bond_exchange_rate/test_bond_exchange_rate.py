from decimal import Decimal
from types import SimpleNamespace

import frappe
from frappe.tests import IntegrationTestCase

from bond_management.bond_management.tests.factories import make_exchange_rate, make_portfolio, make_statement
from bond_management.bond_management.utils.statement_exchange_rates import (
    SOURCE_DOCTYPE,
    sync_statement_exchange_rates,
)
from bond_management.patches.add_bond_query_indexes import (
    EXCHANGE_RATE_SOURCE_EXCHANGE_RATE_INDEX,
    EXCHANGE_RATE_SOURCE_STATEMENT_INDEX,
    EXCHANGE_RATE_UNIQUE,
)
from bond_management.patches.backfill_bond_exchange_reverse_rates import (
    execute as backfill_reverse_rates,
)


class TestBondExchangeRate(IntegrationTestCase):
    def test_identical_high_precision_statement_rates_share_the_stored_rate(self):
        rate = Decimal("1.1234567890123")
        first = make_statement(make_portfolio(), statement_date="2091-04-03")
        second = make_statement(make_portfolio(), statement_date=first.statement_date)
        parsed_rate = SimpleNamespace(from_currency="EUR", to_currency="USD", rate=rate)

        sync_statement_exchange_rates(first, [parsed_rate])
        sync_statement_exchange_rates(second, [parsed_rate])

        sources = frappe.qb.get_query(
            SOURCE_DOCTYPE,
            fields=["exchange_rate", "rate", "reverse_rate"],
            filters={"statement": ["in", [first.name, second.name]]},
            ignore_permissions=True,
        ).run(as_dict=True)
        self.assertEqual(len(sources), 2)
        self.assertEqual(len({source.exchange_rate for source in sources}), 1)
        self.assertTrue(all(Decimal(str(source.rate)) == Decimal("1.123456789012") for source in sources))
        canonical = frappe.get_doc("Bond Exchange Rate", sources[0].exchange_rate)
        self.assertEqual(Decimal(str(canonical.rate)), Decimal("1.123456789012"))
        self.assertEqual(sources[0].reverse_rate, sources[1].reverse_rate)

    def test_high_precision_statement_rates_conflict_at_stored_precision(self):
        first = make_statement(make_portfolio(), statement_date="2091-04-04")
        second = make_statement(make_portfolio(), statement_date=first.statement_date)
        sync_statement_exchange_rates(
            first,
            [SimpleNamespace(from_currency="EUR", to_currency="USD", rate=Decimal("1.1234567890123"))],
        )

        with self.assertRaisesRegex(frappe.ValidationError, "conflicts"):
            sync_statement_exchange_rates(
                second,
                [
                    SimpleNamespace(
                        from_currency="EUR",
                        to_currency="USD",
                        rate=Decimal("1.1234567890125"),
                    )
                ],
            )

        self.assertFalse(frappe.db.exists(SOURCE_DOCTYPE, {"statement": second.name}))
        canonical_rate = frappe.db.get_value(
            "Bond Exchange Rate",
            {"rate_date": first.statement_date, "from_currency": "EUR", "to_currency": "USD"},
            "rate",
        )
        self.assertEqual(Decimal(str(canonical_rate)), Decimal("1.123456789012"))

    def test_high_precision_statement_rate_matches_stored_manual_fallback(self):
        manual = make_exchange_rate(from_currency="EUR", rate="1.1234567890123", rate_date="2091-04-05")
        statement = make_statement(make_portfolio(), statement_date=manual.rate_date)

        sync_statement_exchange_rates(
            statement,
            [SimpleNamespace(from_currency="EUR", to_currency="USD", rate=Decimal("1.1234567890123"))],
        )

        manual.reload()
        self.assertEqual(Decimal(str(manual.rate)), Decimal("1.123456789012"))
        self.assertEqual(manual.manual_fallback, 1)
        self.assertEqual(manual.source, "Statement PDF")

    def test_statement_rate_rounds_half_up_at_storage_precision(self):
        statement = make_statement(make_portfolio(), statement_date="2091-04-06")
        sync_statement_exchange_rates(
            statement,
            [SimpleNamespace(from_currency="EUR", to_currency="USD", rate=Decimal("1.1234567890125"))],
        )

        source_rate = frappe.db.get_value(SOURCE_DOCTYPE, {"statement": statement.name}, "rate")
        self.assertEqual(Decimal(str(source_rate)), Decimal("1.123456789013"))

    def test_statement_rate_below_storage_precision_is_rejected(self):
        statement = make_statement(make_portfolio(), statement_date="2091-04-07")

        with self.assertRaisesRegex(frappe.ValidationError, "too small to store"):
            sync_statement_exchange_rates(
                statement,
                [
                    SimpleNamespace(
                        from_currency="EUR",
                        to_currency="USD",
                        rate=Decimal("0.0000000000004"),
                    )
                ],
            )

        self.assertFalse(frappe.db.exists(SOURCE_DOCTYPE, {"statement": statement.name}))

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
