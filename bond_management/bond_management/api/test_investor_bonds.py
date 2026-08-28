from contextlib import contextmanager
from unittest.mock import patch

import frappe
from frappe.exceptions import FrappeTypeError
from frappe.tests import IntegrationTestCase

from bond_management.bond_management.api.investor import (
    BOND_COUPON_FIELDS,
    BOND_DETAIL_FIELDS,
    BOND_LIST_FIELDS,
    BOND_PRINCIPAL_FIELDS,
    get_bond,
    get_bonds,
)
from bond_management.bond_management.tests.factories import make_bond, unique_name
from bond_management.bond_management.utils.investor_permissions import (
    BOND_MANAGER_ROLE,
    INVESTOR_ROLE,
)
from bond_management.bond_management.utils.investor_ui import FEATURE_FLAG


class TestInvestorBonds(IntegrationTestCase):
    def test_guest_and_unapproved_role_are_rejected(self):
        with self._as_user("Guest"):
            with self.assertRaises(frappe.AuthenticationError):
                get_bonds()

        unapproved_user = self._make_user([])
        with self._as_user(unapproved_user):
            with self.assertRaises(frappe.PermissionError):
                get_bonds()

    def test_feature_flag_is_required(self):
        with self._as_user("Administrator", feature_enabled=False):
            with self.assertRaises(frappe.PermissionError):
                get_bonds()

    def test_investor_without_portfolio_assignment_can_read_shared_catalog(self):
        bond = make_bond()
        investor = self._make_user([INVESTOR_ROLE])

        with self._as_user(investor):
            response = get_bonds()

        self.assertIn(bond.name, {row.name for row in response["data"]})

    def test_list_has_exact_visible_projection(self):
        bond = make_bond()
        investor = self._make_user([INVESTOR_ROLE])

        with self._as_user(investor):
            response = get_bonds()

        row = next(row for row in response["data"] if row.name == bond.name)
        self.assertEqual(set(row), set(BOND_LIST_FIELDS))
        self.assertEqual(row.isin, bond.isin)
        self.assertNotIn("principal_schedule", row)
        self.assertNotIn("modified", row)

    def test_detail_has_exact_visible_projection_and_schedules(self):
        bond = make_bond(withholding_tax="15")
        investor = self._make_user([INVESTOR_ROLE])

        with self._as_user(investor):
            response = get_bond(bond.name)

        detail = response["bond"]
        self.assertEqual(set(detail), set(BOND_DETAIL_FIELDS))
        self.assertEqual(detail.isin, bond.isin)
        self.assertEqual(set(detail.principal_schedule[0]), set(BOND_PRINCIPAL_FIELDS))
        self.assertEqual(set(detail.coupon_schedule[0]), set(BOND_COUPON_FIELDS))
        self.assertNotIn("parent", str(response))
        self.assertNotIn("modified", str(response))

    def test_unreadable_and_unknown_detail_have_same_failure(self):
        readable = make_bond()
        unreadable = make_bond()
        investor = self._make_user([INVESTOR_ROLE])
        frappe.get_doc(
            {
                "doctype": "User Permission",
                "user": investor,
                "allow": "Bond Master",
                "for_value": readable.name,
                "apply_to_all_doctypes": 1,
            }
        ).insert(ignore_permissions=True)
        messages = []

        with self._as_user(investor):
            for name in (unreadable.name, unique_name("UNKNOWN-BOND")):
                with self.assertRaises(frappe.PermissionError) as error:
                    get_bond(name)
                messages.append(str(error.exception))

        self.assertEqual(messages[0], messages[1])

    def test_manager_and_administrator_use_normal_bond_permissions(self):
        first = make_bond()
        second = make_bond()
        bonds = {first.name, second.name}
        manager = self._make_user([BOND_MANAGER_ROLE])

        for user in (manager, "Administrator"):
            with self.subTest(user=user), self._as_user(user):
                response = get_bonds()
                self.assertTrue(bonds.issubset({row.name for row in response["data"]}))

    def test_pagination_is_allow_listed_and_bounded(self):
        newer = make_bond(
            issue_date="2099-01-01",
            first_coupon_date="2099-07-01",
            maturity_date="2101-01-01",
            principal_schedule=[{"repayment_date": "2101-01-01", "principal_units": 100}],
        )
        older = make_bond(
            issue_date="2098-01-01",
            first_coupon_date="2098-07-01",
            maturity_date="2100-01-01",
            principal_schedule=[{"repayment_date": "2100-01-01", "principal_units": 100}],
        )
        investor = self._make_user([INVESTOR_ROLE])

        with self._as_user(investor):
            first_page = get_bonds(page_length="1")
            maximum_page = get_bonds(page_length="50")
            with self.assertRaisesRegex(frappe.ValidationError, "cannot exceed 50"):
                get_bonds(page_length="51")
            with self.assertRaisesRegex(frappe.ValidationError, "must be at least 1"):
                get_bonds(page_length="0")
            with self.assertRaisesRegex(frappe.ValidationError, "must be at least 0"):
                get_bonds(start="-1")
            with self.assertRaises(FrappeTypeError):
                get_bonds(start=[])
            with self.assertRaises(TypeError):
                get_bonds(filters={"currency": "USD"})

        self.assertEqual(first_page["data"][0].name, newer.name)
        self.assertNotEqual(first_page["data"][0].name, older.name)
        self.assertEqual(
            first_page["pagination"],
            {"start": 0, "page_length": 1, "has_more": True},
        )
        self.assertEqual(maximum_page["pagination"]["page_length"], 50)

    def test_visible_columns_can_sort_and_filter_with_server_controls(self):
        first = make_bond(bond_name="A-" + unique_name("TEST-BOND"))
        second = make_bond(bond_name="Z-" + unique_name("TEST-BOND"))
        investor = self._make_user([INVESTOR_ROLE])

        with self._as_user(investor):
            ascending = get_bonds(sort_by="bond_name", sort_order="asc")
            filtered = get_bonds(filter_field="isin", filter_value=first.isin)
            with self.assertRaisesRegex(frappe.ValidationError, "not supported"):
                get_bonds(sort_by="principal_schedule", sort_order="asc")
            with self.assertRaisesRegex(frappe.ValidationError, "Filter field"):
                get_bonds(filter_field="issue_date", filter_value="2099-01-01")

        names = [row.name for row in ascending["data"]]
        self.assertLess(names.index(first.name), names.index(second.name))
        self.assertEqual([row.name for row in filtered["data"]], [first.name])

    @staticmethod
    def _make_user(roles):
        return (
            frappe.get_doc(
                {
                    "doctype": "User",
                    "email": f"{unique_name('investor-bond-ui').lower()}@example.com",
                    "first_name": "Investor Bond Test",
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
