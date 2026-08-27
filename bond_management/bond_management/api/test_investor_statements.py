from contextlib import contextmanager
from datetime import timedelta
from unittest.mock import patch

import frappe
from frappe.exceptions import FrappeTypeError
from frappe.tests import IntegrationTestCase

from bond_management.bond_management.api.investor import (
    STATEMENT_DETAIL_FIELDS,
    STATEMENT_HOLDING_FIELDS,
    STATEMENT_LIST_FIELDS,
    get_statement,
    get_statements,
)
from bond_management.bond_management.tests.factories import (
    make_bond,
    make_market_date,
    make_portfolio,
    make_statement,
    make_transaction,
    unique_name,
)
from bond_management.bond_management.utils.investor_permissions import (
    BOND_MANAGER_ROLE,
    INVESTOR_ROLE,
)
from bond_management.bond_management.utils.investor_ui import FEATURE_FLAG


class TestInvestorStatements(IntegrationTestCase):
    def test_guest_and_unapproved_role_are_rejected(self):
        with self._as_user("Guest"):
            with self.assertRaises(frappe.AuthenticationError):
                get_statements()

        unapproved_user = self._make_user([])
        with self._as_user(unapproved_user):
            with self.assertRaises(frappe.PermissionError):
                get_statements()

    def test_feature_flag_is_required(self):
        with self._as_user("Administrator", feature_enabled=False):
            with self.assertRaises(frappe.PermissionError):
                get_statements()

    def test_investor_without_assignments_gets_an_empty_page(self):
        investor = self._make_user([INVESTOR_ROLE])

        with self._as_user(investor):
            response = get_statements()

        self.assertEqual(response["data"], [])
        self.assertEqual(
            response["pagination"],
            {"start": 0, "page_length": 20, "has_more": False},
        )

    def test_list_contains_only_assigned_statements_and_exact_projection(self):
        assigned_portfolio = make_portfolio()
        other_portfolio = make_portfolio()
        assigned = make_statement(assigned_portfolio)
        other = make_statement(other_portfolio)
        frappe.db.set_value(
            "Bond Statement",
            assigned.name,
            {
                "reconciliation_status": "Matched",
                "attachment": "/private/files/assigned-statement.pdf",
                "quantity_reconciliation_report": "/private/files/assigned-reconciliation.pdf",
            },
            update_modified=False,
        )
        investor = self._make_investor(assigned_portfolio.name)

        with self._as_user(investor):
            response = get_statements(reconciliation_status="Matched")

        self.assertEqual([row.name for row in response["data"]], [assigned.name])
        self.assertNotIn(other.name, {row.name for row in response["data"]})
        self.assertEqual(set(response["data"][0]), set(STATEMENT_LIST_FIELDS))
        self.assertNotIn("attachment", response["data"][0])
        self.assertNotIn("quantity_reconciliation_report", response["data"][0])

    def test_explicit_cross_portfolio_filter_is_denied(self):
        assigned_portfolio = make_portfolio()
        other_portfolio = make_portfolio()
        investor = self._make_investor(assigned_portfolio.name)

        with self._as_user(investor):
            with self.assertRaisesRegex(frappe.PermissionError, "not permitted"):
                get_statements(portfolio=other_portfolio.name)

    def test_detail_contains_exact_visible_projection_with_pdf_attachment(self):
        bond = make_bond()
        portfolio = make_portfolio()
        market_date = make_market_date(bond, market_price=101)
        make_transaction(
            bond,
            portfolio,
            trade_date=market_date.date - timedelta(days=2),
            settlement_date=market_date.date - timedelta(days=1),
        )
        statement = make_statement(
            portfolio,
            statement_date=market_date.date,
            market_price_posting=market_date.name,
        )
        frappe.db.set_value(
            "Bond Statement",
            statement.name,
            {
                "attachment": "/private/files/investor-statement-secret.pdf",
                "quantity_reconciliation_report": ("/private/files/investor-reconciliation-secret.pdf"),
                "reconciliation_status": "Matched",
            },
            update_modified=False,
        )
        investor = self._make_investor(portfolio.name)

        with self._as_user(investor):
            response = get_statement(statement.name)

        detail = response["statement"]
        self.assertEqual(set(detail), set(STATEMENT_DETAIL_FIELDS))
        self.assertEqual(detail.portfolio_name, portfolio.name)
        self.assertEqual(detail.attachment, "/private/files/investor-statement-secret.pdf")
        self.assertEqual(
            detail.quantity_reconciliation_report,
            "/private/files/investor-reconciliation-secret.pdf",
        )
        self.assertTrue(detail.bond_statement_details)
        self.assertEqual(
            set(detail.bond_statement_details[0]),
            set(STATEMENT_HOLDING_FIELDS),
        )

    def test_unreadable_and_unknown_detail_have_the_same_failure(self):
        assigned_portfolio = make_portfolio()
        other_portfolio = make_portfolio()
        other = make_statement(other_portfolio)
        investor = self._make_investor(assigned_portfolio.name)
        messages = []

        with self._as_user(investor):
            for name in (other.name, unique_name("UNKNOWN-STATEMENT")):
                with self.assertRaises(frappe.PermissionError) as error:
                    get_statement(name)
                messages.append(str(error.exception))

        self.assertEqual(messages[0], messages[1])

    def test_manager_and_administrator_use_normal_statement_permissions(self):
        first = make_statement(make_portfolio())
        second = make_statement(make_portfolio())
        statements = {first.name, second.name}
        manager = self._make_user([BOND_MANAGER_ROLE])

        for user in (manager, "Administrator"):
            with self.subTest(user=user), self._as_user(user):
                response = get_statements()
                self.assertTrue(statements.issubset({row.name for row in response["data"]}))

    def test_filters_and_pagination_are_allow_listed_and_bounded(self):
        portfolio = make_portfolio()
        older = make_statement(portfolio, statement_date="2025-11-30")
        newer = make_statement(portfolio, statement_date="2025-12-31")
        investor = self._make_investor(portfolio.name)

        with self._as_user(investor):
            first_page = get_statements(page_length="1")
            maximum_page = get_statements(page_length="50")
            with self.assertRaisesRegex(frappe.ValidationError, "Matched or Mismatched"):
                get_statements(reconciliation_status="Pending")
            with self.assertRaisesRegex(frappe.ValidationError, "cannot exceed 50"):
                get_statements(page_length="51")
            with self.assertRaisesRegex(frappe.ValidationError, "must be at least 1"):
                get_statements(page_length="0")
            with self.assertRaisesRegex(frappe.ValidationError, "must be at least 0"):
                get_statements(start="-1")
            with self.assertRaises(FrappeTypeError):
                get_statements(start=[])
            with self.assertRaises(TypeError):
                get_statements(filters={"attachment": ["is", "set"]})

        self.assertEqual(first_page["data"][0].name, newer.name)
        self.assertNotEqual(first_page["data"][0].name, older.name)
        self.assertEqual(
            first_page["pagination"],
            {"start": 0, "page_length": 1, "has_more": True},
        )
        self.assertEqual(maximum_page["pagination"]["page_length"], 50)

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
                    "first_name": "Investor Statement Test",
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
