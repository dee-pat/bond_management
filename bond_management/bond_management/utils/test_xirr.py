from datetime import date

from frappe.tests import IntegrationTestCase

from bond_management.bond_management.tests.factories import make_bond
from bond_management.bond_management.utils.xirr import (
    calculate_xirr,
    create_future_cash_flows,
)


class TestXirr(IntegrationTestCase):
    def test_returns_none_for_cashflows_without_both_signs(self):
        self.assertIsNone(calculate_xirr({date(2025, 1, 1): 100, date(2026, 1, 1): 110}))

    def test_market_price_uses_price_per_hundred(self):
        bond = make_bond(face_value_per_unit=1000)
        cashflows = create_future_cash_flows(bond.name, "2025-12-31", 105)

        self.assertEqual(cashflows[0]["amount"], -1050)
