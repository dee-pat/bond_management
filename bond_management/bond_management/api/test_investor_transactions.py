from contextlib import contextmanager
from unittest.mock import patch

import frappe
from frappe.exceptions import FrappeTypeError
from frappe.tests import IntegrationTestCase

from bond_management.bond_management.api.investor import (
    TRANSACTION_DETAIL_FIELDS,
    TRANSACTION_LIST_FIELDS,
    get_transaction,
    get_transactions,
)
from bond_management.bond_management.tests.factories import (
    make_bond,
    make_portfolio,
    make_transaction,
    unique_name,
)
from bond_management.bond_management.utils.investor_permissions import (
    BOND_MANAGER_ROLE,
    INVESTOR_ROLE,
)
from bond_management.bond_management.utils.investor_ui import FEATURE_FLAG


class TestInvestorTransactions(IntegrationTestCase):
    def test_guest_and_unapproved_role_are_rejected(self):
        with self._as_user("Guest"):
            with self.assertRaises(frappe.AuthenticationError):
                get_transactions()

        unapproved_user = self._make_user([])
        with self._as_user(unapproved_user):
            with self.assertRaises(frappe.PermissionError):
                get_transactions()

    def test_feature_flag_is_required(self):
        with self._as_user("Administrator", feature_enabled=False):
            with self.assertRaises(frappe.PermissionError):
                get_transactions()

    def test_investor_without_assignments_gets_an_empty_page(self):
        investor = self._make_user([INVESTOR_ROLE])

        with self._as_user(investor):
            response = get_transactions()

        self.assertEqual(response["data"], [])
        self.assertEqual(
            response["pagination"],
            {"start": 0, "page_length": 20, "has_more": False},
        )

    def test_list_contains_only_assigned_transactions_and_exact_projection(self):
        bond = make_bond()
        assigned_portfolio = make_portfolio()
        other_portfolio = make_portfolio()
        assigned = make_transaction(bond, assigned_portfolio)
        other = make_transaction(bond, other_portfolio)
        frappe.db.set_value(
            "Bond Transaction",
            assigned.name,
            "attachment",
            "/private/files/assigned-transaction.pdf",
            update_modified=False,
        )
        investor = self._make_investor(assigned_portfolio.name)

        with self._as_user(investor):
            response = get_transactions()

        self.assertEqual([row.name for row in response["data"]], [assigned.name])
        self.assertNotIn(other.name, {row.name for row in response["data"]})
        self.assertEqual(set(response["data"][0]), set(TRANSACTION_LIST_FIELDS))
        self.assertNotIn("attachment", response["data"][0])

    def test_explicit_cross_portfolio_filter_is_denied(self):
        assigned_portfolio = make_portfolio()
        other_portfolio = make_portfolio()
        investor = self._make_investor(assigned_portfolio.name)

        with self._as_user(investor):
            with self.assertRaisesRegex(frappe.PermissionError, "not permitted"):
                get_transactions(portfolio=other_portfolio.name)

    def test_detail_contains_exact_visible_projection_with_attachment(self):
        bond = make_bond()
        portfolio = make_portfolio()
        transaction = make_transaction(bond, portfolio)
        frappe.db.set_value(
            "Bond Transaction",
            transaction.name,
            "attachment",
            "/private/files/investor-secret.pdf",
            update_modified=False,
        )
        investor = self._make_investor(portfolio.name)

        with self._as_user(investor):
            response = get_transaction(transaction.name)

        detail = response["transaction"]
        self.assertEqual(set(detail), set(TRANSACTION_DETAIL_FIELDS))
        self.assertEqual(detail.transaction_reference, transaction.name)
        self.assertEqual(detail.attachment, "/private/files/investor-secret.pdf")
        self.assertNotIn("attachment_portfolio_override", detail)

    def test_unreadable_and_unknown_detail_have_the_same_failure(self):
        bond = make_bond()
        assigned_portfolio = make_portfolio()
        other_portfolio = make_portfolio()
        other = make_transaction(bond, other_portfolio)
        investor = self._make_investor(assigned_portfolio.name)
        messages = []

        with self._as_user(investor):
            for name in (other.name, unique_name("UNKNOWN-TRANSACTION")):
                with self.assertRaises(frappe.PermissionError) as error:
                    get_transaction(name)
                messages.append(str(error.exception))

        self.assertEqual(messages[0], messages[1])

    def test_manager_and_administrator_use_normal_transaction_permissions(self):
        bond = make_bond()
        first_portfolio = make_portfolio()
        second_portfolio = make_portfolio()
        transactions = {
            make_transaction(bond, first_portfolio).name,
            make_transaction(bond, second_portfolio).name,
        }
        manager = self._make_user([BOND_MANAGER_ROLE])

        for user in (manager, "Administrator"):
            with self.subTest(user=user), self._as_user(user):
                response = get_transactions()
                self.assertTrue(transactions.issubset({row.name for row in response["data"]}))

    def test_pagination_is_bounded_and_reports_more_rows(self):
        bond = make_bond()
        portfolio = make_portfolio()
        older = make_transaction(bond, portfolio)
        newer = make_transaction(bond, portfolio)
        investor = self._make_investor(portfolio.name)

        with self._as_user(investor):
            first_page = get_transactions(page_length="1")
            maximum_page = get_transactions(page_length="50")
            with self.assertRaisesRegex(frappe.ValidationError, "cannot exceed 50"):
                get_transactions(page_length="51")
            with self.assertRaisesRegex(frappe.ValidationError, "must be at least 1"):
                get_transactions(page_length="0")
            with self.assertRaisesRegex(frappe.ValidationError, "must be at least 0"):
                get_transactions(start="-1")
            with self.assertRaises(FrappeTypeError):
                get_transactions(start=[])

        self.assertEqual(first_page["data"][0].name, newer.name)
        self.assertNotEqual(first_page["data"][0].name, older.name)
        self.assertEqual(
            first_page["pagination"],
            {"start": 0, "page_length": 1, "has_more": True},
        )
        self.assertEqual(maximum_page["pagination"]["page_length"], 50)

    def test_arbitrary_filters_are_not_accepted(self):
        investor = self._make_user([INVESTOR_ROLE])

        with self._as_user(investor):
            with self.assertRaises(TypeError):
                get_transactions(filters={"attachment": ["is", "set"]})

    def _make_investor(self, portfolio_name):
        investor = self._make_user([INVESTOR_ROLE])
        frappe.get_doc(
            {
                "doctype": "User Permission",
                "user": investor,
                "allow": "Bond Portfolio",
                "for_value": portfolio_name,
                "apply_to_all_doctypes": 1,
            }
        ).insert(ignore_permissions=True)
        return investor

    @staticmethod
    def _make_user(roles):
        return (
            frappe.get_doc(
                {
                    "doctype": "User",
                    "email": f"{unique_name('investor-ui').lower()}@example.com",
                    "first_name": "Investor Transaction Test",
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
