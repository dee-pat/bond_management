from unittest.mock import patch

from frappe.tests import IntegrationTestCase

from bond_management.bond_management.report.portfolio_performance.portfolio_performance import (
    execute,
    get_columns,
    make_total_row,
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
