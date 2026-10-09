from decimal import Decimal

import frappe
from frappe.tests import IntegrationTestCase

from bond_management.bond_management.report.interest_difference_by_portfolio.interest_difference_by_portfolio import (
    execute,
    get_columns,
)
from bond_management.bond_management.tests.factories import (
    make_bond,
    make_portfolio,
    make_transaction,
    unique_name,
)
from bond_management.bond_management.utils.investor_permissions import INVESTOR_ROLE


class TestInterestDifferenceByPortfolio(IntegrationTestCase):
    def test_report_shows_signed_differences_and_portfolio_currency_totals(self):
        portfolio = make_portfolio()
        usd_bond = make_bond(currency="USD")
        kes_bond = make_bond(currency="KES")
        expected = {}
        for transaction_type, charged, calculated, difference in (
            ("Purchase", "12.25", "10.00", "-2.25"),
            ("Purchase", "5.00", "8.50", "3.50"),
            ("Purchase", "7.00", "7.00", "0"),
            ("Sale", "14.25", "10.00", "4.25"),
            ("Sale", "5.00", "8.50", "-3.50"),
            ("Sale", "7.00", "7.00", "0"),
        ):
            transaction = make_transaction(
                usd_bond, portfolio, transaction_type=transaction_type, accrued_interest_paid=charged
            )
            frappe.db.set_value(
                "Bond Transaction", transaction.name, "accrued_interest_calculated", calculated
            )
            expected[transaction.name] = Decimal(difference)
        equal = make_transaction(kes_bond, portfolio, accrued_interest_paid="7.00")
        frappe.db.set_value("Bond Transaction", equal.name, "accrued_interest_calculated", "7.00")
        expected[equal.name] = Decimal("0")

        rows = execute({"portfolio_name": portfolio.name})[1]
        detail_rows = [row for row in rows if not row.get("is_total_row")]
        totals = {(row["portfolio_name"], row["currency"]): row for row in rows if row.get("is_total_row")}

        self.assertEqual(
            {row.transaction_reference: row.interest_difference for row in detail_rows},
            expected,
        )
        days_by_type_and_difference = {
            (row.transaction_type, row.interest_difference): row.interest_difference_days
            for row in detail_rows
        }
        self.assertEqual(days_by_type_and_difference[("Purchase", Decimal("-2.25"))], Decimal("-11.57"))
        self.assertEqual(days_by_type_and_difference[("Sale", Decimal("4.25"))], Decimal("21.86"))
        self.assertEqual(totals[(portfolio.name, "USD")]["interest_difference"], Decimal("2"))
        self.assertEqual(totals[(portfolio.name, "KES")]["interest_difference"], Decimal("0"))
        self.assertIsNone(totals[(portfolio.name, "USD")]["interest_difference_days"])

    def test_day_conversion_uses_actual_coupon_period_under_day_count_conventions(self):
        portfolio = make_portfolio()
        for currency, convention in (
            ("USD", "Actual/Actual(ICMA)"),
            ("KES", "Actual/364(Kenya)"),
        ):
            bond = make_bond(currency=currency, day_count_convention=convention)
            transaction = make_transaction(
                bond,
                portfolio,
                trade_date="2025-06-29",
                settlement_date="2025-06-30",
                accrued_interest_paid="10.00",
            )
            frappe.db.set_value("Bond Transaction", transaction.name, "accrued_interest_calculated", "0")

        rows = execute({"portfolio_name": portfolio.name})[1]
        days_by_currency = {
            row.currency: row.interest_difference_days for row in rows if not row.get("is_total_row")
        }

        self.assertEqual(days_by_currency["USD"], Decimal("-51.71"))
        self.assertEqual(days_by_currency["KES"], Decimal("-52.00"))

    def test_kenya_day_conversion_uses_saved_transaction_coupon_rate(self):
        portfolio = make_portfolio()
        bond = make_bond(currency="KES", day_count_convention="Actual/364(Kenya)", coupon_rate=7)
        transaction = make_transaction(
            bond,
            portfolio,
            trade_date="2025-06-29",
            settlement_date="2025-06-30",
            accrued_interest_paid="10.00",
        )
        frappe.db.set_value("Bond Transaction", transaction.name, "accrued_interest_calculated", "0")

        original_row = next(
            row
            for row in execute({"portfolio_name": portfolio.name})[1]
            if row.transaction_reference == transaction.name
        )
        self.assertEqual(original_row.interest_difference_days, Decimal("-52.00"))
        self.assertEqual(frappe.db.get_value("Bond Transaction", transaction.name, "coupon_rate"), 7)

        bond.coupon_rate = 14
        bond.save()

        updated_row = next(
            row
            for row in execute({"portfolio_name": portfolio.name})[1]
            if row.transaction_reference == transaction.name
        )
        self.assertEqual(updated_row.interest_difference_days, Decimal("-52.00"))
        self.assertEqual(frappe.db.get_value("Bond Transaction", transaction.name, "coupon_rate"), 7)

    def test_settlement_date_and_portfolio_filters_are_inclusive(self):
        portfolio = make_portfolio()
        other_portfolio = make_portfolio()
        bond = make_bond()
        first = make_transaction(bond, portfolio, trade_date="2025-01-31", settlement_date="2025-02-01")
        last = make_transaction(bond, portfolio, trade_date="2025-02-27", settlement_date="2025-02-28")
        make_transaction(bond, portfolio, trade_date="2025-02-28", settlement_date="2025-03-01")
        make_transaction(bond, other_portfolio, trade_date="2025-02-14", settlement_date="2025-02-15")

        rows = execute(
            {
                "from_date": "2025-02-01",
                "to_date": "2025-02-28",
                "portfolio_name": portfolio.name,
            }
        )[1]

        self.assertEqual(
            {row.transaction_reference for row in rows if not row.get("is_total_row")},
            {first.name, last.name},
        )

    def test_filters_validate_date_order_and_type(self):
        with self.assertRaisesRegex(frappe.ValidationError, "Portfolio is required"):
            execute({})
        with self.assertRaisesRegex(frappe.ValidationError, "From Date must be on or before To Date"):
            execute(
                {
                    "from_date": "2025-02-02",
                    "to_date": "2025-02-01",
                    "portfolio_name": "TEST-PORTFOLIO",
                }
            )
        with self.assertRaisesRegex(frappe.ValidationError, "Portfolio must be a string"):
            execute({"portfolio_name": []})

    def test_selected_portfolio_respects_investor_assignment(self):
        assigned_portfolio = make_portfolio()
        other_portfolio = make_portfolio()
        bond = make_bond()
        assigned_transaction = make_transaction(bond, assigned_portfolio)
        other_transaction = make_transaction(bond, other_portfolio)
        email = f"{unique_name('report-investor').lower()}@example.com"
        frappe.get_doc(
            {
                "doctype": "User",
                "email": email,
                "first_name": "Report Investor",
                "send_welcome_email": 0,
                "roles": [{"role": INVESTOR_ROLE}],
            }
        ).insert(ignore_permissions=True)
        frappe.get_doc(
            {
                "doctype": "User Permission",
                "user": email,
                "allow": "Bond Portfolio",
                "for_value": assigned_portfolio.name,
                "apply_to_all_doctypes": 1,
            }
        ).insert(ignore_permissions=True)

        previous_user = frappe.session.user
        try:
            frappe.set_user(email)
            rows = execute({"portfolio_name": assigned_portfolio.name})[1]
            visible = {row.transaction_reference for row in rows if not row.get("is_total_row")}
            with self.assertRaises(frappe.PermissionError):
                execute({"portfolio_name": other_portfolio.name})
        finally:
            frappe.set_user(previous_user)

        self.assertIn(assigned_transaction.name, visible)
        self.assertNotIn(other_transaction.name, visible)

    def test_columns_include_signed_result_without_portfolio_or_transaction_count(self):
        columns = get_columns()
        fieldnames = [column["fieldname"] for column in columns]

        self.assertIn("interest_difference", fieldnames)
        self.assertIn("currency", fieldnames)
        self.assertIn("interest_difference_days", fieldnames)
        self.assertNotIn("portfolio_name", fieldnames)
        self.assertNotIn("transaction_count", fieldnames)
        self.assertIn(
            "Investor Gain + / Loss -",
            next(column["label"] for column in columns if column["fieldname"] == "interest_difference"),
        )
