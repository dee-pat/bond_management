from contextlib import contextmanager
from unittest.mock import patch

import frappe
from frappe.exceptions import FrappeTypeError
from frappe.tests import IntegrationTestCase

from bond_management.bond_management.api.investor import (
    MARKET_DATE_DETAIL_FIELDS,
    MARKET_DATE_LIST_FIELDS,
    MARKET_PRICE_FIELDS,
    get_market_date,
    get_market_dates,
)
from bond_management.bond_management.tests.factories import make_bond, make_market_date, unique_name
from bond_management.bond_management.utils.investor_permissions import (
    BOND_MANAGER_ROLE,
    INVESTOR_ROLE,
)
from bond_management.bond_management.utils.investor_ui import FEATURE_FLAG


class TestInvestorMarketDates(IntegrationTestCase):
    def test_guest_and_unapproved_role_are_rejected(self):
        with self._as_user("Guest"):
            with self.assertRaises(frappe.AuthenticationError):
                get_market_dates()

        unapproved_user = self._make_user([])
        with self._as_user(unapproved_user):
            with self.assertRaises(frappe.PermissionError):
                get_market_dates()

    def test_feature_flag_is_required(self):
        with self._as_user("Administrator", feature_enabled=False):
            with self.assertRaises(frappe.PermissionError):
                get_market_dates()

    def test_investor_without_portfolio_assignment_can_read_shared_history(self):
        market_date = make_market_date(make_bond())
        investor = self._make_user([INVESTOR_ROLE])

        with self._as_user(investor):
            response = get_market_dates()

        self.assertIn(market_date.name, {row.name for row in response["data"]})

    def test_list_has_exact_visible_projection(self):
        market_date = make_market_date(make_bond())
        investor = self._make_user([INVESTOR_ROLE])

        with self._as_user(investor):
            response = get_market_dates()

        row = next(row for row in response["data"] if row.name == market_date.name)
        self.assertEqual(set(row), set(MARKET_DATE_LIST_FIELDS))
        self.assertEqual(row.date, market_date.date)
        self.assertNotIn("bond_market_prices", row)
        self.assertNotIn("modified", row)

    def test_detail_has_exact_visible_projection_and_chart_coordinates(self):
        market_date = make_market_date(make_bond(), market_price=103.25)
        investor = self._make_user([INVESTOR_ROLE])

        with self._as_user(investor):
            response = get_market_date(market_date.name)

        detail = response["market_date"]
        self.assertEqual(set(detail), set(MARKET_DATE_DETAIL_FIELDS))
        self.assertEqual(detail.date, market_date.date)
        self.assertEqual(set(detail.bond_market_prices[0]), set(MARKET_PRICE_FIELDS))
        self.assertIsNotNone(detail.bond_market_prices[0]["future_xirr"])
        self.assertIsNotNone(detail.bond_market_prices[0]["weighted_avg_repayment_years"])
        self.assertNotIn("parent", str(response))
        self.assertNotIn("modified", str(response))

    def test_unreadable_and_unknown_detail_have_same_failure(self):
        readable = make_market_date(make_bond())
        unreadable = make_market_date(make_bond())
        investor = self._make_user([INVESTOR_ROLE])
        frappe.get_doc(
            {
                "doctype": "User Permission",
                "user": investor,
                "allow": "Bond Market Date",
                "for_value": readable.name,
                "apply_to_all_doctypes": 1,
            }
        ).insert(ignore_permissions=True)
        messages = []

        with self._as_user(investor):
            for name in (unreadable.name, unique_name("UNKNOWN-MARKET-DATE")):
                with self.assertRaises(frappe.PermissionError) as error:
                    get_market_date(name)
                messages.append(str(error.exception))

        self.assertEqual(messages[0], messages[1])

    def test_manager_and_administrator_use_normal_market_date_permissions(self):
        first = make_market_date(make_bond())
        second = make_market_date(make_bond())
        market_dates = {first.name, second.name}
        manager = self._make_user([BOND_MANAGER_ROLE])

        for user in (manager, "Administrator"):
            with self.subTest(user=user), self._as_user(user):
                response = get_market_dates()
                self.assertTrue(market_dates.issubset({row.name for row in response["data"]}))

    def test_pagination_is_allow_listed_and_bounded(self):
        newer = make_market_date(make_bond(), date="2099-06-02")
        older = make_market_date(make_bond(), date="2099-06-01")
        investor = self._make_user([INVESTOR_ROLE])

        with self._as_user(investor):
            first_page = get_market_dates(page_length="1")
            maximum_page = get_market_dates(page_length="50")
            with self.assertRaisesRegex(frappe.ValidationError, "cannot exceed 50"):
                get_market_dates(page_length="51")
            with self.assertRaisesRegex(frappe.ValidationError, "must be at least 1"):
                get_market_dates(page_length="0")
            with self.assertRaisesRegex(frappe.ValidationError, "must be at least 0"):
                get_market_dates(start="-1")
            with self.assertRaises(FrappeTypeError):
                get_market_dates(start=[])
            with self.assertRaises(TypeError):
                get_market_dates(filters={"date": "2025-01-01"})

        self.assertEqual(first_page["data"][0].name, newer.name)
        self.assertNotEqual(first_page["data"][0].name, older.name)
        self.assertEqual(
            first_page["pagination"],
            {"start": 0, "page_length": 1, "has_more": True},
        )
        self.assertEqual(maximum_page["pagination"]["page_length"], 50)

    def test_visible_columns_can_sort_and_filter_with_server_controls(self):
        older = make_market_date(make_bond(), date="2030-01-01")
        newer = make_market_date(make_bond(), date="2030-01-02")
        investor = self._make_user([INVESTOR_ROLE])

        with self._as_user(investor):
            ascending = get_market_dates(sort_by="date", sort_order="asc")
            with self.assertRaisesRegex(frappe.ValidationError, "not supported"):
                get_market_dates(sort_by="bond_market_prices", sort_order="asc")
            with self.assertRaisesRegex(frappe.ValidationError, "Filter field"):
                get_market_dates(filter_field="date", filter_value="2030-01-01")

        names = [row.name for row in ascending["data"]]
        self.assertLess(names.index(older.name), names.index(newer.name))

    @staticmethod
    def _make_user(roles):
        return (
            frappe.get_doc(
                {
                    "doctype": "User",
                    "email": f"{unique_name('investor-market-date-ui').lower()}@example.com",
                    "first_name": "Investor Market Date Test",
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
