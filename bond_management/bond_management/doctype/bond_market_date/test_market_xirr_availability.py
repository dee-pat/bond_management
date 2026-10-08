from decimal import Decimal

import frappe
from frappe.tests import IntegrationTestCase
from frappe.utils import getdate

from bond_management.bond_management.doctype.bond_market_date.bond_market_date import (
    get_recalculated_market_data,
)
from bond_management.bond_management.tests.factories import make_bond, make_market_date


class TestMarketXirrAvailability(IntegrationTestCase):
    def test_persisted_solver_distinguishes_unavailable_zero_positive_and_negative(self):
        matured = make_market_date(make_bond(coupon_rate=0), date="2027-01-02")
        matured.reload()
        self.assertEqual(matured.bond_market_prices[0].future_xirr_available, 0)
        # Frappe's numeric storage represents the unavailable result as zero.
        self.assertEqual(matured.bond_market_prices[0].future_xirr, 0)

        snapshot = None
        for price in (100, 90, 110):
            with self.subTest(price=price):
                bond = make_bond(coupon_rate=0)
                snapshot = (
                    make_market_date(bond, price, date="2025-11-19")
                    if snapshot is None
                    else make_market_date(bond, price, market_date=snapshot)
                )
                snapshot.reload()
                row = next(row for row in snapshot.bond_market_prices if row.isin == bond.name)
                days = (getdate(bond.maturity_date) - getdate(snapshot.date)).days
                expected = ((Decimal(100) / Decimal(price)) ** (Decimal(365) / Decimal(days)) - 1) * 100
                self.assertEqual(row.future_xirr_available, 1)
                self.assertAlmostEqual(row.future_xirr, float(expected), places=7)
                if price == 100:
                    self.assertEqual(row.future_xirr, 0)
                elif price < 100:
                    self.assertGreater(row.future_xirr, 0)
                else:
                    self.assertLess(row.future_xirr, 0)

    def test_save_overwrites_client_yield_and_availability(self):
        for quote_date, expected_available in (("2025-11-20", 1), ("2027-01-03", 0)):
            with self.subTest(quote_date=quote_date):
                snapshot = make_market_date(make_bond(coupon_rate=0), date=quote_date)
                row = snapshot.bond_market_prices[0]
                row.future_xirr = 99
                row.future_xirr_available = 1 - expected_available
                snapshot.save()
                snapshot.reload()
                self.assertEqual(snapshot.bond_market_prices[0].future_xirr, 0)
                self.assertEqual(snapshot.bond_market_prices[0].future_xirr_available, expected_available)

    def test_recalculation_returns_server_availability_and_ignores_client_override(self):
        bond = make_bond(coupon_rate=0)
        for quote_date, expected_available, expected_yield in (
            ("2025-11-21", 1, 0),
            ("2027-01-04", 0, None),
        ):
            with self.subTest(quote_date=quote_date):
                result = get_recalculated_market_data(
                    quote_date,
                    [
                        {
                            "name": "client-row",
                            "isin": bond.name,
                            "market_price": 100,
                            "future_xirr": 99,
                            "future_xirr_available": 1 - expected_available,
                        }
                    ],
                )[0]
                self.assertEqual(result["future_xirr_available"], expected_available)
                self.assertEqual(result["future_xirr"], expected_yield)
