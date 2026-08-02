from types import SimpleNamespace
from unittest.mock import patch

import frappe
from frappe.tests import IntegrationTestCase

from bond_management.bond_management.report.portfolio_performance.portfolio_performance import (
    validate_report_inputs,
)
from bond_management.bond_management.tests.factories import (
    make_bond,
    make_portfolio,
    make_transaction,
    unique_name,
)
from bond_management.bond_management.utils import investor_permissions
from bond_management.patches.add_bond_investor_read_only_access import execute as ensure_investor_access


class TestInvestorPermissions(IntegrationTestCase):
    def test_real_user_permissions_isolate_lists_documents_and_reports(self):
        assigned_portfolio = make_portfolio()
        other_portfolio = make_portfolio()
        bond = make_bond()
        assigned_transaction = make_transaction(bond, assigned_portfolio)
        other_transaction = make_transaction(bond, other_portfolio)
        email = f"{unique_name('investor').lower()}@example.com"
        frappe.get_doc(
            {
                "doctype": "User",
                "email": email,
                "first_name": "Investor",
                "send_welcome_email": 0,
                "roles": [{"role": investor_permissions.INVESTOR_ROLE}],
            }
        ).insert(ignore_permissions=True)
        frappe.get_doc(
            {
                "doctype": "User Permission",
                "user": email,
                "allow": "Bond Portfolio",
                "for_value": assigned_portfolio.name,
                "apply_to_all_doctypes": 1,
            }
        ).insert(ignore_permissions=True)

        previous_user = frappe.session.user
        try:
            frappe.set_user(email)
            visible_transactions = frappe.qb.get_query(
                "Bond Transaction",
                fields=["name"],
                ignore_permissions=False,
            ).run(pluck=True)

            self.assertIn(assigned_transaction.name, visible_transactions)
            self.assertNotIn(other_transaction.name, visible_transactions)
            frappe.get_doc("Bond Transaction", assigned_transaction.name).check_permission("read")
            with self.assertRaises(frappe.PermissionError):
                frappe.get_doc("Bond Transaction", other_transaction.name).check_permission("read")
            self.assertEqual(
                validate_report_inputs(assigned_portfolio.name, "2025-12-31")[0],
                assigned_portfolio.name,
            )
            with self.assertRaises(frappe.PermissionError):
                validate_report_inputs(other_portfolio.name, "2025-12-31")
        finally:
            frappe.set_user(previous_user)

    def test_read_only_permission_patch_is_idempotent_and_clears_mutating_access(self):
        ensure_investor_access()
        ensure_investor_access()
        permissions = frappe.qb.get_query(
            "DocPerm",
            fields=["read", "write", "create", "delete"],
            filters={
                "parent": "Bond Transaction",
                "role": investor_permissions.INVESTOR_ROLE,
                "permlevel": 0,
            },
            ignore_permissions=True,
        ).run(as_dict=True)

        self.assertEqual(len(permissions), 1)
        self.assertEqual(permissions[0].read, 1)
        self.assertEqual(permissions[0].write, 0)
        self.assertEqual(permissions[0].create, 0)
        self.assertEqual(permissions[0].delete, 0)

    def test_investor_without_an_assigned_portfolio_is_denied(self):
        with (
            patch.object(frappe, "get_roles", return_value=[investor_permissions.INVESTOR_ROLE]),
            patch.object(investor_permissions.frappe.qb, "get_query") as get_query,
        ):
            get_query.return_value.run.return_value = []

            self.assertEqual(investor_permissions.transaction_query_condition("investor@example.com"), "1=0")

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

    def test_bond_management_manager_can_open_bond_management_desk(self):
        with (
            patch.dict(frappe.local.session, {"user": "manager@example.com"}),
            patch.object(frappe, "get_roles", return_value=[investor_permissions.BOND_MANAGER_ROLE]),
        ):
            self.assertTrue(investor_permissions.has_investor_desk_access())

    def test_bond_management_manager_has_full_app_permissions(self):
        doctypes = [
            "Bond Market Date",
            "Bond Master",
            "Bond Portfolio",
            "Bond Statement",
            "Bond Transaction",
        ]
        permissions = frappe.qb.get_query(
            "DocPerm",
            fields=["parent", "read", "write", "create", "delete", "submit", "cancel", "amend", "import"],
            filters={
                "role": investor_permissions.BOND_MANAGER_ROLE,
                "parent": ["in", doctypes],
                "permlevel": 0,
            },
            ignore_permissions=True,
        ).run(as_dict=True)

        self.assertEqual(len(permissions), len(doctypes))
        for permission in permissions:
            self.assertTrue(
                all(
                    permission.get(field)
                    for field in (
                        "read",
                        "write",
                        "create",
                        "delete",
                        "submit",
                        "cancel",
                        "amend",
                        "import",
                    )
                )
            )

    def test_direct_permission_check_allows_an_assigned_portfolio(self):
        with patch.object(investor_permissions, "_get_allowed_portfolios", return_value=["Nanda"]):
            self.assertTrue(
                investor_permissions._has_portfolio_access("Nanda", "investor@example.com", "read")
            )

    def test_investor_login_redirects_to_the_investor_workspace(self):
        with patch.object(frappe, "get_roles", return_value=[investor_permissions.INVESTOR_ROLE]):
            frappe.local.response = {"redirect_to": "/desk"}
            investor_permissions.redirect_investor_to_workspace(SimpleNamespace(user="investor@example.com"))

            self.assertEqual(frappe.local.response["home_page"], "/desk/bond-investor")
            self.assertNotIn("redirect_to", frappe.local.response)
