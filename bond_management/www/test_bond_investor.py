from contextlib import contextmanager
from unittest.mock import patch

import frappe
from frappe.tests import IntegrationTestCase

from bond_management.bond_management.tests.factories import unique_name
from bond_management.bond_management.utils.investor_permissions import (
    BOND_MANAGER_ROLE,
    INVESTOR_ROLE,
)
from bond_management.bond_management.utils.investor_ui import FEATURE_FLAG
from bond_management.www import bond_investor


class TestBondInvestorWebsite(IntegrationTestCase):
    def test_disabled_site_redirects_to_the_legacy_workspace(self):
        with patch.dict(frappe.conf, {FEATURE_FLAG: 0}):
            with self.assertRaises(frappe.Redirect) as redirect:
                bond_investor.get_context(frappe._dict())

        self.assertEqual(frappe.flags.redirect_location, "/desk/bond-investor")
        self.assertEqual(redirect.exception.http_status_code, 302)

    def test_guest_is_temporarily_redirected_to_login(self):
        previous_user = frappe.session.user
        try:
            frappe.set_user("Guest")
            with patch.dict(frappe.conf, {FEATURE_FLAG: 1}):
                with self.assertRaises(frappe.Redirect) as redirect:
                    bond_investor.get_context(frappe._dict())
        finally:
            frappe.set_user(previous_user)

        self.assertEqual(
            frappe.flags.redirect_location,
            "/login?redirect-to=%2Fbond-investor",
        )
        self.assertEqual(redirect.exception.http_status_code, 302)

    def test_enabled_site_embeds_only_minimum_support_context(self):
        previous_user = frappe.session.user
        try:
            frappe.set_user("Administrator")
            with patch.dict(frappe.conf, {FEATURE_FLAG: 1}):
                context = bond_investor.get_context(frappe._dict())
        finally:
            frappe.set_user(previous_user)

        self.assertEqual(
            set(context["boot"]),
            {"csrf_token", "bond_investor"},
        )
        self.assertTrue(context["boot"]["bond_investor"]["is_support"])
        self.assertNotIn("portfolios", context["boot"]["bond_investor"])

    def test_enabled_site_rejects_an_authenticated_user_without_an_allowed_role(self):
        user = self._make_user([])

        with self._as_user(user):
            with patch.dict(frappe.conf, {FEATURE_FLAG: 1}):
                with self.assertRaises(frappe.PermissionError):
                    bond_investor.get_context(frappe._dict())

    def test_enabled_site_allows_an_investor(self):
        user = self._make_user([INVESTOR_ROLE])

        with self._as_user(user):
            with patch.dict(frappe.conf, {FEATURE_FLAG: 1}):
                context = bond_investor.get_context(frappe._dict())

        self.assertTrue(context["boot"]["bond_investor"]["is_investor"])
        self.assertFalse(context["boot"]["bond_investor"]["is_support"])

    def test_enabled_site_allows_a_manager(self):
        user = self._make_user([BOND_MANAGER_ROLE])

        with self._as_user(user):
            with patch.dict(frappe.conf, {FEATURE_FLAG: 1}):
                context = bond_investor.get_context(frappe._dict())

        self.assertFalse(context["boot"]["bond_investor"]["is_investor"])
        self.assertTrue(context["boot"]["bond_investor"]["is_support"])

    @staticmethod
    def _make_user(roles):
        return frappe.get_doc(
            {
                "doctype": "User",
                "email": f"{unique_name('investor-route').lower()}@example.com",
                "first_name": "Investor Route Test",
                "send_welcome_email": 0,
                "roles": [{"role": role} for role in roles],
            }
        ).insert(ignore_permissions=True).name

    @staticmethod
    @contextmanager
    def _as_user(user):
        previous_user = frappe.session.user
        try:
            frappe.set_user(user)
            yield
        finally:
            frappe.set_user(previous_user)
