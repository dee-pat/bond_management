from types import SimpleNamespace
from unittest.mock import patch

import frappe
from frappe.tests import IntegrationTestCase

from bond_management.bond_management.utils import investor_permissions


class TestInvestorPermissions(IntegrationTestCase):
    def test_investor_without_an_assigned_portfolio_is_denied(self):
        with (
            patch.object(frappe, "get_roles", return_value=[investor_permissions.INVESTOR_ROLE]),
            patch.object(investor_permissions.frappe.qb, "get_query") as get_query,
        ):
            get_query.return_value.run.return_value = []

            self.assertEqual(
                investor_permissions.transaction_query_condition("investor@example.com"), "1=0"
            )

    def test_investor_query_is_restricted_to_assigned_portfolios(self):
        with (
            patch.object(frappe, "get_roles", return_value=[investor_permissions.INVESTOR_ROLE]),
            patch.object(investor_permissions.frappe.qb, "get_query") as get_query,
            patch.object(investor_permissions.frappe.db, "escape", side_effect=lambda value: f"'{value}'"),
        ):
            get_query.return_value.run.return_value = ["Nanda Portfolio", "Joint Portfolio"]

            self.assertEqual(
                investor_permissions.statement_query_condition("investor@example.com"),
                "`tabBond Statement`.`portfolio_name` in ('Nanda Portfolio', 'Joint Portfolio')",
            )

    def test_non_investor_uses_the_standard_permission_model(self):
        with patch.object(frappe, "get_roles", return_value=[]):
            self.assertIsNone(investor_permissions.portfolio_query_condition("manager@example.com"))

    def test_administrator_is_not_restricted_by_the_investor_role(self):
        with patch.object(frappe, "get_roles", return_value=[investor_permissions.INVESTOR_ROLE]):
            self.assertIsNone(investor_permissions.portfolio_query_condition("Administrator"))

    def test_direct_permission_check_allows_an_assigned_portfolio(self):
        with patch.object(investor_permissions, "_get_allowed_portfolios", return_value=["Nanda"]):
            self.assertTrue(
                investor_permissions._has_portfolio_access("Nanda", "investor@example.com", "read")
            )

    def test_investor_login_redirects_to_the_investor_workspace(self):
        with patch.object(frappe, "get_roles", return_value=[investor_permissions.INVESTOR_ROLE]):
            frappe.local.response = {"redirect_to": "/desk"}
            investor_permissions.redirect_investor_to_workspace(
                SimpleNamespace(user="investor@example.com")
            )

            self.assertEqual(frappe.local.response["home_page"], "/desk/bond-investor")
            self.assertNotIn("redirect_to", frappe.local.response)
