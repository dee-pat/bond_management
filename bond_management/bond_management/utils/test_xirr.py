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
    round_cashflow_amount,
)


class TestXirr(IntegrationTestCase):
    def test_returns_none_for_cashflows_without_both_signs(self):
        self.assertIsNone(calculate_xirr({date(2025, 1, 1): 100, date(2026, 1, 1): 110}))

    def test_cashflow_amounts_use_four_decimal_place_bankers_rounding(self):
        self.assertEqual(round_cashflow_amount("1.23445"), 1.2344)
        self.assertEqual(round_cashflow_amount("1.23455"), 1.2346)
        self.assertEqual(round_cashflow_amount("-1.23445"), -1.2344)

    def test_market_price_uses_price_per_hundred(self):
        bond = make_bond(face_value_per_unit=1000)

        for market_price in (105, "105"):
            with self.subTest(market_price=market_price):
                cashflows = create_future_cash_flows(bond.name, "2025-12-31", market_price)

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

    def test_past_cashflows_accept_numeric_string_market_prices(self):
        bond = make_bond(coupon_rate=0)
        portfolio = make_portfolio()
        make_transaction(bond, portfolio)

        cashflows = create_past_cash_flows(bond.name, "2025-12-31", "105", portfolio.name)
        market_price = next(row for row in cashflows if row["type"] == "market_price")

        self.assertEqual(market_price["amount"], 1050)

    def test_same_day_purchase_receives_coupon_when_full_coupon_is_paid_as_accrued_interest(self):
        bond = make_bond()
        portfolio = make_portfolio()
        coupon_date = "2025-07-01"
        make_transaction(
            bond,
            portfolio,
            trade_date=coupon_date,
            settlement_date=coupon_date,
            accrued_interest_paid=35,
            commission=0,
        )

        cashflows = create_past_cash_flows(bond.name, coupon_date, 0, portfolio.name)

        coupons = [row["amount"] for row in cashflows if row["type"] == "coupon"]
        self.assertEqual(len(coupons), 1)
        self.assertAlmostEqual(coupons[0], 35, places=2)

    def test_same_day_purchase_does_not_receive_coupon_when_accrued_interest_is_short_paid(self):
        bond = make_bond()
        portfolio = make_portfolio()
        coupon_date = "2025-07-01"
        make_transaction(
            bond,
            portfolio,
            trade_date=coupon_date,
            settlement_date=coupon_date,
            accrued_interest_paid=1,
            commission=0,
        )

        cashflows = create_past_cash_flows(bond.name, coupon_date, 0, portfolio.name)

        self.assertEqual([row for row in cashflows if row["type"] == "coupon"], [])

    def test_same_day_sale_leaves_coupon_with_the_opening_holder(self):
        bond = make_bond()
        portfolio = make_portfolio()
        coupon_date = "2025-07-01"
        make_transaction(
            bond,
            portfolio,
            trade_date="2025-06-29",
            settlement_date="2025-06-30",
            accrued_interest_paid=0,
            commission=0,
        )
        make_transaction(
            bond,
            portfolio,
            transaction_type="Sale",
            trade_date=coupon_date,
            settlement_date=coupon_date,
            accrued_interest_paid=0,
            commission=0,
        )

        cashflows = create_past_cash_flows(bond.name, coupon_date, 0, portfolio.name)

        coupons = [row["amount"] for row in cashflows if row["type"] == "coupon"]
        self.assertEqual(len(coupons), 1)
        self.assertAlmostEqual(coupons[0], 35, places=2)
