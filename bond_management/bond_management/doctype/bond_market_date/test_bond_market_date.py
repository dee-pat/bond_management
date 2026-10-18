# Copyright (c) 2026, Deepak Patel and Contributors
# See license.txt

from datetime import date, timedelta
from decimal import Decimal
from unittest.mock import patch

import frappe
from frappe.exceptions import FrappeTypeError
from frappe.tests import IntegrationTestCase

from bond_management.bond_management.doctype.bond_market_date.bond_market_date import (
    get_cashflows,
    get_recalculated_market_data,
)
from bond_management.bond_management.tests.factories import make_bond, make_market_date
from bond_management.bond_management.utils.performance import get_latest_market_rows
from bond_management.patches.add_bond_query_indexes import (
    LEDGER_INDEX,
    MARKET_DATE_UNIQUE,
    REPORT_INDEX,
    STATEMENT_ATTACHMENT_UNIQUE,
)
from bond_management.patches.add_bond_query_indexes import (
    execute as add_bond_query_indexes,
)


class TestBondMarketDate(IntegrationTestCase):
    def test_batched_recalculation_does_not_repeat_missing_history_queries(self):
        bonds = [make_bond(), make_bond()]
        valuation_date = date(2095, 1, 1)
        while frappe.db.exists("Bond Market Date", {"date": valuation_date}):
            valuation_date -= timedelta(days=1)
        valuation_date_string = valuation_date.isoformat()
        rows = [
            {"name": f"market-row-{index}", "isin": bond.name, "market_price": 100}
            for index, bond in enumerate(bonds)
        ]

        with patch(
            "bond_management.bond_management.utils.xirr.get_last_xirr_guess",
            side_effect=AssertionError("batch lookup should avoid per-row history queries"),
        ) as get_last_xirr_guess:
            calculated_rows = get_recalculated_market_data(valuation_date_string, rows)
            market_date = frappe.get_doc(
                {
                    "doctype": "Bond Market Date",
                    "date": valuation_date,
                    "bond_market_prices": [{"isin": bond.name, "market_price": 100} for bond in bonds],
                }
            ).insert()

        get_last_xirr_guess.assert_not_called()
        self.assertEqual(len(calculated_rows), len(bonds))
        self.assertTrue(all(row["future_xirr_available"] == 0 for row in calculated_rows))
        self.assertTrue(all(row.future_xirr_available == 0 for row in market_date.bond_market_prices))

    def test_updates_market_price_derived_fields_and_cashflows(self):
        bond = make_bond()
        market_date = make_market_date(bond, date="2025-12-29")
        price_row = market_date.bond_market_prices[-1]

        self.assertEqual(price_row.maturity_date, bond.maturity_date)
        self.assertEqual(price_row.principal_factor, 1)
        self.assertEqual(price_row.weighted_avg_repayment_date, bond.maturity_date)
        self.assertEqual(price_row.weighted_avg_repayment_years, Decimal(368) / Decimal(365))
        self.assertIsNotNone(price_row.future_xirr)

        cashflows = get_cashflows(market_date.date.isoformat(), bond.name, "100")
        self.assertGreater(len(cashflows), 2)
        self.assertEqual(cashflows[0]["type"], "market_price")
        self.assertEqual(cashflows[0]["amount"], -100)

    def test_cashflow_endpoint_rejects_invalid_market_prices(self):
        bond = make_bond()

        for market_price in (None, "", "0", "-1"):
            with self.subTest(market_price=market_price):
                with self.assertRaisesRegex(frappe.ValidationError, "must be greater than zero"):
                    get_cashflows("2025-12-29", bond.name, market_price)

        with self.assertRaisesRegex(frappe.ValidationError, "Market Price must be a valid number"):
            get_cashflows("2025-12-29", bond.name, "not-a-number")
        with self.assertRaisesRegex(frappe.ValidationError, "Market Price must be a finite number"):
            get_cashflows("2025-12-29", bond.name, "NaN")

        with self.assertRaisesRegex(FrappeTypeError, "date.*str"):
            get_cashflows([], bond.name, "100")
        with self.assertRaisesRegex(FrappeTypeError, "isin.*str"):
            get_cashflows("2025-12-29", {}, "100")

    def test_value_endpoint_clears_stale_derived_fields_for_incomplete_rows(self):
        result = get_recalculated_market_data(
            "",
            [
                {"name": "row-without-isin", "isin": None, "market_price": 100},
                {
                    "name": "row-without-price",
                    "isin": make_bond().name,
                    "market_price": None,
                },
            ],
        )

        self.assertEqual(
            result[0],
            {
                "name": "row-without-isin",
                "currency": None,
                "future_xirr": None,
                "future_xirr_available": 0,
                "principal_factor": None,
                "weighted_avg_repayment_date": None,
                "weighted_avg_repayment_years": None,
                "maturity_date": None,
            },
        )
        self.assertIsNotNone(result[1]["maturity_date"])
        self.assertIsNone(result[1]["principal_factor"])
        self.assertIsNone(result[1]["future_xirr"])

    def test_value_endpoint_rejects_complex_boundary_values(self):
        with self.assertRaisesRegex(FrappeTypeError, "date.*str"):
            get_recalculated_market_data(date=[], rows=[])
        with self.assertRaisesRegex(frappe.ValidationError, "Row 1 name must be a string"):
            get_recalculated_market_data(rows=[{"name": [], "isin": None, "market_price": 100}])
        with self.assertRaisesRegex(frappe.ValidationError, "Row 1 ISIN must be a string"):
            get_recalculated_market_data(rows=[{"name": "row", "isin": {}, "market_price": 100}])

    def test_value_endpoint_allows_rows_before_parent_date(self):
        bond = make_bond()

        result = get_recalculated_market_data(
            rows=[{"name": "new-row", "isin": bond.name, "market_price": 100}],
        )

        self.assertEqual(result[0]["currency"], bond.currency)
        self.assertEqual(result[0]["maturity_date"], bond.maturity_date)
        self.assertIsNone(result[0]["principal_factor"])
        self.assertIsNone(result[0]["future_xirr"])

    def test_persists_remaining_principal_weighted_repayment_values(self):
        bond = make_bond(
            principal_schedule=[
                {"repayment_date": "2026-01-01", "principal_units": 20},
                {"repayment_date": "2027-01-01", "principal_units": 80},
            ]
        )

        price_row = make_market_date(bond, date="2025-02-03").bond_market_prices[-1]

        self.assertEqual(price_row.weighted_avg_repayment_date.isoformat(), "2026-10-20")
        self.assertEqual(price_row.weighted_avg_repayment_years, Decimal(624) / Decimal(365))

    def test_market_price_must_be_greater_than_zero(self):
        bond = make_bond()

        for invalid_price in (-1, 0):
            with self.subTest(market_price=invalid_price):
                with self.assertRaisesRegex(frappe.ValidationError, "must be greater than zero"):
                    make_market_date(bond, market_price=invalid_price, date="2025-12-27")

        self.assertEqual(
            make_market_date(bond, market_price=0.01, date="2025-12-27").bond_market_prices[-1].market_price,
            0.01,
        )

    def test_rejects_duplicate_isin_rows(self):
        bond = make_bond()
        with self.assertRaisesRegex(frappe.ValidationError, "appears more than once"):
            frappe.get_doc(
                {
                    "doctype": "Bond Market Date",
                    "date": "2025-12-28",
                    "bond_market_prices": [
                        {"isin": bond.name, "market_price": 99},
                        {"isin": bond.name, "market_price": 100},
                    ],
                }
            ).insert()

    def test_date_is_required_and_unique(self):
        bond = make_bond()
        with self.assertRaises(frappe.MandatoryError):
            frappe.get_doc(
                {
                    "doctype": "Bond Market Date",
                    "bond_market_prices": [{"isin": bond.name, "market_price": 100}],
                }
            ).insert()

        market_date = make_market_date(bond, date="2025-12-25")
        with self.assertRaises(frappe.UniqueValidationError):
            make_market_date(make_bond(), date=market_date.date)

    def test_database_indexes_enforce_market_dates_and_support_hot_queries(self):
        add_bond_query_indexes()
        add_bond_query_indexes()

        self.assertTrue(frappe.db.has_index("tabBond Transaction", LEDGER_INDEX))
        self.assertTrue(frappe.db.has_index("tabBond Transaction", REPORT_INDEX))
        self.assertTrue(frappe.db.has_index("tabBond Market Date", MARKET_DATE_UNIQUE))
        self.assertTrue(frappe.db.has_index("tabBond Statement", STATEMENT_ATTACHMENT_UNIQUE))

        bond = make_bond()
        market_date = make_market_date(bond, date="2025-12-23")
        duplicate = frappe.get_doc(
            {
                "doctype": "Bond Market Date",
                "date": market_date.date,
                "bond_market_prices": [{"isin": make_bond().name, "market_price": 100}],
            }
        )
        duplicate.flags.ignore_validate = True
        with self.assertRaises(frappe.UniqueValidationError):
            duplicate.insert()

    def test_market_price_lookup_uses_latest_price_on_or_before_date(self):
        bond = make_bond()
        early = make_market_date(bond, market_price=90, date="2025-06-29")
        late = make_market_date(bond, market_price=100, date="2025-12-26")

        def market_price(valuation_date):
            rows = get_latest_market_rows([bond.name], valuation_date)
            return rows[0].market_price if rows else None

        self.assertIsNone(market_price(early.date - timedelta(days=1)))
        self.assertEqual(market_price(early.date), 90)
        self.assertEqual(market_price(late.date + timedelta(days=1)), 100)

    def test_bank_quote_is_not_scaled_by_principal_factor_again(self):
        bond = make_bond(
            coupon_rate=0,
            principal_schedule=[
                {"repayment_date": "2025-07-01", "principal_units": 50},
                {"repayment_date": "2027-01-01", "principal_units": 50},
            ],
        )
        market_date = make_market_date(bond, market_price=50, date="2025-12-24")
        price_row = market_date.bond_market_prices[-1]

        self.assertEqual(price_row.principal_factor, 0.5)
        self.assertEqual(get_cashflows(market_date.date.isoformat(), bond.name, 50)[0]["amount"], -50)
