from decimal import Decimal

from frappe.tests import UnitTestCase

from bond_management.bond_management.tests.pdf_factory import make_positioned_text_pdf, make_text_pdf
from bond_management.bond_management.utils.transaction_pdf import (
    TransactionPdfError,
    TransactionPdfPasswordError,
    extract_transaction_pdf,
    parse_transaction_pdf_text,
)


class TestTransactionPdf(UnitTestCase):
    def test_parses_current_multi_transaction_confirmation(self):
        parsed = parse_transaction_pdf_text(
            _current_transaction_text("U1999155", quantity="20,000.000000")
            + "\n"
            + _current_transaction_text(
                "R0775727",
                transaction_label="Redemption",
                quantity="10,000.000000",
                commission="N/A",
            )
        )

        self.assertEqual(parsed.account_no, "1110700431101")
        self.assertEqual(len(parsed.transactions), 2)
        purchase, sale = parsed.transactions
        self.assertEqual(purchase.transaction_type, "Purchase")
        self.assertEqual(purchase.quantity_face_value, Decimal("20000.000000"))
        self.assertEqual(purchase.trade_date.isoformat(), "2026-06-02")
        self.assertEqual(purchase.commission_percent, Decimal("0.45"))
        self.assertEqual(sale.transaction_type, "Sale")
        self.assertEqual(sale.commission_percent, Decimal("0"))

    def test_parses_multiple_rows_under_one_subscription_heading(self):
        parsed = parse_transaction_pdf_text(
            _current_transaction_text("U0792275", quantity="39,000.000000")
            + "\n"
            + _current_transaction_row_text("U0792348", quantity="2,500.000000")
        )

        self.assertEqual(
            [row.transaction_reference for row in parsed.transactions],
            ["U0792275", "U0792348"],
        )
        self.assertEqual(parsed.transactions[1].quantity_face_value, Decimal("2500.000000"))

    def test_parses_legacy_confirmation_and_uses_settlement_as_trade_date(self):
        parsed = parse_transaction_pdf_text(
            """
            Account No: 1110700351101
            TRANSACTION DETAILS :
            Subscription
            Bonds Name : REPUBLIC OF KENYA - XS1781710543 / XS1781710543
            Currency : USD Quantity / Face Value : 3,000.000000
            Price : 96.000000 Principal : 288,000.00
            Settlement Date : 02/06/2020 Settlement Amount in Currency : 293,679.17
            Accrued Interest : 5,679.17 Commission : 2,025.00
            Transaction Reference : U0667558
            """
        )

        row = parsed.transactions[0]
        self.assertEqual(row.isin, "XS1781710543")
        self.assertEqual(row.trade_date, row.settlement_date)
        self.assertIsNone(row.commission_percent)
        self.assertEqual(row.commission_amount, Decimal("2025.00"))

    def test_parses_pdf_principal_and_settlement_amount(self):
        parsed = parse_transaction_pdf_text(
            """
            Account No: 1110700351101
            TRANSACTION DETAILS :
            Subscription
            Bonds Name : FXD1/2019/10 - KE5000009653 / KE5000009653
            Currency : KES Quantity / Face Value : 400,000.000000
            Price : 104.039100 Principal : 41,615,640.00
            Settlement Date : 25/02/2020 Settlement Amount in Currency : 41,629,320.00
            Accrued Interest : 13,680.00 Commission : 0.00
            Transaction Reference : U0644850
            """
        )

        row = parsed.transactions[0]
        self.assertEqual(row.principal, Decimal("41615640.00"))
        self.assertEqual(row.settlement_amount, Decimal("41629320.00"))

    def test_decrypts_with_configured_password(self):
        content = make_text_pdf(_current_transaction_text("U1999155"), "portfolio-password")

        parsed = extract_transaction_pdf(content, ["wrong", "portfolio-password"])

        self.assertEqual(parsed.transactions[0].transaction_reference, "U1999155")
        self.assertNotIn("portfolio-password", repr(parsed))
        with self.assertRaises(TransactionPdfPasswordError):
            extract_transaction_pdf(content, ["wrong"])

    def test_parses_column_ordered_confirmation_without_breaking_legacy_formats(self):
        text_items = [
            (50, 700, "Account No :"),
            (50, 650, "Bonds Name :"),
            (50, 630, "ISIN :"),
            (50, 610, "Currency :"),
            (50, 590, "Price :"),
            (50, 570, "Trade Date :"),
            (50, 550, "Settlement Date :"),
            (50, 530, "Accrued Interest :"),
            (300, 590, "Quantity :"),
            (300, 570, "Face Value :"),
            (300, 550, "Commission % :"),
            (300, 530, "Transaction Reference :"),
            (150, 700, "1110700351101"),
            (150, 650, "REPUBLIC OF KENYA - XS3305838602"),
            (150, 630, "XS3305838602"),
            (150, 610, "USD"),
            (150, 590, "99.950000"),
            (150, 570, "26/02/2026"),
            (150, 550, "27/02/2026"),
            (150, 530, "49.22"),
            (500, 590, "2,250.000000"),
            (500, 570, "225,000.00"),
            (500, 550, "0.45%"),
            (500, 530, "U1903418"),
        ]

        parsed = extract_transaction_pdf(make_positioned_text_pdf(text_items), [])

        self.assertEqual(parsed.account_no, "1110700351101")
        self.assertEqual(parsed.transactions[0].transaction_reference, "U1903418")
        self.assertEqual(parsed.transactions[0].quantity_face_value, Decimal("2250.000000"))
        self.assertEqual(parsed.transactions[0].settlement_date.isoformat(), "2026-02-27")

    def test_blank_commission_fields_mean_zero(self):
        parsed = parse_transaction_pdf_text(
            """
            Account No : 1110700351101
            Redemption
            Bonds Name : REPUBLIC OF KENYA - ISIN XS1028952403
            ISIN : XS1028952403
            Quantity / Face Value : 2,000.000000
            Price : 110.025000
            Trade Date : 30/07/2021
            Settlement Date : 30/07/2021
            Commission % :
            Accrued Interest : 1,375.00
            Commission Amount :
            Transaction Reference : R0362130
            """
        )

        self.assertEqual(parsed.transactions[0].commission_percent, Decimal("0"))
        self.assertIsNone(parsed.transactions[0].commission_amount)

    def test_accepts_zero_at_non_negative_transaction_boundaries(self):
        parsed = parse_transaction_pdf_text(
            _current_transaction_text(
                "U1999155",
                accrued_interest="0",
                commission="0",
                commission_amount="0",
            )
        )

        row = parsed.transactions[0]
        self.assertEqual(row.accrued_interest_paid, Decimal("0"))
        self.assertEqual(row.commission_percent, Decimal("0"))

        amount_only = parse_transaction_pdf_text(
            _current_transaction_text(
                "U1999156",
                commission=None,
                commission_amount="0",
            )
        )
        self.assertEqual(amount_only.transactions[0].commission_amount, Decimal("0"))

    def test_rejects_non_positive_transaction_values_before_arithmetic(self):
        invalid_values = (
            ("quantity", {"quantity": "0"}, "Quantity / Face Value must be greater than zero"),
            ("quantity", {"quantity": "-1"}, "Quantity / Face Value must be greater than zero"),
            ("price", {"price": "0"}, "Price must be greater than zero"),
            ("price", {"price": "-1"}, "Price must be greater than zero"),
            (
                "accrued interest",
                {"accrued_interest": "-0.01"},
                "Accrued Interest must be zero or greater",
            ),
            ("commission percent", {"commission": "-0.01"}, "Commission % must be zero or greater"),
            (
                "commission amount",
                {"commission": None, "commission_amount": "-0.01"},
                "Commission Amount must be zero or greater",
            ),
            ("principal", {"principal": "0"}, "Principal must be greater than zero"),
            ("settlement amount", {"settlement_amount": "0"}, "Settlement Amount must be greater than zero"),
        )

        for label, values, message in invalid_values:
            with self.subTest(label=label):
                with self.assertRaisesRegex(TransactionPdfError, message):
                    parse_transaction_pdf_text(_current_transaction_text("U1999155", **values))

    def test_valid_password_does_not_mask_a_format_error(self):
        content = make_text_pdf(
            "Account No: 1110700351101\nNo transaction rows",
            "portfolio-password",
        )

        with self.assertRaisesRegex(TransactionPdfError, "reference starting with R or U"):
            extract_transaction_pdf(content, ["portfolio-password"])

    def test_rejects_missing_accounts_transactions_and_conflicting_rows(self):
        with self.assertRaisesRegex(TransactionPdfError, "Account No"):
            parse_transaction_pdf_text("Subscription Transaction Reference: U123")
        with self.assertRaisesRegex(TransactionPdfError, "reference starting with R or U"):
            parse_transaction_pdf_text("Account No: 1110700431101")

        conflicting = (
            _current_transaction_text("U1999155", price="100.350000")
            + "\n"
            + (_current_transaction_text("U1999155", price="101.350000"))
        )
        with self.assertRaisesRegex(TransactionPdfError, "conflicting values"):
            parse_transaction_pdf_text(conflicting)


def _current_transaction_text(
    reference,
    *,
    transaction_label="Subscription",
    quantity="20,000.000000",
    price="100.350000",
    accrued_interest="24,062.50",
    commission="0.45",
    commission_amount="9,000.00",
    principal="2,000,000.00",
    settlement_amount="2,031,062.50",
):
    return f"""
    Account No : 1110700431101
    TRANSACTION DETAILS:
    {transaction_label}
    {
        _current_transaction_row_text(
            reference,
            quantity=quantity,
            price=price,
            accrued_interest=accrued_interest,
            commission=commission,
            commission_amount=commission_amount,
            principal=principal,
            settlement_amount=settlement_amount,
        )
    }
    """


def _current_transaction_row_text(
    reference,
    *,
    quantity="20,000.000000",
    price="100.350000",
    accrued_interest="24,062.50",
    commission="0.45",
    commission_amount="9,000.00",
    principal="2,000,000.00",
    settlement_amount="2,031,062.50",
):
    commission_field = (
        f"Commission % : {commission}%"
        if commission is not None
        else f"Commission Amount : {commission_amount}"
    )
    return f"""
    Bonds Name : REPUBLIC OF KENYA - XS3196101201
    ISIN : XS3196101201
    Currency : USD Quantity : {quantity}
    Price : {price} Face Value : 2,000,000.00 Principal : {principal}
    Trade Date : 02/06/2026 Settlement Amount in Currency : {settlement_amount}
    Settlement Date : 03/06/2026 {commission_field}
    Accrued Interest : {accrued_interest} Commission Amount : {commission_amount}
    Transaction Reference : {reference}
    """
