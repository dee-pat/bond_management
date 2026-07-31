from datetime import date
from decimal import Decimal

from frappe.tests import UnitTestCase

from bond_management.bond_management.tests.pdf_factory import make_text_pdf
from bond_management.bond_management.utils.statement_pdf import (
    StatementPdfError,
    StatementPdfPasswordError,
    extract_statement_pdf,
    parse_statement_market_prices,
    parse_statement_pdf_text,
)


class TestStatementPdf(UnitTestCase):
    def test_parses_current_portfolio_summary_layout(self):
        parsed = parse_statement_pdf_text(
            """
            Portfolio Summary as of 30/06/2026
            Product Account No.: 1110700431102
            """
        )

        self.assertEqual(parsed.account_no, "1110700431102")
        self.assertEqual(parsed.statement_date, date(2026, 6, 30))

    def test_parses_legacy_summary_of_account_layout(self):
        parsed = parse_statement_pdf_text(
            """
            SUMMARY OF ACCOUNT                              As of 30/09/2021
            IS Account : 1110700431101
            """
        )

        self.assertEqual(parsed.account_no, "1110700431101")
        self.assertEqual(parsed.statement_date, date(2021, 9, 30))

    def test_rejects_missing_or_conflicting_statement_values(self):
        with self.assertRaisesRegex(StatementPdfError, "Product Account No. or IS Account"):
            parse_statement_pdf_text("Portfolio Summary as of 30/06/2026")

        with self.assertRaisesRegex(StatementPdfError, "conflicting product account"):
            parse_statement_pdf_text(
                """
                Portfolio Summary as of 30/06/2026
                Product Account No.: ACCOUNT-1
                IS Account: ACCOUNT-2
                """
            )

        with self.assertRaisesRegex(StatementPdfError, "conflicting portfolio summary dates"):
            parse_statement_pdf_text(
                """
                Portfolio Summary as of 30/06/2026
                SUMMARY OF ACCOUNT As of 31/05/2026
                Product Account No.: ACCOUNT-1
                """
            )

    def test_decrypts_with_a_configured_password_without_exposing_it(self):
        pdf = make_text_pdf(
            "Portfolio Summary as of 30/06/2026\nProduct Account No.: ACCOUNT-1",
            password="correct-password",
        )

        parsed = extract_statement_pdf(pdf, ["wrong-password", "correct-password"])

        self.assertEqual(parsed.account_no, "ACCOUNT-1")
        self.assertEqual(parsed.statement_date, date(2026, 6, 30))
        self.assertNotIn("correct-password", repr(parsed))

    def test_rejects_unknown_passwords_and_non_pdf_content(self):
        pdf = make_text_pdf(
            "Portfolio Summary as of 30/06/2026\nProduct Account No.: ACCOUNT-1",
            password="correct-password",
        )

        with self.assertRaisesRegex(StatementPdfPasswordError, "configured Bond Portfolio password"):
            extract_statement_pdf(pdf, ["wrong-password"])

        with self.assertRaisesRegex(StatementPdfError, "not a valid PDF"):
            extract_statement_pdf(b"not a pdf", ["correct-password"])

    def test_uses_original_filename_account_only_when_legacy_pdf_omits_it(self):
        pdf = make_text_pdf(
            """
            SUMMARY OF ACCOUNT As of 31/10/2022
            XS2354781614
            USD 3,900,000.00 101.384699 6.30000000 98.750000
            """,
            password="correct-password",
        )

        parsed = extract_statement_pdf(
            pdf,
            ["correct-password"],
            account_no_hint="1110700431101",
        )

        self.assertEqual(parsed.account_no, "1110700431101")
        self.assertEqual(parsed.statement_date, date(2022, 10, 31))
        self.assertEqual(parsed.market_prices[0].market_price, Decimal("98.750000"))
        self.assertEqual(parsed.market_prices[0].reported_quantity, Decimal("3900000.00"))
        self.assertTrue(parsed.market_prices[0].quantity_is_face_value)

        embedded_account = extract_statement_pdf(
            make_text_pdf(
                """
                Portfolio Summary as of 31/10/2022
                Product Account No.: EMBEDDED-ACCOUNT
                """,
            ),
            [],
            account_no_hint="FILENAME-ACCOUNT",
        )
        self.assertEqual(embedded_account.account_no, "EMBEDDED-ACCOUNT")

    def test_parses_current_and_legacy_fixed_income_market_prices(self):
        current_prices = parse_statement_market_prices(
            """
            REPUBLIC OF KENYA - XS1843435766 USD XS1843435766
            151,370.000000 100 103.210664 15,622,998.21
            29/05/2026 101.650000 15,386,760.50
            """
        )
        legacy_prices = parse_statement_market_prices(
            """
            REPUBLIC OF KENYA -
            XS2354781614
            USD 3,900,000.00 101.384699 6.30000000 98.750000
            3,954,003.26 3,851,250.00 23/01/2034
            """
        )

        self.assertEqual(len(current_prices), 1)
        self.assertEqual(current_prices[0].isin, "XS1843435766")
        self.assertEqual(current_prices[0].market_price, Decimal("101.650000"))
        self.assertEqual(current_prices[0].reported_quantity, Decimal("151370.000000"))
        self.assertFalse(current_prices[0].quantity_is_face_value)
        self.assertEqual(len(legacy_prices), 1)
        self.assertEqual(legacy_prices[0].isin, "XS2354781614")
        self.assertEqual(legacy_prices[0].market_price, Decimal("98.750000"))
        self.assertEqual(legacy_prices[0].reported_quantity, Decimal("3900000.00"))
        self.assertTrue(legacy_prices[0].quantity_is_face_value)

    def test_rejects_conflicting_market_prices_for_an_isin(self):
        with self.assertRaisesRegex(StatementPdfError, "conflicting market prices"):
            parse_statement_market_prices(
                """
                XS1843435766 1,000 100 99 99,000 30/06/2026 101.25
                XS1843435766 USD 1,000 99 8 102.25
                """
            )

        with self.assertRaisesRegex(StatementPdfError, "conflicting reported quantities"):
            parse_statement_market_prices(
                """
                XS1843435766 1,000 100 99 99,000 30/06/2026 101.25
                XS1843435766 2,000 100 99 99,000 30/06/2026 101.25
                """
            )
