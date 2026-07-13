# Copyright (c) 2026, Deepak Patel and Contributors
# See license.txt

import frappe
from frappe.tests import IntegrationTestCase

from bond_management.bond_management.doctype.bond_market_date.bond_market_date import (
    get_cashflows,
    get_recalculated_market_data,
)
from bond_management.bond_management.tests.factories import make_bond, make_market_date
from bond_management.bond_management.utils.performance import get_market_price


class TestBondMarketDate(IntegrationTestCase):
    def test_updates_market_price_derived_fields_and_cashflows(self):
        bond = make_bond()
        market_date = make_market_date(bond, date="2025-12-29")
        price_row = market_date.bond_market_prices[0]

        self.assertEqual(price_row.maturity_date, bond.maturity_date)
        self.assertEqual(price_row.principal_factor, 1)
        self.assertIsNotNone(price_row.future_xirr)

        cashflows = get_cashflows(market_date.date, bond.name, 100)
        self.assertGreater(len(cashflows), 2)
        self.assertEqual(cashflows[0]["type"], "market_price")

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
                "maturity_date": None,
            },
        )
        self.assertIsNotNone(result[1]["maturity_date"])
        self.assertIsNone(result[1]["principal_factor"])
        self.assertIsNone(result[1]["future_xirr"])

    def test_market_price_must_be_greater_than_zero(self):
        bond = make_bond()

        for invalid_price in (-1, 0):
            with self.subTest(market_price=invalid_price):
                with self.assertRaisesRegex(frappe.ValidationError, "must be greater than zero"):
                    make_market_date(bond, market_price=invalid_price, date="2025-12-27")

        self.assertEqual(
            make_market_date(bond, market_price=0.01, date="2025-12-27").bond_market_prices[0].market_price,
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

    def test_market_price_lookup_uses_latest_price_on_or_before_date(self):
        bond = make_bond()
        frappe.get_doc(
            {
                "doctype": "Bond Market Date",
                "date": "2025-06-29",
                "bond_market_prices": [{"isin": bond.name, "market_price": 90}],
            }
        ).insert()
        frappe.get_doc(
            {
                "doctype": "Bond Market Date",
                "date": "2025-12-26",
                "bond_market_prices": [{"isin": bond.name, "market_price": 100}],
            }
        ).insert()

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
        price_row = market_date.bond_market_prices[0]

        self.assertEqual(price_row.principal_factor, 0.5)
        self.assertEqual(get_cashflows(market_date.date, bond.name, 50)[0]["amount"], -50)
