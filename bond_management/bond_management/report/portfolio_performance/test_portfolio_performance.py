from unittest.mock import patch

import frappe
from frappe.tests import IntegrationTestCase

from bond_management.bond_management.report.portfolio_performance.portfolio_performance import (
    execute,
    get_columns,
    get_data,
    get_xirr_cashflows,
    make_total_row,
)
from bond_management.bond_management.tests.factories import (
    make_bond,
    make_market_date,
    make_portfolio,
    make_transaction,
)
from bond_management.bond_management.utils.xirr import create_future_cash_flows


class TestPortfolioPerformance(IntegrationTestCase):
    def test_columns_are_defined_and_multi_currency_data_has_no_total(self):
        columns = get_columns()
        fieldnames = [column["fieldname"] for column in columns]
        self.assertIn("isin", fieldnames)
        self.assertIn("proceeds_value", fieldnames)
        self.assertNotIn("sales_value", fieldnames)
        self.assertNotIn("coupons_value", fieldnames)
        self.assertNotIn("amortisation_value", fieldnames)
        labels = {column["fieldname"]: column["label"] for column in columns}
        self.assertEqual(labels["currency"], "CCY")
        self.assertEqual(labels["principal_factor"], "Prin. Factor")
        widths = {column["fieldname"]: column["width"] for column in columns}
        self.assertEqual(
            widths,
            {
                "isin": 160,
                "currency": 60,
                "principal_factor": 90,
                "nominal_value": 135,
                "purchases_value": 135,
                "proceeds_value": 135,
                "market_value": 135,
                "gain_value": 135,
                "xirr": 80,
                "future_xirr": 105,
            },
        )

        rows = [
            {
                "currency": "USD",
                "nominal_value": 1,
                "purchases_value": 1,
                "proceeds_value": 3,
                "market_value": 1,
                "gain_value": 3,
            },
            {
                "currency": "KES",
                "nominal_value": 1,
                "purchases_value": 1,
                "proceeds_value": 5,
                "market_value": 1,
                "gain_value": 5,
            },
        ]
        portfolio = make_portfolio()
        with patch(
            "bond_management.bond_management.report.portfolio_performance.portfolio_performance.get_data",
            return_value=(rows, [], []),
        ):
            _, data = execute({"portfolio": portfolio.name, "valuation_date": "2025-01-01"})

        self.assertEqual(data, rows)
        total = make_total_row(rows[:1], [], [])
        self.assertEqual(total["currency"], "USD")
        self.assertEqual(total["proceeds_value"], 3)

    def test_returns_copyable_past_and_future_xirr_cashflows(self):
        bond = make_bond()
        portfolio = make_portfolio()
        make_transaction(bond, portfolio)
        make_market_date(bond)

        past = get_xirr_cashflows(portfolio.name, "2025-12-31", bond.name, "past")
        future = get_xirr_cashflows(portfolio.name, "2025-12-31", bond.name, "future")

        self.assertIn("purchase", [cashflow["transaction_type"] for cashflow in past])
        self.assertEqual(future[0]["transaction_type"], "market_price")
        self.assertEqual(future[0]["amount"], -1000)

        def sort_key(cashflow):
            return cashflow["date"], cashflow["amount"]

        self.assertEqual(past, sorted(past, key=sort_key))
        self.assertEqual(future, sorted(future, key=sort_key))
        self.assertNotIn(0, [cashflow["amount"] for cashflow in past + future])

    def test_real_report_arithmetic_preserves_bank_price_convention(self):
        bond = make_bond(
            coupon_rate=10,
            principal_schedule=[
                {"repayment_date": "2025-07-01", "principal_units": 50},
                {"repayment_date": "2027-01-01", "principal_units": 50},
            ],
        )
        portfolio = make_portfolio()
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
            trade_date="2025-08-31",
            settlement_date="2025-09-01",
            quantity_face_value=2,
            price=50,
            accrued_interest_paid=0,
            commission=0,
        )
        make_market_date(bond, market_price=50, date="2025-12-29")

        with patch(
            "bond_management.bond_management.report.portfolio_performance.portfolio_performance.create_future_cash_flows",
            wraps=create_future_cash_flows,
        ) as future_cashflow_builder:
            rows, past_cashflows, future_cashflows = get_data(portfolio.name, "2025-12-31")

        self.assertEqual(future_cashflow_builder.call_count, 1)
        self.assertEqual(rows[0]["principal_factor"], 0.5)
        self.assertEqual(rows[0]["nominal_value"], 400)
        self.assertEqual(
            next(cashflow["amount"] for cashflow in past_cashflows if cashflow["type"] == "market_price"),
            400,
        )
        proceeds = [
            cashflow for cashflow in past_cashflows if cashflow["type"] in {"sale", "coupon", "amortisation"}
        ]
        self.assertEqual({cashflow["type"] for cashflow in proceeds}, {"sale", "coupon", "amortisation"})
        self.assertEqual(rows[0]["proceeds_value"], sum(cashflow["amount"] for cashflow in proceeds))
        self.assertEqual(rows[0]["proceeds_value"], 650)
        self.assertAlmostEqual(rows[0]["gain_value"], rows[0]["market_value"] + 650 - 1050)
        self.assertEqual(future_cashflows[0]["amount"], -400)

    def test_open_position_requires_a_market_price(self):
        bond = make_bond()
        portfolio = make_portfolio()
        make_transaction(bond, portfolio)

        with self.assertRaisesRegex(frappe.ValidationError, "No market price found"):
            get_data(portfolio.name, "2025-12-31")

    def test_closed_position_needs_no_quote_or_future_yield(self):
        bond = make_bond()
        portfolio = make_portfolio()
        make_transaction(bond, portfolio)
        make_transaction(
            bond,
            portfolio,
            transaction_type="Sale",
            trade_date="2026-01-01",
            settlement_date="2026-01-02",
            quantity_face_value=10,
            price=100,
            accrued_interest_paid=0,
            commission=0,
        )

        rows, past_cashflows, future_cashflows = get_data(portfolio.name, "2026-01-03")

        self.assertEqual(rows[0]["market_value"], 0)
        self.assertIsNone(rows[0]["future_xirr"])
        self.assertTrue(past_cashflows)
        self.assertEqual(future_cashflows, [])
        self.assertEqual(
            get_xirr_cashflows(portfolio.name, "2026-01-03", bond.name, "future"),
            [],
        )

    def test_matured_position_needs_no_quote(self):
        bond = make_bond()
        portfolio = make_portfolio()
        make_transaction(bond, portfolio)

        rows, _, future_cashflows = get_data(portfolio.name, bond.maturity_date)

        self.assertEqual(rows[0]["market_value"], 0)
        self.assertIsNone(rows[0]["future_xirr"])
        self.assertEqual(future_cashflows, [])

    def test_report_inputs_and_permissions_are_validated(self):
        with self.assertRaisesRegex(frappe.ValidationError, "Portfolio is required"):
            execute({"valuation_date": "2025-01-01"})
        with self.assertRaisesRegex(frappe.ValidationError, "Valuation Date is required"):
            execute({"portfolio": make_portfolio().name})
        with self.assertRaisesRegex(frappe.ValidationError, "does not exist"):
            execute({"portfolio": "NOT-A-PORTFOLIO", "valuation_date": "2025-01-01"})

        portfolio = make_portfolio()
        with (
            patch(
                "bond_management.bond_management.report.portfolio_performance.portfolio_performance.frappe.has_permission",
                return_value=False,
            ),
            self.assertRaises(frappe.PermissionError),
        ):
            execute({"portfolio": portfolio.name, "valuation_date": "2025-01-01"})

    def test_cashflow_endpoint_rejects_bond_outside_portfolio(self):
        portfolio = make_portfolio()
        portfolio_bond = make_bond()
        other_bond = make_bond()
        make_transaction(portfolio_bond, portfolio)

        with self.assertRaisesRegex(frappe.ValidationError, "is not in this portfolio"):
            get_xirr_cashflows(portfolio.name, "2025-12-31", other_bond.name, "past")
