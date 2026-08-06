from datetime import date
from decimal import Decimal

from frappe.tests import UnitTestCase

from bond_management.bond_management.tests.pdf_factory import make_text_pdf
from bond_management.bond_management.utils.statement_pdf import (
    StatementPdfError,
    StatementPdfPasswordError,
    extract_statement_pdf,
    parse_statement_exchange_rates,
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

        with self.assertRaisesRegex(StatementPdfError, "Bond Transaction confirmation"):
            parse_statement_pdf_text(
                """
                Bonds - Confirmation Notice
                Account No: 1110700351101
                Transaction Reference: U1046471
                """
            )

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
            3,954,003.26 3,851,250.00 23/01/2034
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

    def test_uses_explicit_account_hint_when_legacy_pdf_omits_account(self):
        parsed = extract_statement_pdf(
            make_text_pdf("SUMMARY OF ACCOUNT As of 30/11/2020", "correct-password"),
            ["correct-password"],
            account_no_hint="1110700350102",
        )

        self.assertEqual(parsed.account_no, "1110700350102")
        self.assertEqual(parsed.statement_date, date(2020, 11, 30))

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

        legacy_unit_prices = parse_statement_market_prices(
            """
            REPUBLIC OF KENYA - ISIN XS1028952403
            XS1028952403 USD 2,000.000000 99.250000 0.00000000 110.000000
            198,500.00 220,000.00 24/06/2024
            """
        )
        self.assertEqual(legacy_unit_prices[0].reported_quantity, Decimal("2000.000000"))
        self.assertFalse(legacy_unit_prices[0].quantity_is_face_value)

        named_prices = parse_statement_market_prices(
            """
            FXD3/2019/15 KES 100,000.000000 104.592600 0.00000000 98.965410
            10,459,260.00 9,896,541.00 10/07/2034
            """,
            {"Kenya Treasury Bond FXD3-2019-15": "KE6000001328"},
        )
        self.assertEqual(len(named_prices), 1)
        self.assertEqual(named_prices[0].isin, "KE6000001328")
        self.assertEqual(named_prices[0].market_price, Decimal("98.965410"))
        self.assertEqual(named_prices[0].reported_quantity, Decimal("100000.000000"))
        self.assertFalse(named_prices[0].quantity_is_face_value)

        wrapped_isin_prices = parse_statement_market_prices(
            """
            UNITED KINGDOM GILT 1.5% 2026 -
            GB00BYZW3G
            56
            GBP GB00BYZW3G
            56 900.00 100 94.413000 84,971.70
            29/02/2024 93.938000 84,544.20
            """
        )
        self.assertEqual(len(wrapped_isin_prices), 1)
        self.assertEqual(wrapped_isin_prices[0].isin, "GB00BYZW3G56")
        self.assertEqual(wrapped_isin_prices[0].reported_quantity, Decimal("900.00"))
        self.assertFalse(wrapped_isin_prices[0].quantity_is_face_value)

    def test_parses_statement_exchange_rates(self):
        rates = parse_statement_exchange_rates(
            """
            Currency Pair Rate
            KES / USD 0.00772499
            """
        )

        self.assertEqual(len(rates), 1)
        self.assertEqual(rates[0].from_currency, "KES")
        self.assertEqual(rates[0].to_currency, "USD")
        self.assertEqual(rates[0].rate, Decimal("0.00772499"))

    def test_ignores_mutual_fund_rows_when_parsing_fixed_income_prices(self):
        self.assertEqual(
            parse_statement_market_prices(
                """
                AB SICAV I - ALL MARKET INCOME PORTFOLIO - LU1127387386
                USD 6,709.696000 12.668234 10.620000 85,000.00 71,256.97
                -13,743.03 -16.1683
                """
            ),
            (),
        )

    def test_allows_statements_without_exchange_rates_for_manual_fallback(self):
        self.assertEqual(parse_statement_exchange_rates("Currency Pair Rate"), ())

    def test_rejects_invalid_or_conflicting_exchange_rates(self):
        with self.assertRaisesRegex(StatementPdfError, "must be greater than zero"):
            parse_statement_exchange_rates("KES / USD 0")

        with self.assertRaisesRegex(StatementPdfError, "conflicting exchange rates"):
            parse_statement_exchange_rates("KES / USD 0.0077\nKES / USD 0.0078")

    def test_rejects_conflicting_market_prices_for_an_isin(self):
        with self.assertRaisesRegex(StatementPdfError, "conflicting market prices"):
            parse_statement_market_prices(
                """
                XS1843435766 1,000 100 99 99,000 30/06/2026 101.25
                XS1843435766 USD 1,000 99 8 102.25 99,000 1,022.50 30/06/2026
                """
            )

        with self.assertRaisesRegex(StatementPdfError, "conflicting reported quantities"):
            parse_statement_market_prices(
                """
                XS1843435766 1,000 100 99 99,000 30/06/2026 101.25
                XS1843435766 USD 2,000 100 99 101.25 200,000 202,500 30/06/2026
                """
            )

    def test_rejects_ambiguous_legacy_quantity_interpretation(self):
        with self.assertRaisesRegex(StatementPdfError, "ambiguous legacy quantity"):
            parse_statement_market_prices(
                """
                XS1028952403 USD 2,000.000000 99.250000 6.30000000 99.250000
                0.000000 100,242.50 23/01/2034
                """
            )

    def test_accepts_empty_legacy_holding_with_zero_market_value(self):
        prices = parse_statement_market_prices(
            """
            XS1028952403 USD 0.000000 99.250000 6.30000000 99.250000
            0.000000 0.000000 23/01/2034
            """
        )

        self.assertEqual(len(prices), 1)
        self.assertEqual(prices[0].reported_quantity, Decimal("0.000000"))
        self.assertFalse(prices[0].quantity_is_face_value)
