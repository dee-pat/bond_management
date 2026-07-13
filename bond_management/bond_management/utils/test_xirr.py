from datetime import date

from frappe.tests import IntegrationTestCase

from bond_management.bond_management.tests.factories import (
    make_bond,
    make_portfolio,
    make_transaction,
)
from bond_management.bond_management.utils.xirr import (
    calculate_xirr,
    create_future_cash_flows,
    create_past_cash_flows,
)


class TestXirr(IntegrationTestCase):
    def test_returns_none_for_cashflows_without_both_signs(self):
        self.assertIsNone(calculate_xirr({date(2025, 1, 1): 100, date(2026, 1, 1): 110}))

    def test_market_price_uses_price_per_hundred(self):
        bond = make_bond(face_value_per_unit=1000)
        cashflows = create_future_cash_flows(bond.name, "2025-12-31", 105)

        self.assertEqual(cashflows[0]["amount"], -1050)

    def test_maturity_day_purchase_receives_redemption_without_double_counting_commission(self):
        bond = make_bond(coupon_rate=0)
        portfolio = make_portfolio()
        transaction = make_transaction(
            bond,
            portfolio,
            trade_date=bond.maturity_date,
            settlement_date=bond.maturity_date,
            price=100,
            accrued_interest_paid=0,
            commission=2,
        )

        cashflows = create_past_cash_flows(bond.name, bond.maturity_date, 0, portfolio.name)
        amounts_by_type = {row["type"]: row["amount"] for row in cashflows}

        self.assertEqual(transaction.commission_amount, 20)
        self.assertEqual(transaction.settlement_amount, 1000)
        self.assertEqual(amounts_by_type["purchase"], -1000)
        self.assertEqual(amounts_by_type["sale"], 1000)
