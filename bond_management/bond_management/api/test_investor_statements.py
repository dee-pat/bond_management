from datetime import timedelta

import frappe
from frappe.tests import IntegrationTestCase

from bond_management.bond_management.api.investor import get_statement, get_statements
from bond_management.bond_management.tests.factories import (
    allow_user,
    as_investor_user,
    make_assigned_investor,
    make_bond,
    make_investor_user,
    make_market_date,
    make_portfolio,
    make_statement,
    make_transaction,
    unique_name,
)
from bond_management.bond_management.tests.investor_contracts import (
    STATEMENT_DETAIL_FIELDS,
    STATEMENT_HOLDING_FIELDS,
    STATEMENT_LIST_FIELDS,
)
from bond_management.bond_management.utils.investor_permissions import (
    BOND_MANAGER_ROLE,
    INVESTOR_ROLE,
)


class TestInvestorStatements(IntegrationTestCase):
    def test_investor_without_assignments_gets_an_empty_page(self):
        investor = make_investor_user([INVESTOR_ROLE])

        with as_investor_user(investor):
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
        investor = make_assigned_investor(assigned_portfolio.name)

        with as_investor_user(investor):
            response = get_statements(reconciliation_status="Matched")

        self.assertEqual([row.name for row in response["data"]], [assigned.name])
        self.assertNotIn(other.name, {row.name for row in response["data"]})
        self.assertEqual(set(response), {"data", "pagination"})
        self.assertEqual(set(response["pagination"]), {"start", "page_length", "has_more"})
        self.assertEqual(set(response["data"][0]), set(STATEMENT_LIST_FIELDS))
        self.assertTrue(all(set(row) == set(STATEMENT_LIST_FIELDS) for row in response["data"]))
        self.assertNotIn("attachment", response["data"][0])
        self.assertNotIn("quantity_reconciliation_report", response["data"][0])

    def test_explicit_cross_portfolio_filter_is_denied(self):
        assigned_portfolio = make_portfolio()
        other_portfolio = make_portfolio()
        investor = make_assigned_investor(assigned_portfolio.name)

        with as_investor_user(investor):
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
        investor = make_assigned_investor(portfolio.name)

        with as_investor_user(investor):
            response = get_statement(statement.name)

        self.assertEqual(set(response), {"statement"})
        detail = response["statement"]
        self.assertEqual(set(detail), set(STATEMENT_DETAIL_FIELDS))
        self.assertEqual(detail.portfolio_name, portfolio.name)
        self.assertEqual(detail.attachment, "/private/files/investor-statement-secret.pdf")
        self.assertEqual(
            detail.quantity_reconciliation_report,
            "/private/files/investor-reconciliation-secret.pdf",
        )
        self.assertTrue(detail.bond_statement_details)
        for row in detail.bond_statement_details:
            self.assertEqual(set(row), set(STATEMENT_HOLDING_FIELDS))

    def test_detail_rejects_holdings_outside_bond_user_permissions(self):
        readable = make_bond()
        restricted = make_bond()
        portfolio = make_portfolio()
        make_transaction(readable, portfolio)
        readable_statement = make_statement(portfolio)
        make_transaction(restricted, portfolio, settlement_date="2026-01-01")
        statement = make_statement(portfolio, statement_date="2026-01-02")
        self.assertEqual(
            {row.isin for row in readable_statement.bond_statement_details},
            {readable.name},
        )
        self.assertEqual(
            {row.isin for row in statement.bond_statement_details},
            {readable.name, restricted.name},
        )
        investor = make_assigned_investor(portfolio.name)
        allow_user(investor, "Bond Master", readable.name)

        with as_investor_user(investor):
            response = get_statement(readable_statement.name)
            self.assertEqual(
                {row["isin"] for row in response["statement"].bond_statement_details},
                {readable.name},
            )
            with self.assertRaises(frappe.PermissionError):
                get_statement(statement.name)

    def test_unreadable_and_unknown_detail_have_the_same_failure(self):
        assigned_portfolio = make_portfolio()
        other_portfolio = make_portfolio()
        other = make_statement(other_portfolio)
        investor = make_assigned_investor(assigned_portfolio.name)
        messages = []

        with as_investor_user(investor):
            for name in (other.name, unique_name("UNKNOWN-STATEMENT")):
                with self.assertRaises(frappe.PermissionError) as error:
                    get_statement(name)
                messages.append(str(error.exception))

        self.assertEqual(messages[0], messages[1])

    def test_manager_and_administrator_use_normal_statement_permissions(self):
        first = make_statement(make_portfolio())
        second = make_statement(make_portfolio())
        statements = {first.name, second.name}
        manager = make_investor_user([BOND_MANAGER_ROLE])

        for user in (manager, "Administrator"):
            with self.subTest(user=user), as_investor_user(user):
                response = get_statements()
                self.assertTrue(statements.issubset({row.name for row in response["data"]}))

    def test_filters_and_pagination_are_allow_listed_and_bounded(self):
        portfolio = make_portfolio()
        newer = make_statement(portfolio, statement_date="2025-12-31")
        older = make_statement(portfolio, statement_date="2025-11-30")
        investor = make_assigned_investor(portfolio.name)

        with as_investor_user(investor):
            first_page = get_statements(page_length="1")
            with self.assertRaisesRegex(frappe.ValidationError, "Matched or Mismatched"):
                get_statements(reconciliation_status="Pending")

        self.assertEqual(first_page["data"][0].name, newer.name)
        self.assertNotEqual(first_page["data"][0].name, older.name)
        self.assertEqual(
            first_page["pagination"],
            {"start": 0, "page_length": 1, "has_more": True},
        )

    def test_visible_columns_can_sort_and_filter_with_server_controls(self):
        portfolio = make_portfolio()
        older = make_statement(portfolio, statement_date="2025-11-30")
        newer = make_statement(portfolio, statement_date="2025-12-31")
        investor = make_assigned_investor(portfolio.name)

        with as_investor_user(investor):
            ascending = get_statements(sort_by="statement_date", sort_order="asc")

        self.assertEqual([row.name for row in ascending["data"]], [older.name, newer.name])
