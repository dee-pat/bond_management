from unittest.mock import patch

import frappe
from frappe.tests import IntegrationTestCase

from bond_management.bond_management.api.investor import get_bootstrap
from bond_management.bond_management.tests.factories import make_portfolio, unique_name
from bond_management.bond_management.utils.investor_permissions import (
    BOND_MANAGER_ROLE,
    INVESTOR_ROLE,
)
from bond_management.bond_management.utils.investor_ui import FEATURE_FLAG


class TestInvestorBootstrap(IntegrationTestCase):
    def test_guest_is_rejected(self):
        previous_user = frappe.session.user
        try:
            frappe.set_user("Guest")
            with self.assertRaises(frappe.AuthenticationError):
                get_bootstrap()
        finally:
            frappe.set_user(previous_user)

    def test_feature_flag_is_required(self):
        previous_user = frappe.session.user
        try:
            frappe.set_user("Administrator")
            with patch.dict(frappe.conf, {FEATURE_FLAG: 0}):
                with self.assertRaises(frappe.PermissionError):
                    get_bootstrap()
        finally:
            frappe.set_user(previous_user)

    def test_user_without_an_allowed_role_is_rejected(self):
        email = self._make_user([])
        previous_user = frappe.session.user
        try:
            frappe.set_user(email)
            with patch.dict(frappe.conf, {FEATURE_FLAG: 1}):
                with self.assertRaises(frappe.PermissionError):
                    get_bootstrap()
        finally:
            frappe.set_user(previous_user)

    def test_investor_bootstrap_contains_only_assigned_portfolios(self):
        assigned = make_portfolio()
        unassigned = make_portfolio()
        email = self._make_user([INVESTOR_ROLE])
        frappe.get_doc(
            {
                "doctype": "User Permission",
                "user": email,
                "allow": "Bond Portfolio",
                "for_value": assigned.name,
                "apply_to_all_doctypes": 1,
            }
        ).insert(ignore_permissions=True)

        previous_user = frappe.session.user
        try:
            frappe.set_user(email)
            with patch.dict(frappe.conf, {FEATURE_FLAG: 1}):
                response = get_bootstrap()
        finally:
            frappe.set_user(previous_user)

        self.assertEqual([row["name"] for row in response["portfolios"]], [assigned.name])
        self.assertNotIn(unassigned.name, {row["name"] for row in response["portfolios"]})
        self.assertEqual(
            set(response),
            {"feature_enabled", "user", "is_investor", "is_support", "portfolios"},
        )
        self.assertEqual(set(response["portfolios"][0]), {"name", "label"})
        self.assertNotIn("account_no", response["portfolios"][0])

    def test_investor_without_assignment_gets_an_empty_bootstrap(self):
        email = self._make_user([INVESTOR_ROLE])
        previous_user = frappe.session.user
        try:
            frappe.set_user(email)
            with patch.dict(frappe.conf, {FEATURE_FLAG: 1}):
                response = get_bootstrap()
        finally:
            frappe.set_user(previous_user)

        self.assertEqual(response["portfolios"], [])

    def test_administrator_and_manager_use_normal_portfolio_permissions(self):
        portfolio = make_portfolio()
        manager = self._make_user([BOND_MANAGER_ROLE])

        previous_user = frappe.session.user
        try:
            frappe.set_user(manager)
            with patch.dict(frappe.conf, {FEATURE_FLAG: 1}):
                response = get_bootstrap()
        finally:
            frappe.set_user(previous_user)

        self.assertIn(portfolio.name, {row["name"] for row in response["portfolios"]})
        self.assertTrue(response["is_support"])

    @staticmethod
    def _make_user(roles):
        return (
            frappe.get_doc(
                {
                    "doctype": "User",
                    "email": f"{unique_name('investor-ui').lower()}@example.com",
                    "first_name": "Investor UI Test",
                    "send_welcome_email": 0,
                    "roles": [{"role": role} for role in roles],
                }
            )
            .insert(ignore_permissions=True)
            .name
        )
