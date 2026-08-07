# Copyright (c) 2026, Deepak Patel and Contributors
# See license.txt

from decimal import ROUND_HALF_UP, Decimal

import frappe
from frappe.exceptions import FrappeTypeError
from frappe.tests import IntegrationTestCase

from bond_management.bond_management.doctype.bond_market_date.bond_market_date import (
    get_cashflows,
    get_recalculated_market_data,
)
from bond_management.bond_management.tests.factories import make_bond, make_market_date
from bond_management.bond_management.utils.performance import get_market_price
from bond_management.bond_management.utils.xirr import calculate_future_xirr
from bond_management.patches.add_bond_query_indexes import (
    LEDGER_INDEX,
    MARKET_DATE_UNIQUE,
    REPORT_INDEX,
    STATEMENT_ATTACHMENT_UNIQUE,
)
from bond_management.patches.add_bond_query_indexes import (
    execute as add_bond_query_indexes,
)
from bond_management.patches.backfill_kenya_quantity_change_market_data import (
    execute as backfill_kenya_quantity_change_market_data,
)
from bond_management.patches.backfill_weighted_avg_repayment import execute as backfill_weighted_repayment


class TestBondMarketDate(IntegrationTestCase):
    def test_updates_market_price_derived_fields_and_cashflows(self):
        bond = make_bond()
        market_date = make_market_date(bond, date="2025-12-29")
        price_row = market_date.bond_market_prices[-1]

        self.assertEqual(price_row.maturity_date, bond.maturity_date)
        self.assertEqual(price_row.principal_factor, 1)
        self.assertEqual(price_row.weighted_avg_repayment_date, bond.maturity_date)
        self.assertEqual(price_row.weighted_avg_repayment_years, Decimal(368) / Decimal(365))
        self.assertIsNotNone(price_row.future_xirr)

        cashflows = get_cashflows(market_date.date, bond.name, "100")
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

    def test_backfill_patch_updates_existing_market_price_rows(self):
        bond = make_bond(
            principal_schedule=[
                {"repayment_date": "2026-01-01", "principal_units": 20},
                {"repayment_date": "2027-01-01", "principal_units": 80},
            ]
        )
        market_date = make_market_date(bond, date="2025-02-04")
        price_row = market_date.bond_market_prices[-1]
        frappe.db.set_value(
            "Bond Market Prices",
            price_row.name,
            {
                "weighted_avg_repayment_date": None,
                "weighted_avg_repayment_years": 0,
            },
            update_modified=False,
        )

        backfill_weighted_repayment()
        market_date.reload()
        price_row = market_date.bond_market_prices[-1]

        self.assertEqual(price_row.weighted_avg_repayment_date.isoformat(), "2026-10-20")
        expected_years = (Decimal(623) / Decimal(365)).quantize(
            Decimal("0.000000001"), rounding=ROUND_HALF_UP
        )
        self.assertEqual(Decimal(str(price_row.weighted_avg_repayment_years)), expected_years)

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

        make_market_date(bond, date="2025-12-25")
        with self.assertRaises(frappe.UniqueValidationError):
            frappe.get_doc(
                {
                    "doctype": "Bond Market Date",
                    "date": "2025-12-25",
                    "bond_market_prices": [{"isin": make_bond().name, "market_price": 100}],
                }
            ).insert()

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
        make_market_date(bond, market_price=90, date="2025-06-29")
        make_market_date(bond, market_price=100, date="2025-12-26")

        self.assertIsNone(get_market_price(bond.name, "2025-06-28"))
        self.assertEqual(get_market_price(bond.name, "2025-06-29"), 90)
        self.assertEqual(get_market_price(bond.name, "2026-01-01"), 100)

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
        self.assertEqual(get_cashflows(market_date.date, bond.name, 50)[0]["amount"], -50)

    def test_kenya_market_data_backfill_is_idempotent(self):
        bond = make_bond(
            currency="KES",
            day_count_convention="Actual/364(Kenya)",
            principal_schedule=[
                {"repayment_date": "2025-07-04", "principal_units": 50},
                {"repayment_date": "2027-01-01", "principal_units": 50},
            ],
        )
        market_date = make_market_date(bond, market_price=103.248, date="2025-07-05")
        price_row = market_date.bond_market_prices[-1]

        frappe.db.set_value(
            "Bond Market Prices",
            price_row.name,
            {"principal_factor": 0.5, "future_xirr": -18.771252834},
            update_modified=False,
        )
        expected_future_xirr = calculate_future_xirr(bond.name, market_date.date, 103.248) * 100

        backfill_kenya_quantity_change_market_data([bond.name])
        price_row.reload()
        self.assertEqual(price_row.market_price, 103.248)
        self.assertEqual(price_row.principal_factor, 1)
        self.assertEqual(price_row.future_xirr, round(expected_future_xirr, 9))

        backfill_kenya_quantity_change_market_data([bond.name])
        price_row.reload()
        self.assertEqual(price_row.principal_factor, 1)
        self.assertEqual(price_row.future_xirr, round(expected_future_xirr, 9))
