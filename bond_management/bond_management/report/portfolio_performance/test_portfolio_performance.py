from unittest.mock import patch

from frappe.tests import IntegrationTestCase

from bond_management.bond_management.report.portfolio_performance.portfolio_performance import (
    execute,
    get_xirr_cashflows,
    get_columns,
    make_total_row,
)
from bond_management.bond_management.tests.factories import (
    make_bond,
    make_market_date,
    make_portfolio,
    make_transaction,
)


class TestPortfolioPerformance(IntegrationTestCase):
    def test_columns_are_defined_and_multi_currency_data_has_no_total(self):
        columns = get_columns()
        self.assertIn("isin", [column["fieldname"] for column in columns])

        rows = [
            {
                "currency": "USD",
                "nominal_value": 1,
                "purchases_value": 1,
                "sales_value": 0,
                "coupons_value": 0,
                "amortisation_value": 0,
                "market_value": 1,
                "gain_value": 0,
            },
            {
                "currency": "KES",
                "nominal_value": 1,
                "purchases_value": 1,
                "sales_value": 0,
                "coupons_value": 0,
                "amortisation_value": 0,
                "market_value": 1,
                "gain_value": 0,
            },
        ]
        with (
            patch(
                "bond_management.bond_management.report.portfolio_performance.portfolio_performance.frappe.has_permission",
                return_value=True,
            ),
            patch(
                "bond_management.bond_management.report.portfolio_performance.portfolio_performance.get_data",
                return_value=(rows, [], []),
            ),
        ):
            _, data = execute({"portfolio": "TEST", "valuation_date": "2025-01-01"})

        self.assertEqual(data, rows)
        self.assertEqual(make_total_row(rows[:1], [], [])["currency"], "USD")

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
        sort_key = lambda cashflow: (cashflow["date"], cashflow["amount"])
        self.assertEqual(past, sorted(past, key=sort_key))
        self.assertEqual(future, sorted(future, key=sort_key))
        self.assertNotIn(0, [cashflow["amount"] for cashflow in past + future])
