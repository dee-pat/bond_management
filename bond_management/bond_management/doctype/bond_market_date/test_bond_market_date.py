# Copyright (c) 2026, Deepak Patel and Contributors
# See license.txt

from frappe.tests import IntegrationTestCase

from bond_management.bond_management.tests.factories import make_bond, make_market_date


class TestBondMarketDate(IntegrationTestCase):
    def test_updates_market_price_derived_fields_and_cashflows(self):
        bond = make_bond()
        market_date = make_market_date(bond)
        price_row = market_date.bond_market_prices[0]

        self.assertEqual(price_row.maturity_date, bond.maturity_date)
        self.assertEqual(price_row.principal_factor, 1)
        self.assertIsNotNone(price_row.future_xirr)

        cashflows = market_date.get_cashflows(bond.name, 100)
        self.assertGreater(len(cashflows), 2)
        self.assertEqual(cashflows[0]["type"], "market_price")

    def test_ignores_incomplete_market_price_rows(self):
        market_date = make_market_date(make_bond())
        market_date.append("bond_market_prices", {"market_price": 100})

        market_date.save()
        self.assertIsNone(market_date.bond_market_prices[-1].maturity_date)

    def test_recalculates_a_zero_market_price(self):
        market_date = make_market_date(make_bond(), market_price=0)
        price_row = market_date.bond_market_prices[0]

        self.assertIsNone(price_row.future_xirr)
