from contextlib import contextmanager
from unittest.mock import patch

import frappe
from frappe.exceptions import FrappeTypeError
from frappe.tests import IntegrationTestCase

from bond_management.bond_management.api import investor as investor_api
from bond_management.bond_management.api.investor_reports import (
    PORTFOLIO_CASHFLOW_FIELDS,
    PORTFOLIO_PERFORMANCE_COLUMN_FIELDS,
    PORTFOLIO_PERFORMANCE_ROW_FIELDS,
    get_portfolio_performance,
    get_portfolio_performance_cashflows,
)
from bond_management.bond_management.report.portfolio_performance.portfolio_performance import (
    execute,
    get_xirr_cashflows,
)
from bond_management.bond_management.tests.factories import (
    make_bond,
    make_exchange_rate,
    make_market_date,
    make_portfolio,
    make_transaction,
    unique_name,
)
from bond_management.bond_management.utils.investor_permissions import (
    BOND_MANAGER_ROLE,
    INVESTOR_ROLE,
)
from bond_management.bond_management.utils.investor_ui import FEATURE_FLAG

COLUMN_FIELDS = {
    "fieldname",
    "label",
    "fieldtype",
    "options",
    "description",
    "precision",
    "cashflow_action",
}
VALUATION_DATE = "2025-12-31"


class TestInvestorPortfolioPerformance(IntegrationTestCase):
    def test_common_access_gate_protects_both_endpoints(self):
        portfolio = make_portfolio()
        report_args = (portfolio.name, VALUATION_DATE)
        cashflow_args = (*report_args, "TOTAL", "past")

        for endpoint, args in (
            (get_portfolio_performance, report_args),
            (get_portfolio_performance_cashflows, cashflow_args),
        ):
            with self.subTest(endpoint=endpoint.__name__), self._as_user("Guest"):
                with self.assertRaises(frappe.AuthenticationError):
                    endpoint(*args)

            unapproved = self._make_user([])
            with self._as_user(unapproved):
                with self.assertRaises(frappe.PermissionError):
                    endpoint(*args)

            with self._as_user("Administrator", feature_enabled=False):
                with self.assertRaises(frappe.PermissionError):
                    endpoint(*args)

    def test_standard_report_role_and_reference_doctype_permissions_are_required(self):
        portfolio = make_portfolio()
        investor = self._make_investor(portfolio.name)

        with self._as_user(investor):
            with (
                patch(
                    "frappe.core.doctype.report.report.Report.is_permitted",
                    return_value=False,
                ),
                self.assertRaisesRegex(frappe.PermissionError, "access to Report"),
            ):
                get_portfolio_performance(portfolio.name, VALUATION_DATE)

            original_has_permission = frappe.has_permission

            def deny_report_permission(doctype, ptype=None, *args, **kwargs):
                if doctype == "Bond Portfolio" and ptype == "report":
                    return False
                return original_has_permission(doctype, ptype, *args, **kwargs)

            with (
                patch.object(frappe, "has_permission", side_effect=deny_report_permission),
                self.assertRaisesRegex(frappe.PermissionError, "report on: Bond Portfolio"),
            ):
                get_portfolio_performance(portfolio.name, VALUATION_DATE)

    def test_unreadable_and_unknown_portfolios_have_same_failure(self):
        assigned = make_portfolio()
        unreadable = make_portfolio()
        investor = self._make_investor(assigned.name)
        unknown = unique_name("UNKNOWN-PORTFOLIO")

        for endpoint, suffix in (
            (get_portfolio_performance, ()),
            (get_portfolio_performance_cashflows, ("TOTAL", "past")),
        ):
            messages = []
            with self._as_user(investor):
                for portfolio in (unreadable.name, unknown):
                    with self.assertRaises(frappe.PermissionError) as error:
                        endpoint(portfolio, VALUATION_DATE, *suffix)
                    messages.append(str(error.exception))

            self.assertEqual(messages[0], messages[1])

    def test_manager_and_administrator_use_normal_report_permissions(self):
        portfolio = make_portfolio()
        manager = self._make_user([BOND_MANAGER_ROLE])

        for user in (manager, "Administrator"):
            with self.subTest(user=user), self._as_user(user):
                response = get_portfolio_performance(portfolio.name, VALUATION_DATE)

            self.assertEqual(response["report"]["rows"], [])

    def test_assigned_empty_portfolio_has_no_rows_or_total(self):
        portfolio = make_portfolio()
        investor = self._make_investor(portfolio.name)

        with self._as_user(investor):
            response = get_portfolio_performance(portfolio.name, VALUATION_DATE)

        self.assertEqual(response["report"]["rows"], [])

    def test_usd_report_has_exact_normalized_projection(self):
        portfolio, _, investor = self._make_usd_report()

        with self._as_user(investor):
            response = get_portfolio_performance(portfolio.name, VALUATION_DATE)

        self.assertEqual(set(response), {"report"})
        report = response["report"]
        self.assertEqual(set(report), {"filters", "columns", "rows", "chart"})
        self.assertEqual(
            report["filters"],
            {"portfolio": portfolio.name, "valuation_date": VALUATION_DATE},
        )
        self.assertIsNone(report["chart"])
        self.assertEqual(
            [column["fieldname"] for column in report["columns"]],
            [
                "isin",
                "currency",
                "principal_factor",
                "nominal_value",
                "purchases_value",
                "proceeds_value",
                "market_value",
                "gain_value",
                "xirr",
                "future_xirr",
            ],
        )
        self.assertTrue(all(set(column) == COLUMN_FIELDS for column in report["columns"]))
        self.assertTrue(all(set(row) == set(PORTFOLIO_PERFORMANCE_ROW_FIELDS) for row in report["rows"]))
        self.assertEqual(report["columns"][0]["fieldtype"], "Link")
        self.assertEqual(report["columns"][0]["options"], "Bond Master")

        columns = {column["fieldname"]: column for column in report["columns"]}
        self.assertEqual(columns["principal_factor"]["precision"], 3)
        self.assertEqual(columns["market_value"]["precision"], 2)
        self.assertEqual(columns["xirr"]["precision"], 3)
        self.assertIsNone(columns["isin"]["precision"])
        self.assertEqual(
            columns["xirr"]["cashflow_action"],
            {"xirr_type": "past", "cashflow_currency": "native"},
        )
        self.assertEqual(
            columns["future_xirr"]["cashflow_action"],
            {"xirr_type": "future", "cashflow_currency": "native"},
        )
        self.assertIsNone(columns["market_value"]["cashflow_action"])
        self.assertIs(investor_api.get_portfolio_performance, get_portfolio_performance)
        self.assertEqual(frappe.allowed_http_methods_for_whitelisted_func[get_portfolio_performance], ["GET"])

    def test_hidden_report_helpers_and_column_controls_are_omitted(self):
        portfolio, _, investor = self._make_usd_report()

        with self._as_user(investor):
            response = get_portfolio_performance(portfolio.name, VALUATION_DATE)

        report = response["report"]
        hidden = {
            "exchange_rate",
            "nominal_value_usd",
            "purchases_value_usd",
            "proceeds_value_usd",
            "gain_value_usd",
            "future_xirr_usd",
        }
        self.assertTrue(all(hidden.isdisjoint(row) for row in report["rows"]))
        self.assertTrue(all(set(column) == COLUMN_FIELDS for column in report["columns"]))
        self.assertTrue(
            set(PORTFOLIO_PERFORMANCE_COLUMN_FIELDS).issuperset(
                column["fieldname"] for column in report["columns"]
            )
        )
        self.assertNotIn("width", str(report["columns"]))
        self.assertNotIn("disable_total", str(report["columns"]))

    def test_mixed_currency_columns_totals_and_values_match_authoritative_report(self):
        portfolio = make_portfolio()
        usd_bond = make_bond()
        kes_bond = make_bond(currency="KES")
        make_transaction(usd_bond, portfolio)
        make_transaction(kes_bond, portfolio)
        make_exchange_rate(rate="0.01")
        market_date = make_market_date(usd_bond)
        make_market_date(kes_bond, market_date=market_date)
        investor = self._make_investor(portfolio.name)
        filters = {"portfolio": portfolio.name, "valuation_date": VALUATION_DATE}

        with self._as_user(investor):
            _, authoritative_rows = execute(filters)
            response = get_portfolio_performance(portfolio.name, VALUATION_DATE)

        report = response["report"]
        self.assertEqual(
            [column["fieldname"] for column in report["columns"]],
            list(PORTFOLIO_PERFORMANCE_COLUMN_FIELDS),
        )
        self.assertEqual(
            report["rows"],
            [
                {field: row.get(field) for field in PORTFOLIO_PERFORMANCE_ROW_FIELDS}
                for row in authoritative_rows
            ],
        )
        total = report["rows"][-1]
        self.assertEqual(total["isin"], "TOTAL")
        self.assertIsNone(total["currency"])
        self.assertIsNone(total["principal_factor"])
        self.assertIsNone(total["market_value"])
        self.assertIsNone(total["xirr"])
        self.assertEqual(total["reporting_currency"], "USD")
        self.assertEqual(total["market_value_usd"], authoritative_rows[-1]["market_value_usd"])

    def test_cashflows_have_exact_projection_order_and_authoritative_values(self):
        portfolio, bond, investor = self._make_usd_report()

        with self._as_user(investor):
            authoritative = get_xirr_cashflows(
                portfolio.name,
                VALUATION_DATE,
                bond.name,
                "past",
            )
            response = get_portfolio_performance_cashflows(
                portfolio.name,
                VALUATION_DATE,
                bond.name,
                "past",
            )

        self.assertEqual(
            response["cashflows"],
            [{field: row.get(field) for field in PORTFOLIO_CASHFLOW_FIELDS} for row in authoritative],
        )
        self.assertTrue(response["cashflows"])
        self.assertTrue(all(set(row) == set(PORTFOLIO_CASHFLOW_FIELDS) for row in response["cashflows"]))
        self.assertEqual(
            response["cashflows"],
            sorted(response["cashflows"], key=lambda row: (row["date"], row["amount"])),
        )
        self.assertIs(
            investor_api.get_portfolio_performance_cashflows,
            get_portfolio_performance_cashflows,
        )
        self.assertEqual(
            frappe.allowed_http_methods_for_whitelisted_func[get_portfolio_performance_cashflows],
            ["GET"],
        )

    def test_rejects_complex_invalid_and_arbitrary_arguments(self):
        portfolio = make_portfolio()
        investor = self._make_investor(portfolio.name)

        with self._as_user(investor):
            with self.assertRaisesRegex(frappe.ValidationError, "Portfolio is required"):
                get_portfolio_performance("", VALUATION_DATE)
            with self.assertRaisesRegex(frappe.ValidationError, "Valuation Date is required"):
                get_portfolio_performance(portfolio.name, "")
            with self.assertRaises(FrappeTypeError):
                get_portfolio_performance([], VALUATION_DATE)
            with self.assertRaises(TypeError):
                get_portfolio_performance(portfolio.name, VALUATION_DATE, filters={})
            with self.assertRaisesRegex(frappe.ValidationError, "Invalid XIRR type"):
                get_portfolio_performance_cashflows(
                    portfolio.name,
                    VALUATION_DATE,
                    "TOTAL",
                    "invalid",
                )
            with self.assertRaisesRegex(frappe.ValidationError, "Invalid cash-flow currency"):
                get_portfolio_performance_cashflows(
                    portfolio.name,
                    VALUATION_DATE,
                    "TOTAL",
                    "past",
                    "invalid",
                )
            with self.assertRaises(FrappeTypeError):
                get_portfolio_performance_cashflows(
                    portfolio.name,
                    VALUATION_DATE,
                    [],
                    "past",
                )
            with self.assertRaises(TypeError):
                get_portfolio_performance_cashflows(
                    portfolio.name,
                    VALUATION_DATE,
                    "TOTAL",
                    "past",
                    sort="date desc",
                )

    def _make_usd_report(self):
        portfolio = make_portfolio()
        bond = make_bond()
        make_transaction(bond, portfolio)
        make_market_date(bond)
        return portfolio, bond, self._make_investor(portfolio.name)

    def _make_investor(self, portfolio_name):
        investor = self._make_user([INVESTOR_ROLE])
        frappe.get_doc(
            {
                "doctype": "User Permission",
                "user": investor,
                "allow": "Bond Portfolio",
                "for_value": portfolio_name,
                "apply_to_all_doctypes": 1,
            }
        ).insert(ignore_permissions=True)
        return investor

    @staticmethod
    def _make_user(roles):
        return (
            frappe.get_doc(
                {
                    "doctype": "User",
                    "email": f"{unique_name('investor-performance-ui').lower()}@example.com",
                    "first_name": "Investor Performance Test",
                    "send_welcome_email": 0,
                    "roles": [{"role": role} for role in roles],
                }
            )
            .insert(ignore_permissions=True)
            .name
        )

    @staticmethod
    @contextmanager
    def _as_user(user, *, feature_enabled=True):
        previous_user = frappe.session.user
        try:
            frappe.set_user(user)
            with patch.dict(frappe.conf, {FEATURE_FLAG: int(feature_enabled)}):
                yield
        finally:
            frappe.set_user(previous_user)
