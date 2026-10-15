import frappe
from frappe.exceptions import FrappeTypeError
from frappe.tests import IntegrationTestCase

from bond_management.bond_management.api import investor, investor_reports
from bond_management.bond_management.api.investor import MAX_PAGE_LENGTH, MAX_PAGE_START, get_bootstrap
from bond_management.bond_management.tests.factories import (
    as_investor_user,
    make_assigned_investor,
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
            # The gate must run before name lookup, so a missing name still hits it.
            (investor.get_transaction, ("missing",)),
            (investor.get_statement, ("missing",)),
            (investor.get_bond, ("missing",)),
            (investor.get_market_date, ("missing",)),
            (investor.get_exchange_rate, ("missing",)),
            (investor_reports.get_portfolio_performance, report_args),
            (investor_reports.get_portfolio_performance_cashflows, (*report_args, "TOTAL", "past")),
            (investor_reports.get_interest_difference_by_portfolio, (portfolio.name,)),
            (investor_reports.get_bond_yield_comparison, ()),
            (investor_reports.get_yield_comparison_defaults, ()),
        )
        # Match the gate's own messages so later portfolio or record checks cannot satisfy a case.
        access_cases = (
            ("Guest", True, frappe.AuthenticationError, "Login is required"),
            (make_investor_user([]), True, frappe.PermissionError, "not permitted to access the investor"),
            ("Administrator", False, frappe.PermissionError, "investor application is not enabled"),
        )
        for endpoint, args in endpoints:
            for user, feature_enabled, error, message in access_cases:
                with (
                    self.subTest(endpoint=endpoint.__name__, user=user, feature_enabled=feature_enabled),
                    as_investor_user(user, feature_enabled=feature_enabled),
                    self.assertRaisesRegex(error, message),
                ):
                    endpoint(*args)


class TestInvestorListControls(IntegrationTestCase):
    # Each list shares one validated paging/sort/filter path; a hidden or
    # non-filterable column per endpoint proves its allowlist is applied.
    LIST_ENDPOINTS = (
        (investor.get_transactions, "isin", "attachment", "settlement_date"),
        (investor.get_statements, "statement_date", "attachment", "statement_date"),
        (investor.get_bonds, "isin", "principal_schedule", "issue_date"),
        (investor.get_market_dates, "date", "bond_market_prices", "date"),
        (investor.get_exchange_rates, "rate", "statement", "rate_date"),
    )

    def test_list_endpoints_bound_paging_and_allow_list_sort_and_filter(self):
        rejected = (
            (
                {"page_length": str(MAX_PAGE_LENGTH + 1)},
                frappe.ValidationError,
                f"cannot exceed {MAX_PAGE_LENGTH}",
            ),
            ({"page_length": "0"}, frappe.ValidationError, "must be at least 1"),
            ({"start": "-1"}, frappe.ValidationError, "must be at least 0"),
            ({"start": MAX_PAGE_START + 1}, frappe.ValidationError, f"cannot exceed {MAX_PAGE_START}"),
            ({"start": "1.5"}, frappe.ValidationError, "must be an integer"),
            ({"start": []}, FrappeTypeError, ""),
            ({"filters": {"name": "x"}}, TypeError, ""),
            ({"sort_by": "name", "sort_order": "asc"}, frappe.ValidationError, "not supported"),
            ({"sort_order": "asc"}, frappe.ValidationError, "requires Sort by"),
            ({"filter_field": "isin"}, frappe.ValidationError, "provided together"),
        )
        investor_user = make_investor_user([INVESTOR_ROLE])

        with as_investor_user(investor_user):
            for endpoint, sortable, hidden_sort, unfilterable in self.LIST_ENDPOINTS:
                with self.subTest(endpoint=endpoint.__name__):
                    page = endpoint(page_length=str(MAX_PAGE_LENGTH))
                    self.assertEqual(page["pagination"]["page_length"], MAX_PAGE_LENGTH)
                    cases = (
                        *rejected,
                        (
                            {"sort_by": hidden_sort, "sort_order": "asc"},
                            frappe.ValidationError,
                            "not supported",
                        ),
                        (
                            {"sort_by": sortable, "sort_order": "sideways"},
                            frappe.ValidationError,
                            "asc or desc",
                        ),
                        (
                            {"filter_field": unfilterable, "filter_value": "2025-01-01"},
                            frappe.ValidationError,
                            "Filter field is not supported",
                        ),
                    )
                    for kwargs, error, message in cases:
                        with self.subTest(kwargs=kwargs), self.assertRaisesRegex(error, message):
                            endpoint(**kwargs)


class TestInvestorBootstrap(IntegrationTestCase):
    def test_investor_bootstrap_contains_only_assigned_portfolios(self):
        assigned = make_portfolio()
        unassigned = make_portfolio()
        email = make_assigned_investor(assigned.name)

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
