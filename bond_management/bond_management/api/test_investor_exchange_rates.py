from contextlib import contextmanager
from unittest.mock import patch

import frappe
from frappe.exceptions import FrappeTypeError
from frappe.tests import IntegrationTestCase

from bond_management.bond_management.api.investor import (
    EXCHANGE_RATE_DETAIL_FIELDS,
    EXCHANGE_RATE_LIST_FIELDS,
    get_exchange_rate,
    get_exchange_rates,
)
from bond_management.bond_management.tests.factories import (
    make_exchange_rate,
    make_portfolio,
    make_statement,
    unique_name,
)
from bond_management.bond_management.utils.investor_permissions import (
    BOND_MANAGER_ROLE,
    INVESTOR_ROLE,
)
from bond_management.bond_management.utils.investor_ui import FEATURE_FLAG


class TestInvestorExchangeRates(IntegrationTestCase):
    def test_guest_and_unapproved_role_are_rejected(self):
        with self._as_user("Guest"):
            with self.assertRaises(frappe.AuthenticationError):
                get_exchange_rates()

        unapproved_user = self._make_user([])
        with self._as_user(unapproved_user):
            with self.assertRaises(frappe.PermissionError):
                get_exchange_rates()

    def test_feature_flag_is_required(self):
        with self._as_user("Administrator", feature_enabled=False):
            with self.assertRaises(frappe.PermissionError):
                get_exchange_rates()

    def test_investor_without_portfolio_assignment_can_read_shared_history(self):
        exchange_rate = make_exchange_rate()
        investor = self._make_user([INVESTOR_ROLE])

        with self._as_user(investor):
            response = get_exchange_rates()

        self.assertIn(exchange_rate.name, {row.name for row in response["data"]})

    def test_list_has_exact_visible_projection(self):
        exchange_rate = make_exchange_rate()
        investor = self._make_user([INVESTOR_ROLE])

        with self._as_user(investor):
            response = get_exchange_rates()

        row = next(row for row in response["data"] if row.name == exchange_rate.name)
        self.assertEqual(set(row), set(EXCHANGE_RATE_LIST_FIELDS))
        self.assertEqual(row.from_currency, exchange_rate.from_currency)
        self.assertNotIn("source", row)
        self.assertNotIn("statement", row)
        self.assertNotIn("modified", row)

    def test_detail_has_exact_visible_projection(self):
        exchange_rate = make_exchange_rate()
        investor = self._make_user([INVESTOR_ROLE])

        with self._as_user(investor):
            response = get_exchange_rate(exchange_rate.name)

        detail = response["exchange_rate"]
        self.assertEqual(set(detail), set(EXCHANGE_RATE_DETAIL_FIELDS))
        self.assertEqual(detail.from_currency, exchange_rate.from_currency)
        self.assertEqual(detail.source, "Manual")
        self.assertIsNone(detail.statement)
        self.assertNotIn("owner", str(response))
        self.assertNotIn("modified", str(response))

    def test_detail_keeps_a_readable_statement_reference(self):
        portfolio = make_portfolio()
        exchange_rate = self._make_statement_exchange_rate(portfolio)
        investor = self._make_user([INVESTOR_ROLE])
        self._assign_user_permission(investor, "Bond Portfolio", portfolio.name)

        with self._as_user(investor):
            response = get_exchange_rate(exchange_rate.name)

        detail = response["exchange_rate"]
        self.assertEqual(detail.source, "Statement PDF")
        self.assertEqual(detail.statement, exchange_rate.statement)

    def test_detail_masks_an_unreadable_cross_portfolio_statement_reference(self):
        assigned_portfolio = make_portfolio()
        other_portfolio = make_portfolio()
        exchange_rate = self._make_statement_exchange_rate(other_portfolio)
        investor = self._make_user([INVESTOR_ROLE])
        self._assign_user_permission(investor, "Bond Portfolio", assigned_portfolio.name)

        with self._as_user(investor):
            response = get_exchange_rate(exchange_rate.name)

        detail = response["exchange_rate"]
        self.assertEqual(detail.source, "Statement PDF")
        self.assertIsNone(detail.statement)

    def test_unreadable_and_unknown_detail_have_same_failure(self):
        readable = make_exchange_rate()
        unreadable = make_exchange_rate()
        investor = self._make_user([INVESTOR_ROLE])
        self._assign_user_permission(investor, "Bond Exchange Rate", readable.name)
        messages = []

        with self._as_user(investor):
            for name in (unreadable.name, unique_name("UNKNOWN-EXCHANGE-RATE")):
                with self.assertRaises(frappe.PermissionError) as error:
                    get_exchange_rate(name)
                messages.append(str(error.exception))

        self.assertEqual(messages[0], messages[1])

    def test_manager_and_administrator_use_normal_exchange_rate_permissions(self):
        first = make_exchange_rate()
        second = make_exchange_rate()
        exchange_rates = {first.name, second.name}
        manager = self._make_user([BOND_MANAGER_ROLE])

        for user in (manager, "Administrator"):
            with self.subTest(user=user), self._as_user(user):
                response = get_exchange_rates()
                self.assertTrue(exchange_rates.issubset({row.name for row in response["data"]}))

    def test_pagination_is_allow_listed_bounded_and_sorted_by_rate_date(self):
        newer = make_exchange_rate(from_currency="EUR", rate_date="2025-01-02")
        older = make_exchange_rate(from_currency="EUR", rate_date="2025-01-01")
        investor = self._make_user([INVESTOR_ROLE])
        self._assign_user_permission(investor, "Bond Exchange Rate", older.name)
        self._assign_user_permission(investor, "Bond Exchange Rate", newer.name)

        with self._as_user(investor):
            first_page = get_exchange_rates(page_length="1")
            maximum_page = get_exchange_rates(page_length="50")
            with self.assertRaisesRegex(frappe.ValidationError, "cannot exceed 50"):
                get_exchange_rates(page_length="51")
            with self.assertRaisesRegex(frappe.ValidationError, "must be at least 1"):
                get_exchange_rates(page_length="0")
            with self.assertRaisesRegex(frappe.ValidationError, "must be at least 0"):
                get_exchange_rates(start="-1")
            with self.assertRaises(FrappeTypeError):
                get_exchange_rates(start=[])
            with self.assertRaises(TypeError):
                get_exchange_rates(filters={"from_currency": "EUR"})

        self.assertGreater(newer.rate_date, older.rate_date)
        self.assertEqual(first_page["data"][0].name, newer.name)
        self.assertEqual(
            first_page["pagination"],
            {"start": 0, "page_length": 1, "has_more": True},
        )
        self.assertEqual(maximum_page["pagination"]["page_length"], 50)

    def test_visible_columns_can_sort_and_filter_with_server_controls(self):
        older = make_exchange_rate(from_currency="CHF", rate_date="2030-01-01")
        newer = make_exchange_rate(from_currency="CHF", rate_date="2030-01-02")
        investor = self._make_user([INVESTOR_ROLE])

        with self._as_user(investor):
            ascending = get_exchange_rates(sort_by="rate_date", sort_order="asc")
            filtered = get_exchange_rates(
                filter_field="from_currency",
                filter_value="CHF",
            )
            with self.assertRaisesRegex(frappe.ValidationError, "not supported"):
                get_exchange_rates(sort_by="statement", sort_order="asc")
            with self.assertRaisesRegex(frappe.ValidationError, "Filter field"):
                get_exchange_rates(filter_field="rate_date", filter_value="2025-01-02")

        names = [row.name for row in ascending["data"]]
        self.assertLess(names.index(older.name), names.index(newer.name))
        self.assertEqual({row.name for row in filtered["data"]}, {older.name, newer.name})

    @staticmethod
    def _make_statement_exchange_rate(portfolio):
        exchange_rate = make_exchange_rate()
        statement = make_statement(portfolio, statement_date=exchange_rate.rate_date)
        exchange_rate.statement = statement.name
        exchange_rate.save()
        return exchange_rate

    @staticmethod
    def _assign_user_permission(user, allow, value):
        frappe.get_doc(
            {
                "doctype": "User Permission",
                "user": user,
                "allow": allow,
                "for_value": value,
                "apply_to_all_doctypes": 1,
            }
        ).insert(ignore_permissions=True)

    @staticmethod
    def _make_user(roles):
        return (
            frappe.get_doc(
                {
                    "doctype": "User",
                    "email": f"{unique_name('investor-exchange-rate-ui').lower()}@example.com",
                    "first_name": "Investor Exchange Rate Test",
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
