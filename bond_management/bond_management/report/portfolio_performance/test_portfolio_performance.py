from decimal import Decimal
from unittest.mock import patch

import frappe
from frappe.exceptions import FrappeTypeError
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
    make_exchange_rate,
    make_market_date,
    make_portfolio,
    make_transaction,
)
from bond_management.bond_management.utils.performance import get_latest_market_rows
from bond_management.bond_management.utils.xirr import create_future_cash_flows


class TestPortfolioPerformance(IntegrationTestCase):
    def test_columns_are_defined_and_multi_currency_totals_use_usd(self):
        columns = get_columns()
        fieldnames = [column["fieldname"] for column in columns]
        self.assertIn("isin", fieldnames)
        self.assertIn("proceeds_value", fieldnames)
        self.assertNotIn("proceeds_value_usd", fieldnames)
        self.assertNotIn("nominal_value_usd", fieldnames)
        self.assertNotIn("purchases_value_usd", fieldnames)
        self.assertNotIn("gain_value_usd", fieldnames)
        self.assertNotIn("reporting_currency", fieldnames)
        self.assertNotIn("exchange_rate", fieldnames)
        self.assertIn("market_value_usd", fieldnames)
        self.assertIn("xirr_usd", fieldnames)
        self.assertNotIn("future_xirr_usd", fieldnames)
        self.assertNotIn("sales_value", fieldnames)
        self.assertNotIn("coupons_value", fieldnames)
        self.assertNotIn("amortisation_value", fieldnames)
        labels = {column["fieldname"]: column["label"] for column in columns}
        self.assertEqual(labels["currency"], "CCY")
        self.assertEqual(labels["principal_factor"], "Prin. Factor")
        principal_factor_column = next(
            column for column in columns if column["fieldname"] == "principal_factor"
        )
        self.assertTrue(principal_factor_column["disable_total"])
        widths = {column["fieldname"]: column["width"] for column in columns}
        self.assertEqual(
            widths,
            {
                "isin": 140,
                "currency": 60,
                "principal_factor": 110,
                "nominal_value": 135,
                "purchases_value": 135,
                "proceeds_value": 135,
                "market_value": 135,
                "gain_value": 135,
                "xirr": 80,
                "market_value_usd": 145,
                "xirr_usd": 95,
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
                "reporting_currency": "USD",
                "nominal_value_usd": 1,
                "purchases_value_usd": 1,
                "proceeds_value_usd": 3,
                "market_value_usd": 1,
                "gain_value_usd": 3,
            },
            {
                "currency": "KES",
                "nominal_value": 1,
                "purchases_value": 1,
                "proceeds_value": 5,
                "market_value": 1,
                "gain_value": 5,
                "reporting_currency": "USD",
                "nominal_value_usd": 2,
                "purchases_value_usd": 2,
                "proceeds_value_usd": 5,
                "market_value_usd": 2,
                "gain_value_usd": 5,
            },
        ]
        portfolio = make_portfolio()
        with patch(
            "bond_management.bond_management.report.portfolio_performance.portfolio_performance.get_data",
            return_value=(rows, [], [], [], []),
        ):
            _, data = execute({"portfolio": portfolio.name, "valuation_date": "2025-01-01"})

        self.assertEqual(data[:2], rows)
        total = data[-1]
        self.assertIsNone(total["currency"])
        self.assertEqual(total["reporting_currency"], "USD")
        self.assertEqual(total["proceeds_value_usd"], 8)
        total = make_total_row(rows[:1], [], [], [], [])
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
        self.assertEqual(future[0]["currency"], "USD")
        self.assertEqual(future[0]["amount"], -1000)
        self.assertEqual(future[0]["quantity"], 10)
        self.assertEqual(future[0]["rate"], -100)

        purchase = next(cashflow for cashflow in past if cashflow["transaction_type"] == "purchase")
        self.assertEqual(purchase["quantity"], 10)
        self.assertEqual(purchase["rate"], -105.1)

        def sort_key(cashflow):
            return cashflow["date"], cashflow["amount"]

        self.assertEqual(past, sorted(past, key=sort_key))
        self.assertEqual(future, sorted(future, key=sort_key))
        self.assertNotIn(0, [cashflow["amount"] for cashflow in past + future])

    def test_mixed_currency_rows_include_usd_values_and_usd_total(self):
        portfolio = make_portfolio()
        usd_bond = make_bond()
        kes_bond = make_bond(currency="KES")
        make_transaction(usd_bond, portfolio)
        make_transaction(kes_bond, portfolio)
        make_exchange_rate(portfolio, rate_date="2025-12-30", rate="0.01")
        make_market_date(usd_bond, date="2025-12-30")
        make_market_date(kes_bond, date="2025-12-30")

        columns, rows = execute({"portfolio": portfolio.name, "valuation_date": "2025-12-31"})

        self.assertIn("market_value_usd", {column["fieldname"] for column in columns})
        bond_rows = {row["isin"]: row for row in rows if row["isin"] != "TOTAL"}
        self.assertEqual(bond_rows[kes_bond.name]["currency"], "KES")
        self.assertEqual(bond_rows[kes_bond.name]["reporting_currency"], "USD")
        self.assertEqual(bond_rows[kes_bond.name]["exchange_rate"], Decimal("0.01"))
        self.assertEqual(
            bond_rows[kes_bond.name]["market_value_usd"],
            (bond_rows[kes_bond.name]["market_value"] * Decimal("0.01")).quantize(Decimal("0.0001")),
        )

        total = rows[-1]
        self.assertEqual(total["isin"], "TOTAL")
        self.assertIsNone(total["currency"])
        self.assertEqual(total["reporting_currency"], "USD")
        self.assertEqual(
            total["market_value_usd"],
            sum(row["market_value_usd"] for row in bond_rows.values()),
        )
        self.assertIsNone(total["xirr"])

        with self.assertRaisesRegex(frappe.ValidationError, "mixed-currency portfolio"):
            get_xirr_cashflows(portfolio.name, "2025-12-31", "TOTAL", "past")

        reporting_cashflows = get_xirr_cashflows(
            portfolio.name,
            "2025-12-31",
            "TOTAL",
            "past",
            "reporting",
        )
        kes_purchase = next(
            cashflow
            for cashflow in reporting_cashflows
            if cashflow["isin"] == kes_bond.name and cashflow["transaction_type"] == "purchase"
        )
        self.assertEqual(kes_purchase["currency"], "USD")
        self.assertEqual(kes_purchase["amount"], -10.51)

    def test_non_usd_report_requires_a_rate_or_manual_fallback(self):
        bond = make_bond(currency="KES")
        portfolio = make_portfolio()
        make_transaction(bond, portfolio)
        make_market_date(bond)

        with self.assertRaisesRegex(frappe.ValidationError, "Add a Bond Exchange Rate row manually"):
            execute({"portfolio": portfolio.name, "valuation_date": "2025-12-31"})

    def test_past_and_future_accrued_interest_use_the_same_total_rounding(self):
        bond = make_bond()
        portfolio = make_portfolio()
        make_transaction(
            bond,
            portfolio,
            trade_date="2025-06-29",
            settlement_date="2025-06-30",
            accrued_interest_paid=0,
            commission=0,
        )
        make_market_date(bond, date="2025-09-14")

        past = get_xirr_cashflows(portfolio.name, "2025-09-14", bond.name, "past")
        future = get_xirr_cashflows(portfolio.name, "2025-09-14", bond.name, "future")

        past_accrued = next(flow for flow in past if flow["transaction_type"] == "accrued_interest")
        future_accrued = next(flow for flow in future if flow["transaction_type"] == "accrued_interest")
        self.assertEqual(past_accrued["quantity"], future_accrued["quantity"])
        self.assertEqual(past_accrued["amount"], -future_accrued["amount"])
        self.assertEqual(past_accrued["amount"], 14.1944)

    def test_report_cashflows_use_bond_withholding_tax(self):
        bond = make_bond(coupon_rate=10, withholding_tax=10)
        portfolio = make_portfolio()
        make_transaction(
            bond,
            portfolio,
            trade_date="2025-01-01",
            settlement_date="2025-01-02",
            accrued_interest_paid=0,
            commission=0,
        )
        make_market_date(bond, date="2025-12-31")

        _, past_cashflows, future_cashflows, _, _ = get_data(portfolio.name, "2025-12-31")

        past_coupon = next(flow for flow in past_cashflows if flow["type"] == "coupon")
        future_coupon = next(flow for flow in future_cashflows if flow["type"] == "coupon")
        self.assertEqual(past_coupon["amount"], 45)
        self.assertEqual(future_coupon["amount"], 45)

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
            rows, past_cashflows, future_cashflows, _, _ = get_data(portfolio.name, "2025-12-31")

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

    def test_kes_quantity_change_scales_values_and_keeps_principal_factor_one(self):
        bond = make_bond(
            currency="KES",
            day_count_convention="Actual/364(Kenya)",
            coupon_rate=0,
            principal_schedule=[
                {"repayment_date": "2025-07-04", "principal_units": 50},
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
        make_exchange_rate(portfolio, rate_date="2025-06-30", rate="0.01")
        make_market_date(bond, date="2025-07-05")

        _, rows = execute({"portfolio": portfolio.name, "valuation_date": "2025-07-05"})

        row = rows[0]
        self.assertEqual(row["principal_factor"], 1)
        self.assertEqual(row["nominal_value"], 500)
        self.assertEqual(row["market_value"], 500)

    def test_repayment_day_uses_post_payment_nominal_and_pre_payment_coupon(self):
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
        make_market_date(bond, market_price=50, date="2025-07-01")

        rows, past_cashflows, _, _, _ = get_data(portfolio.name, "2025-07-01")

        self.assertEqual(rows[0]["principal_factor"], 0.5)
        self.assertEqual(rows[0]["nominal_value"], 500)
        self.assertEqual(
            next(flow["amount"] for flow in past_cashflows if flow["type"] == "coupon"),
            50,
        )
        self.assertEqual(
            next(flow["amount"] for flow in past_cashflows if flow["type"] == "amortisation"),
            500,
        )

    def test_report_batch_load_query_count_does_not_grow_per_bond(self):
        portfolio = make_portfolio()
        bonds = [make_bond(), make_bond()]
        for bond in bonds:
            make_transaction(bond, portfolio)
        for bond in bonds:
            make_market_date(bond)

        with patch(
            "bond_management.bond_management.utils.performance.frappe.qb.get_query",
            wraps=frappe.qb.get_query,
        ) as get_query:
            rows, _, _, _, _ = get_data(portfolio.name, "2025-12-31")

        self.assertEqual(len(rows), 2)
        self.assertEqual(get_query.call_count, 5)

    def test_market_history_query_returns_one_latest_row_per_bond(self):
        bond = make_bond()
        make_market_date(bond, market_price=90, date="2025-11-28")
        latest = make_market_date(bond, market_price=101, date="2025-11-29")

        rows = get_latest_market_rows([bond.name], "2025-11-30")

        self.assertEqual(len(rows), 1)
        self.assertEqual(rows[0].market_price, 101)
        self.assertAlmostEqual(
            rows[0].future_xirr,
            latest.bond_market_prices[-1].future_xirr,
            places=9,
        )

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

        rows, past_cashflows, future_cashflows, _, _ = get_data(portfolio.name, "2026-01-03")

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

        rows, _, future_cashflows, _, _ = get_data(portfolio.name, bond.maturity_date)

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

    def test_report_endpoints_reject_complex_input_types(self):
        portfolio = make_portfolio()

        with self.assertRaisesRegex(frappe.ValidationError, "Report filters must be an object"):
            execute([])
        with self.assertRaisesRegex(FrappeTypeError, "isin.*str"):
            get_xirr_cashflows(portfolio.name, "2025-12-31", [], "past")
        with self.assertRaisesRegex(FrappeTypeError, "xirr_type.*str"):
            get_xirr_cashflows(portfolio.name, "2025-12-31", "TOTAL", {})
        with self.assertRaisesRegex(FrappeTypeError, "cashflow_currency.*str"):
            get_xirr_cashflows(portfolio.name, "2025-12-31", "TOTAL", "past", [])
