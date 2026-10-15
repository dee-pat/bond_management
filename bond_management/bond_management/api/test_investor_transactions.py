import frappe
from frappe.exceptions import FrappeTypeError
from frappe.tests import IntegrationTestCase

from bond_management.bond_management.api.investor import get_transaction, get_transactions
from bond_management.bond_management.tests.factories import (
    as_investor_user,
    make_assigned_investor,
    make_bond,
    make_investor_user,
    make_portfolio,
    make_transaction,
    unique_name,
)
from bond_management.bond_management.tests.investor_contracts import (
    TRANSACTION_DETAIL_FIELDS,
    TRANSACTION_LIST_FIELDS,
)
from bond_management.bond_management.utils.investor_permissions import (
    BOND_MANAGER_ROLE,
    INVESTOR_ROLE,
)


class TestInvestorTransactions(IntegrationTestCase):
    def test_investor_without_assignments_gets_an_empty_page(self):
        investor = make_investor_user([INVESTOR_ROLE])

        with as_investor_user(investor):
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
        investor = make_assigned_investor(assigned_portfolio.name)

        with as_investor_user(investor):
            response = get_transactions()

        self.assertEqual([row.name for row in response["data"]], [assigned.name])
        self.assertNotIn(other.name, {row.name for row in response["data"]})
        self.assertEqual(set(response), {"data", "pagination"})
        self.assertEqual(set(response["pagination"]), {"start", "page_length", "has_more"})
        self.assertEqual(set(response["data"][0]), set(TRANSACTION_LIST_FIELDS))
        self.assertTrue(all(set(row) == set(TRANSACTION_LIST_FIELDS) for row in response["data"]))
        self.assertNotIn("attachment", response["data"][0])

    def test_explicit_cross_portfolio_filter_is_denied(self):
        assigned_portfolio = make_portfolio()
        other_portfolio = make_portfolio()
        investor = make_assigned_investor(assigned_portfolio.name)

        with as_investor_user(investor):
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
        investor = make_assigned_investor(portfolio.name)

        with as_investor_user(investor):
            response = get_transaction(transaction.name)

        self.assertEqual(set(response), {"transaction"})
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
        investor = make_assigned_investor(assigned_portfolio.name)
        messages = []

        with as_investor_user(investor):
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
        manager = make_investor_user([BOND_MANAGER_ROLE])

        for user in (manager, "Administrator"):
            with self.subTest(user=user), as_investor_user(user):
                response = get_transactions()
                self.assertTrue(transactions.issubset({row.name for row in response["data"]}))

    def test_pagination_is_bounded_and_reports_more_rows(self):
        bond = make_bond()
        portfolio = make_portfolio()
        newer = make_transaction(bond, portfolio, settlement_date="2025-12-31")
        older = make_transaction(bond, portfolio, settlement_date="2025-12-30")
        investor = make_assigned_investor(portfolio.name)

        with as_investor_user(investor):
            first_page = get_transactions(page_length="1")

        self.assertEqual(first_page["data"][0].name, newer.name)
        self.assertNotEqual(first_page["data"][0].name, older.name)
        self.assertEqual(
            first_page["pagination"],
            {"start": 0, "page_length": 1, "has_more": True},
        )

    def test_visible_columns_can_sort_and_filter_with_server_controls(self):
        bond = make_bond()
        portfolio = make_portfolio()
        older = make_transaction(bond, portfolio, settlement_date="2025-12-30")
        newer = make_transaction(bond, portfolio, settlement_date="2025-12-31")
        investor = make_assigned_investor(portfolio.name)

        with as_investor_user(investor):
            ascending = get_transactions(
                sort_by="settlement_date",
                sort_order="asc",
            )
            filtered = get_transactions(
                filter_field="isin",
                filter_value=bond.name,
            )

        self.assertEqual([row.name for row in ascending["data"]], [older.name, newer.name])
        self.assertEqual({row.name for row in filtered["data"]}, {older.name, newer.name})
