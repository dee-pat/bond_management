from types import SimpleNamespace
from unittest.mock import patch

import frappe
from frappe.core.doctype.file.utils import find_file_by_url
from frappe.tests import IntegrationTestCase

from bond_management import hooks as app_hooks
from bond_management.bond_management.report.portfolio_performance.portfolio_performance import (
    validate_report_inputs,
)
from bond_management.bond_management.tests.factories import (
    allow_user,
    make_assigned_investor,
    make_bond,
    make_exchange_rate,
    make_portfolio,
    make_transaction,
    make_user,
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
    def setUp(self):
        # Several tests mock the role and assignment queries for fixed users.
        frappe.db.value_cache.clear()

    def test_cached_investor_scope_follows_role_and_assignment_saves(self):
        assigned = make_portfolio()
        user = make_user()

        self.assertIsNone(investor_permissions.get_allowed_portfolios(user.name))

        user.add_roles(investor_permissions.INVESTOR_ROLE)
        self.assertEqual(investor_permissions.get_allowed_portfolios(user.name), [])

        assignment = allow_user(user.name, "Bond Portfolio", assigned.name)
        allowed = investor_permissions.get_allowed_portfolios(user.name)
        self.assertEqual(allowed, [assigned.name])

        allowed.append("Mutated")
        self.assertEqual(investor_permissions.get_allowed_portfolios(user.name), [assigned.name])

        assignment.delete(ignore_permissions=True)
        self.assertEqual(investor_permissions.get_allowed_portfolios(user.name), [])

    def test_file_query_condition_is_registered_and_preserves_file_owner_and_share_access(self):
        self.assertEqual(
            app_hooks.permission_query_conditions["File"],
            "bond_management.bond_management.utils.investor_permissions.file_query_condition",
        )

        with (
            patch.object(investor_permissions, "get_allowed_portfolios", return_value=[]),
            patch.object(investor_permissions.frappe.db, "escape", side_effect=lambda value: f"'{value}'"),
        ):
            condition = investor_permissions.file_query_condition("investor@example.com")

        self.assertIn("`tabFile`.`is_private` = 0", condition)
        self.assertIn("`tabFile`.`owner` = 'investor@example.com'", condition)
        self.assertIn("`tabDocShare`.`share_name` = `tabFile`.`name`", condition)
        self.assertIn("`tabDocShare`.`everyone` = 1", condition)
        self.assertIn(
            "COALESCE(`tabFile`.`attached_to_doctype`, '') NOT IN "
            "('Bond Portfolio', 'Bond Transaction', 'Bond Statement')",
            condition,
        )
        self.assertIn("OR (1=0)", condition)

    def test_file_share_cannot_expose_unassigned_portfolio_attachment(self):
        assigned_portfolio = make_portfolio()
        other_portfolio = make_portfolio()
        bond = make_bond()
        other_transaction = make_transaction(bond, other_portfolio)
        assigned_file = self._make_private_file("Bond Portfolio", assigned_portfolio.name)
        other_files = [
            self._make_private_file("Bond Portfolio", other_portfolio.name),
            self._make_private_file("Bond Transaction", other_transaction.name),
        ]
        unrelated_file = self._make_private_file("User", "Administrator")
        email = make_assigned_investor(assigned_portfolio.name)
        frappe.share.add("File", unrelated_file.name, email, read=1)
        for file in other_files:
            with self.assertRaises(frappe.PermissionError):
                frappe.share.add("File", file.name, email, read=1)
            with self.assertRaises(frappe.PermissionError):
                frappe.share.add("File", file.name, everyone=1, read=1)
            # Legacy shares predate the share validation.
            frappe.get_doc(
                {
                    "doctype": "DocShare",
                    "share_doctype": "File",
                    "share_name": file.name,
                    "user": email,
                    "read": 1,
                }
            ).db_insert()

        with self.set_user(email):
            with self.assertRaises(frappe.PermissionError):
                frappe.qb.get_query("File", fields=["name"], ignore_permissions=False).run()

            self.assertTrue(frappe.get_doc("File", unrelated_file.name).is_downloadable())
            self.assertEqual(
                find_file_by_url(assigned_file.file_url, name=assigned_file.name).name, assigned_file.name
            )
            for file in other_files:
                with self.subTest(attached_to=file.attached_to_doctype):
                    with self.assertRaises(frappe.PermissionError):
                        frappe.get_doc("File", file.name).check_permission("read")
                    self.assertFalse(frappe.get_doc("File", file.name).is_downloadable())
                    self.assertIsNone(find_file_by_url(file.file_url, name=file.name))

        frappe.db.delete(
            "DocShare", {"share_doctype": "File", "share_name": ["in", [f.name for f in other_files]]}
        )
        with self.set_user(email):
            visible_files = frappe.qb.get_query("File", fields=["name"], ignore_permissions=False).run(
                pluck=True
            )
        self.assertIn(assigned_file.name, visible_files)
        self.assertIn(unrelated_file.name, visible_files)
        self.assertTrue(set(visible_files).isdisjoint(file.name for file in other_files))

    def test_investor_file_list_is_limited_to_assigned_portfolio_attachments(self):
        portfolio = make_portfolio()
        bond = make_bond()
        transaction = make_transaction(bond, portfolio)
        assigned_file = self._make_private_file("Bond Transaction", transaction.name)
        unrelated_file = self._make_private_file("User", "Administrator")
        unattached_file = self._make_private_file(None, None)
        email = make_assigned_investor(portfolio.name)

        with self.set_user(email):
            visible_files = frappe.qb.get_query(
                "File",
                fields=["name"],
                ignore_permissions=False,
            ).run(pluck=True)

            self.assertIn(assigned_file.name, visible_files)
            self.assertNotIn(unrelated_file.name, visible_files)
            self.assertNotIn(unattached_file.name, visible_files)

    @staticmethod
    def _make_private_file(attached_to_doctype, attached_to_name):
        filename = f"{unique_name('private-attachment')}.txt"
        return frappe.get_doc(
            {
                "doctype": "File",
                "file_name": filename,
                "file_url": f"/private/files/{filename}",
                "content": b"private test attachment",
                "is_private": 1,
                "attached_to_doctype": attached_to_doctype,
                "attached_to_name": attached_to_name,
            }
        ).insert(ignore_permissions=True)

    def test_real_user_permissions_isolate_lists_documents_and_reports(self):
        assigned_portfolio = make_portfolio()
        other_portfolio = make_portfolio()
        bond = make_bond()
        assigned_transaction = make_transaction(bond, assigned_portfolio)
        other_transaction = make_transaction(bond, other_portfolio)
        email = make_assigned_investor(assigned_portfolio.name)

        with self.set_user(email):
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

    def test_legacy_share_cannot_override_investor_report_or_list_scope(self):
        assigned_portfolio = make_portfolio()
        other_portfolio = make_portfolio()
        email = make_assigned_investor(assigned_portfolio.name)
        frappe.get_doc(
            {
                "doctype": "DocShare",
                "name": unique_name("legacy-share"),
                "share_doctype": "Bond Portfolio",
                "share_name": other_portfolio.name,
                "user": email,
                "read": 1,
                "owner": "Administrator",
            }
        ).db_insert()

        with self.set_user(email):
            with self.assertRaises(frappe.PermissionError):
                frappe.has_permission("Bond Portfolio", "read", doc=other_portfolio.name)
            with self.assertRaises(frappe.PermissionError):
                validate_report_inputs(other_portfolio.name, "2025-12-31")
            with self.assertRaises(frappe.PermissionError):
                frappe.qb.get_query("Bond Portfolio", fields=["name"], ignore_permissions=False).run(
                    pluck=True
                )

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
            patch.object(investor_permissions, "is_investor_user", return_value=True),
            patch.object(investor_permissions.frappe.qb, "get_query") as get_query,
            patch.object(investor_permissions, "_reject_incompatible_shared_documents"),
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
            patch.object(investor_permissions, "is_investor_user", return_value=True),
            patch.object(investor_permissions.frappe.qb, "get_query") as get_query,
            patch.object(investor_permissions.frappe.db, "escape", side_effect=lambda value: f"'{value}'"),
            patch.object(investor_permissions, "_reject_incompatible_shared_documents"),
        ):
            get_query.return_value.run.return_value = ["Nanda Portfolio", "Joint Portfolio"]

            self.assertEqual(
                investor_permissions.statement_query_condition("investor@example.com"),
                "`tabBond Statement`.`portfolio_name` in ('Nanda Portfolio', 'Joint Portfolio')",
            )

    def test_non_investor_uses_the_standard_permission_model(self):
        with patch.object(investor_permissions, "is_investor_user", return_value=False):
            self.assertIsNone(investor_permissions.portfolio_query_condition("manager@example.com"))
            self.assertTrue(
                investor_permissions.has_portfolio_permission(
                    SimpleNamespace(name="Nanda"),
                    "manager@example.com",
                    "read",
                )
            )

    def test_investor_permission_hook_denies_unassigned_portfolio(self):
        with patch.object(investor_permissions, "get_allowed_portfolios", return_value=["Other"]):
            with self.assertRaises(frappe.PermissionError):
                investor_permissions.has_transaction_permission(
                    SimpleNamespace(portfolio_name="Nanda"),
                    "investor@example.com",
                    "read",
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
        email = make_user(["System Manager"]).name

        with self.set_user(email):
            exchange_rate = make_exchange_rate()
            exchange_rate.rate = "0.0078"
            exchange_rate.save()
            exchange_rate.delete()

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
        with patch.object(investor_permissions, "get_allowed_portfolios", return_value=["Nanda"]):
            self.assertTrue(
                investor_permissions._has_portfolio_access("Nanda", "investor@example.com", "read")
            )

    def test_investor_login_redirects_to_the_vue_homepage(self):
        with patch.object(frappe, "get_roles", return_value=[investor_permissions.INVESTOR_ROLE]):
            frappe.local.response = {"redirect_to": "/desk"}
            investor_permissions.redirect_investor_to_workspace(SimpleNamespace(user="investor@example.com"))

            self.assertEqual(frappe.local.response["home_page"], "/bond-investor")
            self.assertNotIn("redirect_to", frappe.local.response)
