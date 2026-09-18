from types import SimpleNamespace

import frappe
from frappe.tests import IntegrationTestCase

from bond_management.bond_management.tests.factories import (
    make_exchange_rate,
    make_portfolio,
    make_statement,
)
from bond_management.bond_management.utils.statement_exchange_rates import (
    SOURCE_DOCTYPE,
    build_source_key,
    sync_statement_exchange_rates,
)
from bond_management.patches.add_bond_exchange_rate_provenance import (
    execute as backfill_exchange_rate_provenance,
)


class TestBondExchangeRateProvenance(IntegrationTestCase):
    def test_rerun_preserves_manual_fallback_for_existing_provenance(self):
        portfolio = make_portfolio()
        statement = make_statement(portfolio, statement_date="2025-12-31")
        exchange_rate = make_exchange_rate(rate_date=statement.statement_date)
        sync_statement_exchange_rates(
            statement,
            [
                SimpleNamespace(
                    from_currency=exchange_rate.from_currency,
                    to_currency=exchange_rate.to_currency,
                    rate="0.00772499",
                )
            ],
        )
        exchange_rate.reload()

        source_key = build_source_key(exchange_rate.name, statement.name)
        source_name = frappe.db.get_value(SOURCE_DOCTYPE, {"source_key": source_key}, "name")
        self.assertTrue(source_name)
        self.assertEqual(exchange_rate.manual_fallback, 1)

        backfill_exchange_rate_provenance()
        backfill_exchange_rate_provenance()

        exchange_rate.reload()
        self.assertEqual(exchange_rate.manual_fallback, 1)
        self.assertEqual(exchange_rate.statement, statement.name)
        self.assertEqual(
            frappe.db.get_value(SOURCE_DOCTYPE, {"source_key": source_key}, "name"),
            source_name,
        )

        statement.delete()
        self.assertTrue(frappe.db.exists("Bond Exchange Rate", exchange_rate.name))

    def test_first_run_backfills_legacy_statement_provenance(self):
        portfolio = make_portfolio()
        statement = make_statement(portfolio, statement_date="2025-12-30")
        exchange_rate = make_exchange_rate(rate_date=statement.statement_date)
        frappe.db.set_value(
            "Bond Exchange Rate",
            exchange_rate.name,
            "statement",
            statement.name,
            update_modified=False,
        )
        frappe.db.set_value(
            "Bond Exchange Rate",
            exchange_rate.name,
            "manual_fallback",
            1,
            update_modified=False,
        )

        backfill_exchange_rate_provenance()

        source_key = build_source_key(exchange_rate.name, statement.name)
        self.assertTrue(frappe.db.exists(SOURCE_DOCTYPE, {"source_key": source_key}))
        self.assertEqual(
            frappe.db.get_value("Bond Exchange Rate", exchange_rate.name, "manual_fallback"),
            0,
        )
