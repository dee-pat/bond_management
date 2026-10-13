import frappe
from frappe.tests import IntegrationTestCase

from bond_management.bond_management.api import investor, investor_reports
from bond_management.bond_management.api.investor import get_bootstrap
from bond_management.bond_management.tests.factories import (
    as_investor_user,
    make_investor_user,
    make_portfolio,
)
from bond_management.bond_management.utils.investor_permissions import (
    BOND_MANAGER_ROLE,
    INVESTOR_ROLE,
)


class TestInvestorAccess(IntegrationTestCase):
    def test_common_access_gate_protects_all_covered_endpoints(self):
        portfolio = make_portfolio()
        report_args = (portfolio.name, "2025-12-31")
        endpoints = (
            (investor.get_bootstrap, ()),
            (investor.get_transactions, ()),
            (investor.get_statements, ()),
            (investor.get_bonds, ()),
            (investor.get_market_dates, ()),
            (investor.get_exchange_rates, ()),
            (investor_reports.get_portfolio_performance, report_args),
            (investor_reports.get_portfolio_performance_cashflows, (*report_args, "TOTAL", "past")),
            (investor_reports.get_interest_difference_by_portfolio, (portfolio.name,)),
            (investor_reports.get_bond_yield_comparison, ()),
            (investor_reports.get_yield_comparison_defaults, ()),
        )
        access_cases = (
            ("Guest", True, frappe.AuthenticationError),
            (make_investor_user([]), True, frappe.PermissionError),
            ("Administrator", False, frappe.PermissionError),
        )
        for endpoint, args in endpoints:
            for user, feature_enabled, error in access_cases:
                with (
                    self.subTest(endpoint=endpoint.__name__, user=user, feature_enabled=feature_enabled),
                    as_investor_user(user, feature_enabled=feature_enabled),
                    self.assertRaises(error),
                ):
                    endpoint(*args)


class TestInvestorBootstrap(IntegrationTestCase):
    def test_investor_bootstrap_contains_only_assigned_portfolios(self):
        assigned = make_portfolio()
        unassigned = make_portfolio()
        email = make_investor_user([INVESTOR_ROLE])
        frappe.get_doc(
            {
                "doctype": "User Permission",
                "user": email,
                "allow": "Bond Portfolio",
                "for_value": assigned.name,
                "apply_to_all_doctypes": 1,
            }
        ).insert(ignore_permissions=True)

        with as_investor_user(email):
            response = get_bootstrap()

        self.assertEqual([row["name"] for row in response["portfolios"]], [assigned.name])
        self.assertNotIn(unassigned.name, {row["name"] for row in response["portfolios"]})
        self.assertEqual(
            set(response),
            {"feature_enabled", "user", "is_investor", "is_support", "portfolios"},
        )
        self.assertEqual(set(response["portfolios"][0]), {"name", "label"})
        self.assertNotIn("account_no", response["portfolios"][0])

    def test_investor_without_assignment_gets_an_empty_bootstrap(self):
        email = make_investor_user([INVESTOR_ROLE])
        with as_investor_user(email):
            response = get_bootstrap()

        self.assertEqual(response["portfolios"], [])

    def test_administrator_and_manager_use_normal_portfolio_permissions(self):
        portfolio = make_portfolio()
        manager = make_investor_user([BOND_MANAGER_ROLE])

        with as_investor_user(manager):
            response = get_bootstrap()

        self.assertIn(portfolio.name, {row["name"] for row in response["portfolios"]})
        self.assertTrue(response["is_support"])
