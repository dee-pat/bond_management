from types import SimpleNamespace
from unittest.mock import patch

import frappe
from frappe.tests import IntegrationTestCase

from bond_management import hooks as app_hooks
from bond_management.bond_management.report.portfolio_performance.portfolio_performance import (
    validate_report_inputs,
)
from bond_management.bond_management.tests.factories import (
    make_bond,
    make_exchange_rate,
    make_portfolio,
    make_transaction,
    unique_name,
)
from bond_management.bond_management.utils import investor_permissions
from bond_management.patches.add_bond_exchange_rate_permissions import (
    execute as ensure_exchange_rate_permissions,
)
from bond_management.patches.add_bond_investor_read_only_access import execute as ensure_investor_access
from bond_management.patches.add_bond_yield_comparison_report_permission import (
    execute as ensure_yield_report_permission,
)


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

    def test_exchange_rate_query_condition_is_registered(self):
        self.assertEqual(
            app_hooks.permission_query_conditions["Bond Exchange Rate"],
            "bond_management.bond_management.utils.investor_permissions.exchange_rate_query_condition",
        )

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

    def test_exchange_rate_query_condition_hides_unreadable_statement_links(self):
        statement_condition = "`tabBond Statement`.`portfolio_name` in ('Assigned')"
        with patch.object(
            investor_permissions,
            "statement_query_condition",
            return_value=statement_condition,
        ):
            condition = investor_permissions.exchange_rate_query_condition("investor@example.com")
            self.assertIn("`tabBond Exchange Rate`.`statement` is null", condition)
            self.assertIn("select `tabBond Statement`.`name`", condition)
            self.assertIn(statement_condition, condition)

            with investor_permissions.include_shared_exchange_rates_in_safe_projection():
                self.assertIsNone(investor_permissions.exchange_rate_query_condition("investor@example.com"))
            self.assertIn(
                statement_condition,
                investor_permissions.exchange_rate_query_condition("investor@example.com"),
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
            self.assertTrue(
                investor_permissions.has_portfolio_permission(
                    SimpleNamespace(name="Nanda"),
                    "manager@example.com",
                    "read",
                )
            )

    def test_investor_permission_hook_denies_unassigned_portfolio(self):
        with patch.object(investor_permissions, "_get_allowed_portfolios", return_value=["Other"]):
            self.assertFalse(
                investor_permissions.has_transaction_permission(
                    SimpleNamespace(portfolio_name="Nanda"),
                    "investor@example.com",
                    "read",
                )
            )

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
            "Bond Exchange Rate",
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
                    )
                )
            )
            self.assertFalse(permission.submit)
            self.assertFalse(permission.cancel)
            self.assertFalse(permission.amend)
            self.assertEqual(
                bool(permission.get("import")),
                bool(frappe.get_meta(permission.parent).allow_import),
            )

    def test_manager_permissions_are_bootstrapped_on_fresh_install(self):
        self.assertIn(
            "bond_management.patches.add_bond_management_manager_access.execute",
            app_hooks.after_install,
        )
        self.assertIn(
            "bond_management.patches.add_bond_management_manager_access.execute",
            app_hooks.after_migrate,
        )
        self.assertIn(
            "bond_management.patches.add_bond_management_report_permission.execute",
            app_hooks.after_install,
        )
        self.assertIn(
            "bond_management.patches.add_bond_exchange_rate_permissions.execute",
            app_hooks.after_install,
        )
        self.assertIn(
            "bond_management.patches.add_bond_exchange_rate_permissions.execute",
            app_hooks.after_migrate,
        )

    def test_exchange_rate_permissions_include_system_manager(self):
        ensure_exchange_rate_permissions()
        ensure_exchange_rate_permissions()
        permissions = frappe.qb.get_query(
            "DocPerm",
            fields=["role", "read", "write", "create", "delete"],
            filters={
                "parent": "Bond Exchange Rate",
                "role": ["in", [investor_permissions.BOND_MANAGER_ROLE, "System Manager"]],
                "permlevel": 0,
            },
            ignore_permissions=True,
        ).run(as_dict=True)

        self.assertEqual(
            {permission.role for permission in permissions},
            {
                investor_permissions.BOND_MANAGER_ROLE,
                "System Manager",
            },
        )
        for permission in permissions:
            self.assertTrue(permission.read)
            self.assertTrue(permission.write)
            self.assertTrue(permission.create)
            self.assertTrue(permission.delete)

    def test_system_manager_can_manage_exchange_rates(self):
        ensure_exchange_rate_permissions()
        email = f"{unique_name('system-manager').lower()}@example.com"
        frappe.get_doc(
            {
                "doctype": "User",
                "email": email,
                "first_name": "System Manager",
                "send_welcome_email": 0,
                "roles": [{"role": "System Manager"}],
            }
        ).insert(ignore_permissions=True)

        previous_user = frappe.session.user
        try:
            frappe.set_user(email)
            exchange_rate = make_exchange_rate()
            exchange_rate.rate = "0.0078"
            exchange_rate.save()
            exchange_rate.delete()
        finally:
            frappe.set_user(previous_user)

        self.assertFalse(frappe.db.exists("Bond Exchange Rate", exchange_rate.name))

    def test_exchange_rate_provenance_permissions_repair_only_owned_rows(self):
        managers = [investor_permissions.BOND_MANAGER_ROLE, "System Manager"]
        frappe.db.delete(
            "DocPerm",
            {"parent": "Bond Exchange Rate", "role": ["in", managers], "permlevel": 1},
        )
        unrelated = frappe.get_doc(
            {
                "doctype": "DocPerm",
                "parent": "Bond Exchange Rate",
                "parenttype": "DocType",
                "parentfield": "permissions",
                "role": investor_permissions.INVESTOR_ROLE,
                "permlevel": 2,
                "read": 1,
            }
        ).insert(ignore_permissions=True)
        unrelated_before = unrelated.reload().as_dict()

        ensure_exchange_rate_permissions()
        frappe.db.set_value(
            "DocPerm",
            {"parent": "Bond Exchange Rate", "role": "System Manager", "permlevel": 1},
            {"read": 0, "write": 1, "create": 1, "delete": 1},
            update_modified=False,
        )
        ensure_exchange_rate_permissions()
        ensure_exchange_rate_permissions()
        frappe.clear_cache(doctype="Bond Exchange Rate")

        permissions = frappe.qb.get_query(
            "DocPerm",
            fields=["role", "read", "write", "create", "delete"],
            filters={"parent": "Bond Exchange Rate", "permlevel": 1},
            ignore_permissions=True,
        ).run(as_dict=True)
        self.assertEqual(len(permissions), 2)
        self.assertEqual({permission.role for permission in permissions}, set(managers))
        for permission in permissions:
            self.assertTrue(permission.read)
            self.assertFalse(permission.write)
            self.assertFalse(permission.create)
            self.assertFalse(permission.delete)
        self.assertEqual(unrelated.reload().as_dict(), unrelated_before)
        self.assertEqual(frappe.get_meta("Bond Exchange Rate").get_field("statement").permlevel, 1)

    def test_manager_can_run_portfolio_performance_report(self):
        report = frappe.get_doc("Report", "Portfolio Performance")
        self.assertIn(investor_permissions.BOND_MANAGER_ROLE, {row.role for row in report.roles})

    def test_yield_report_permission_is_bootstrapped_on_fresh_install(self):
        self.assertIn(
            "bond_management.patches.add_bond_yield_comparison_report_permission.execute",
            app_hooks.after_install,
        )
        self.assertIn(
            "bond_management.patches.add_bond_yield_comparison_report_permission.execute",
            app_hooks.after_migrate,
        )

        ensure_yield_report_permission()
        ensure_yield_report_permission()
        permission = frappe.qb.get_query(
            "DocPerm",
            fields=["report"],
            filters={
                "parent": "Bond Market Date",
                "role": investor_permissions.INVESTOR_ROLE,
                "permlevel": 0,
            },
            ignore_permissions=True,
        ).run(as_dict=True)

        self.assertEqual(len(permission), 1)
        self.assertTrue(permission[0].report)
        report = frappe.get_doc("Report", "Bond Yield Comparison")
        self.assertIn(investor_permissions.BOND_MANAGER_ROLE, {row.role for row in report.roles})

    def test_direct_permission_check_allows_an_assigned_portfolio(self):
        with patch.object(investor_permissions, "_get_allowed_portfolios", return_value=["Nanda"]):
            self.assertTrue(
                investor_permissions._has_portfolio_access("Nanda", "investor@example.com", "read")
            )

    def test_investor_login_redirects_to_the_vue_homepage(self):
        with patch.object(frappe, "get_roles", return_value=[investor_permissions.INVESTOR_ROLE]):
            frappe.local.response = {"redirect_to": "/desk"}
            investor_permissions.redirect_investor_to_workspace(SimpleNamespace(user="investor@example.com"))

            self.assertEqual(frappe.local.response["home_page"], "/bond-investor")
            self.assertNotIn("redirect_to", frappe.local.response)
