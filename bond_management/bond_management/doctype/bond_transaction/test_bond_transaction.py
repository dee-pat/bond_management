# Copyright (c) 2026, Deepak Patel and Contributors
# See license.txt

from decimal import Decimal
from pathlib import Path
from unittest.mock import patch

import frappe
from frappe.exceptions import FrappeTypeError, ValidationError
from frappe.tests import IntegrationTestCase
from frappe.utils import getdate

from bond_management.bond_management.doctype.bond_transaction.bond_transaction import (
    _calculate_amount_values,
    get_calculated_amounts,
)
from bond_management.bond_management.tests.factories import (
    make_bond,
    make_portfolio,
    make_transaction,
    unique_name,
)
from bond_management.bond_management.tests.pdf_factory import make_text_pdf
from bond_management.bond_management.utils.portfolio import (
    get_position,
    get_position_for_payment,
)
from bond_management.patches.backfill_transaction_amounts import (
    execute as backfill_transaction_amounts,
)
from bond_management.patches.backfill_transaction_principal_values import (
    execute as backfill_transaction_principal_values,
)
from bond_management.patches.standardize_bond_transaction_attachment_names import (
    execute as standardize_existing_transaction_attachments,
)


class TestBondTransaction(IntegrationTestCase):
    def test_read_transaction_pdf_rejects_complex_attachment_values(self):
        transaction = frappe.get_doc({"doctype": "Bond Transaction", "attachment": {}})

        with self.assertRaisesRegex(ValidationError, "Attachment must be a string"):
            transaction.read_transaction_pdf()

    def test_principal_backfill_is_price_adjusted_and_idempotent(self):
        bond = make_bond(face_value_per_unit=100)
        portfolio = make_portfolio()
        transaction = make_transaction(
            bond,
            portfolio,
            quantity_face_value=10,
            price=105,
            accrued_interest_paid=1,
        )
        original_settlement = transaction.settlement_amount
        frappe.db.set_value(
            "Bond Transaction",
            transaction.name,
            "principal",
            1000,
            update_modified=False,
        )

        backfill_transaction_principal_values([transaction.name])
        transaction.reload()
        self.assertEqual(transaction.principal, 1050)
        self.assertEqual(transaction.settlement_amount, original_settlement)

        backfill_transaction_principal_values([transaction.name])
        transaction.reload()
        self.assertEqual(transaction.principal, 1050)

    def test_pdf_attachment_populates_fields_and_rejects_later_changes(self):
        bond = self._make_pdf_bond()
        portfolio = make_portfolio()
        reference = self._numeric_reference("U")
        attachment = self._attach_transaction_pdf(
            self._confirmation_text(
                portfolio.transaction_account_no,
                reference,
                bond.name,
            ),
            "test-password",
        )

        transaction = frappe.get_doc(
            {
                "doctype": "Bond Transaction",
                "attachment": attachment,
            }
        ).insert()

        self.assertEqual(transaction.name, reference)
        self.assertEqual(transaction.transaction_type, "Purchase")
        self.assertEqual(transaction.isin, bond.name)
        self.assertEqual(transaction.portfolio_name, portfolio.name)
        self.assertEqual(getdate(transaction.trade_date), getdate("2025-12-30"))
        self.assertEqual(getdate(transaction.settlement_date), getdate("2025-12-31"))
        self.assertEqual(transaction.quantity_face_value, 10)
        self.assertEqual(transaction.price, 105)
        self.assertEqual(transaction.accrued_interest_paid, 1)
        self.assertEqual(transaction.commission, 2)
        self.assertEqual(transaction.principal, 1050)
        self.assertEqual(transaction.settlement_amount, 1051)
        self.assertEqual(
            transaction.attachment,
            f"/private/files/Transaction-{portfolio.account_no}-20251231.pdf",
        )

        attachment_files = frappe.qb.get_query(
            "File",
            fields=["file_name", "attached_to_name", "attached_to_field"],
            filters={
                "file_url": transaction.attachment,
                "attached_to_doctype": "Bond Transaction",
                "attached_to_name": transaction.name,
                "attached_to_field": "attachment",
            },
            ignore_permissions=False,
        ).run(as_dict=True)
        self.assertEqual(len(attachment_files), 1)
        self.assertEqual(
            attachment_files[0].file_name,
            transaction.attachment.removeprefix("/private/files/"),
        )

        transaction.price = 106
        with self.assertRaisesRegex(ValidationError, "no longer match the attached PDF"):
            transaction.save()

    def test_pdf_reference_prefix_marks_a_sale(self):
        bond = self._make_pdf_bond()
        portfolio = make_portfolio()
        make_transaction(bond, portfolio, quantity_face_value=10)
        reference = self._numeric_reference("R")
        attachment = self._attach_transaction_pdf(
            self._confirmation_text(
                portfolio.transaction_account_no,
                reference,
                bond.name,
                transaction_label="Redemption",
                commission="N/A",
            ),
            "test-password",
        )

        transaction = frappe.get_doc(
            {
                "doctype": "Bond Transaction",
                "attachment": attachment,
            }
        ).insert()

        self.assertEqual(transaction.transaction_type, "Sale")
        self.assertEqual(transaction.commission, 0)

    def test_pdf_accepts_product_account_when_transaction_account_is_different(self):
        bond = self._make_pdf_bond()
        portfolio = make_portfolio(
            account_no=unique_name("PRODUCT-ACCOUNT"),
            transaction_account_no=unique_name("TRANSACTION-ACCOUNT"),
        )
        reference = self._numeric_reference("U")
        attachment = self._attach_transaction_pdf(
            self._confirmation_text(
                portfolio.account_no,
                reference,
                bond.name,
            ),
            "test-password",
        )

        transaction = frappe.get_doc(
            {
                "doctype": "Bond Transaction",
                "attachment": attachment,
            }
        ).insert()

        self.assertEqual(transaction.portfolio_name, portfolio.name)
        self.assertEqual(
            transaction.attachment,
            f"/private/files/Transaction-{portfolio.account_no}-20251231.pdf",
        )

    def test_multi_transaction_pdf_creates_selected_documents_with_same_attachment(self):
        bond = self._make_pdf_bond()
        portfolio = make_portfolio()
        references = [self._numeric_reference("U"), self._numeric_reference("U")]
        attachment = self._attach_transaction_pdf(
            "\n".join(
                self._confirmation_text(
                    portfolio.transaction_account_no,
                    reference,
                    bond.name,
                    quantity=quantity,
                )
                for reference, quantity in zip(references, ("5.000000", "7.000000"), strict=True)
            ),
            "test-password",
        )
        staging = frappe.get_doc(
            {
                "doctype": "Bond Transaction",
                "attachment": attachment,
            }
        )

        created = staging.create_selected_pdf_transactions(references)

        self.assertCountEqual(created, references)
        expected_attachment = f"/private/files/Transaction-{portfolio.account_no}-20251231.pdf"
        quantities = {}
        for reference in references:
            transaction = frappe.get_doc("Bond Transaction", reference)
            quantities[reference] = transaction.quantity_face_value
            self.assertEqual(transaction.attachment, expected_attachment)
            attachment_files = frappe.qb.get_query(
                "File",
                fields=["name"],
                filters={
                    "file_url": expected_attachment,
                    "attached_to_doctype": "Bond Transaction",
                    "attached_to_name": reference,
                    "attached_to_field": "attachment",
                },
                ignore_permissions=False,
            ).run(pluck=True)
            self.assertEqual(len(attachment_files), 1)
        self.assertEqual(sorted(quantities.values()), [5, 7])

    def test_multi_transaction_creation_rejects_non_text_selection_values(self):
        staging = frappe.get_doc({"doctype": "Bond Transaction"})

        invalid_selections = (
            ({"transaction_reference": ["U123"]}, "transaction reference must be text"),
            (
                {"transaction_reference": "U123", "portfolio_name": {"name": "TEST"}},
                "portfolio name must be text",
            ),
        )
        for selection, message in invalid_selections:
            with self.subTest(selection=selection):
                with self.assertRaisesRegex(ValidationError, message):
                    staging.create_selected_pdf_transactions([selection])

    def test_multi_transaction_rows_can_be_posted_to_different_portfolios(self):
        bond = self._make_pdf_bond()
        pdf_portfolio = make_portfolio()
        target_portfolio = make_portfolio()
        references = [self._numeric_reference("U"), self._numeric_reference("U")]
        attachment = self._attach_transaction_pdf(
            self._confirmation_text(
                pdf_portfolio.transaction_account_no,
                references[0],
                bond.name,
                quantity="5.000000",
            )
            + "\n"
            + self._confirmation_row_text(references[1], bond.name, quantity="7.000000"),
            "test-password",
        )
        staging = frappe.get_doc(
            {
                "doctype": "Bond Transaction",
                "attachment": attachment,
            }
        )

        with patch.object(
            staging,
            "_lock_portfolios",
            wraps=staging._lock_portfolios,
        ) as lock_portfolios:
            created = staging.create_selected_pdf_transactions(
                [
                    {
                        "transaction_reference": references[0],
                        "portfolio_name": target_portfolio.name,
                    },
                    {
                        "transaction_reference": references[1],
                        "portfolio_name": pdf_portfolio.name,
                    },
                ]
            )
            lock_portfolios.assert_called_once_with({target_portfolio.name, pdf_portfolio.name})

        self.assertCountEqual(created, references)
        overridden = frappe.get_doc("Bond Transaction", references[0])
        standard = frappe.get_doc("Bond Transaction", references[1])
        self.assertEqual(overridden.portfolio_name, target_portfolio.name)
        self.assertEqual(overridden.attachment_portfolio_override, 1)
        self.assertEqual(standard.portfolio_name, pdf_portfolio.name)
        self.assertEqual(standard.attachment_portfolio_override, 0)
        expected_attachment = f"/private/files/Transaction-{pdf_portfolio.account_no}-20251231.pdf"
        self.assertEqual(overridden.attachment, expected_attachment)
        self.assertEqual(standard.attachment, expected_attachment)

        overridden.save()
        overridden.portfolio_name = pdf_portfolio.name
        with self.assertRaisesRegex(ValidationError, "overrides can only be set"):
            overridden.save()

    def test_patch_standardizes_an_existing_transaction_attachment(self):
        bond = self._make_pdf_bond()
        portfolio = make_portfolio()
        reference = self._numeric_reference("U")
        attachment = self._attach_transaction_pdf(
            self._confirmation_text(
                portfolio.transaction_account_no,
                reference,
                bond.name,
            ),
            "test-password",
        )
        transaction = make_transaction(
            bond,
            portfolio,
            transaction_reference=reference,
            trade_date="2025-12-30",
            settlement_date="2025-12-31",
        )
        transaction.db_set("attachment", attachment, update_modified=False)

        standardize_existing_transaction_attachments([transaction.name])
        transaction.reload()

        expected_attachment = f"/private/files/Transaction-{portfolio.account_no}-20251231.pdf"
        self.assertEqual(transaction.attachment, expected_attachment)
        attachment_files = frappe.qb.get_query(
            "File",
            fields=["file_name", "attached_to_name", "attached_to_field"],
            filters={"file_url": expected_attachment},
            ignore_permissions=False,
        ).run(as_dict=True)
        self.assertEqual(len(attachment_files), 1)
        self.assertEqual(
            attachment_files[0].file_name,
            expected_attachment.removeprefix("/private/files/"),
        )
        self.assertEqual(attachment_files[0].attached_to_name, transaction.name)
        self.assertEqual(attachment_files[0].attached_to_field, "attachment")

        standardize_existing_transaction_attachments([transaction.name])
        transaction.reload()
        self.assertEqual(transaction.attachment, expected_attachment)

    def test_one_selected_row_from_multi_transaction_pdf_populates_current_document(self):
        bond = self._make_pdf_bond()
        portfolio = make_portfolio()
        references = [self._numeric_reference("U"), self._numeric_reference("U")]
        attachment = self._attach_transaction_pdf(
            "\n".join(
                self._confirmation_text(
                    portfolio.transaction_account_no,
                    reference,
                    bond.name,
                    quantity=quantity,
                )
                for reference, quantity in zip(references, ("5.000000", "7.000000"), strict=True)
            ),
            "test-password",
        )

        transaction = frappe.get_doc(
            {
                "doctype": "Bond Transaction",
                "attachment": attachment,
                "transaction_reference": references[1],
            }
        ).insert()

        self.assertEqual(transaction.name, references[1])
        self.assertEqual(transaction.quantity_face_value, 7)

    def test_multi_transaction_creation_rejects_duplicates_before_creating_any_rows(self):
        bond = self._make_pdf_bond()
        portfolio = make_portfolio()
        references = [self._numeric_reference("U"), self._numeric_reference("U")]
        attachment = self._attach_transaction_pdf(
            "\n".join(
                self._confirmation_text(
                    portfolio.transaction_account_no,
                    reference,
                    bond.name,
                )
                for reference in references
            ),
            "test-password",
        )
        existing_transaction = frappe.get_doc(
            {
                "doctype": "Bond Transaction",
                "attachment": attachment,
                "transaction_reference": references[0],
            }
        ).insert()
        staging = frappe.get_doc(
            {
                "doctype": "Bond Transaction",
                "attachment": existing_transaction.attachment,
            }
        )

        with self.assertRaisesRegex(ValidationError, "already exist"):
            staging.create_selected_pdf_transactions(references)

        self.assertFalse(frappe.db.exists("Bond Transaction", references[1]))

    def test_manual_entry_without_attachment_and_existing_legacy_attachment_remain_allowed(self):
        transaction = make_transaction(self._make_pdf_bond(), make_portfolio())
        self.assertFalse(transaction.attachment)

        transaction.db_set("attachment", "/private/files/legacy-transaction.xlsx")
        transaction.reload()
        transaction.save()
        self.assertEqual(transaction.attachment, "/private/files/legacy-transaction.xlsx")

    def test_new_non_pdf_attachment_is_rejected(self):
        transaction = make_transaction(
            self._make_pdf_bond(),
            make_portfolio(),
            insert=False,
            attachment="/private/files/not-a-confirmation.xlsx",
        )

        with self.assertRaisesRegex(ValidationError, "requires a PDF attachment"):
            transaction.insert()

    def test_pdf_amounts_must_match_calculated_values(self):
        bond = self._make_pdf_bond()
        portfolio = make_portfolio()
        reference = self._numeric_reference("U")
        attachment = self._attach_transaction_pdf(
            self._confirmation_text(
                portfolio.transaction_account_no,
                reference,
                bond.name,
                settlement_amount="1,052.00",
            ),
            "test-password",
        )

        with self.assertRaisesRegex(ValidationError, "calculated Bond Transaction amounts"):
            frappe.get_doc(
                {
                    "doctype": "Bond Transaction",
                    "attachment": attachment,
                }
            ).insert()

    def test_pdf_principal_must_imply_bond_master_face_value_per_unit(self):
        bond = self._make_pdf_bond()
        bond.db_set("face_value_per_unit", 100000)
        portfolio = make_portfolio()
        reference = self._numeric_reference("U")
        attachment = self._attach_transaction_pdf(
            self._confirmation_text(
                portfolio.transaction_account_no,
                reference,
                bond.name,
            ),
            "test-password",
        )

        with self.assertRaisesRegex(ValidationError, "Face Value Per Unit.*does not match the PDF"):
            frappe.get_doc(
                {
                    "doctype": "Bond Transaction",
                    "attachment": attachment,
                }
            ).insert()

    def test_calculates_transaction_amounts(self):
        transaction = make_transaction(make_bond(), make_portfolio())

        self.assertEqual(transaction.principal, 1050)
        self.assertEqual(transaction.commission_amount, 20)
        self.assertEqual(transaction.settlement_amount, 1051)
        self.assertEqual(transaction.transaction_amount, 1031)
        self.assertNotEqual(
            transaction.settlement_amount,
            transaction.principal * transaction.price / 100
            + transaction.accrued_interest_paid
            + transaction.commission_amount,
        )

    def test_amount_pipeline_uses_decimal_and_explicit_four_place_rounding(self):
        bond = make_bond(face_value_per_unit="100.03")

        amounts = _calculate_amount_values(
            bond,
            bond.issue_date,
            "3",
            "99.99",
            "0.005",
            "0.015",
        )

        self.assertEqual(amounts["principal"], Decimal("300.0600"))
        self.assertEqual(amounts["commission_amount"], Decimal("0.0450"))
        self.assertEqual(amounts["settlement_amount"], Decimal("300.0650"))
        self.assertEqual(amounts["transaction_amount"], Decimal("300.0200"))

    def test_value_endpoint_clears_amounts_without_an_isin(self):
        self.assertEqual(
            get_calculated_amounts(
                isin=None,
                settlement_date="2025-12-31",
                quantity_face_value=10,
                price=105,
                accrued_interest_paid=12,
                commission=2,
            ),
            {
                "principal": 0.0,
                "commission_amount": 0.0,
                "settlement_amount": 0.0,
                "transaction_amount": 0.0,
                "accrued_interest_calculated": 0.0,
            },
        )

    def test_transaction_amount_backfill_is_idempotent(self):
        transaction = make_transaction(make_bond(), make_portfolio())
        frappe.db.set_value(
            "Bond Transaction",
            transaction.name,
            "transaction_amount",
            0,
            update_modified=False,
        )

        backfill_transaction_amounts([transaction.name])
        transaction.reload()
        self.assertEqual(transaction.transaction_amount, 1031)

        backfill_transaction_amounts([transaction.name])
        transaction.reload()
        self.assertEqual(transaction.transaction_amount, 1031)

    def test_value_endpoint_rejects_complex_string_inputs(self):
        with self.assertRaisesRegex(FrappeTypeError, "isin.*str"):
            get_calculated_amounts(isin=[])
        with self.assertRaisesRegex(FrappeTypeError, "settlement_date.*str"):
            get_calculated_amounts(settlement_date={})
        with self.assertRaisesRegex(FrappeTypeError, "transaction_name.*str"):
            get_calculated_amounts(transaction_name=[])

    def test_uses_authoritative_bond_snapshot(self):
        bond = make_bond()
        transaction = make_transaction(
            bond,
            make_portfolio(),
            face_value_per_unit=999,
            currency="KES",
            coupon_rate=99,
            issue_date="2000-01-01",
            maturity_date="2099-01-01",
        )

        self.assertEqual(transaction.face_value_per_unit, bond.face_value_per_unit)
        self.assertEqual(transaction.currency, bond.currency)
        self.assertEqual(transaction.coupon_rate, bond.coupon_rate)
        self.assertEqual(getdate(transaction.issue_date), getdate(bond.issue_date))
        self.assertEqual(getdate(transaction.maturity_date), getdate(bond.maturity_date))

    def test_financial_value_boundaries(self):
        transaction = make_transaction(make_bond(), make_portfolio())

        for quantity in (0, -1):
            with self.subTest(quantity=quantity):
                transaction.quantity_face_value = quantity
                with self.assertRaisesRegex(ValidationError, "Quantity.*greater than zero"):
                    transaction.save()
                transaction.reload()
        transaction.quantity_face_value = 1
        transaction.save()

        for price in (0, -0.01):
            with self.subTest(price=price):
                transaction.price = price
                with self.assertRaisesRegex(ValidationError, "Price must be greater than zero"):
                    transaction.save()
                transaction.reload()
        transaction.price = 0.01
        transaction.save()

        transaction.commission = 0
        transaction.save()
        transaction.commission = -0.01
        with self.assertRaisesRegex(ValidationError, "Commission must be zero"):
            transaction.save()

    def test_rejects_invalid_transaction_type_and_missing_inputs(self):
        bond = make_bond()
        portfolio = make_portfolio()

        invalid_type = make_transaction(bond, portfolio, insert=False, transaction_type="Transfer")
        with self.assertRaisesRegex(ValidationError, "must be Purchase or Sale"):
            invalid_type.insert()

        missing_trade_date = make_transaction(bond, portfolio, insert=False, trade_date=None)
        with self.assertRaisesRegex(ValidationError, "Trade Date is required"):
            missing_trade_date.insert()

    def test_rejects_sale_larger_than_position(self):
        bond = make_bond()
        portfolio = make_portfolio()
        make_transaction(bond, portfolio)

        sale = frappe.get_doc(
            {
                "doctype": "Bond Transaction",
                "transaction_reference": unique_name("TEST-SALE"),
                "trade_date": "2025-12-30",
                "settlement_date": "2025-12-31",
                "isin": bond.name,
                "portfolio_name": portfolio.name,
                "transaction_type": "Sale",
                "quantity_face_value": 11,
                "price": 105,
                "accrued_interest_paid": 0,
                "commission": 0,
                "face_value_per_unit": bond.face_value_per_unit,
                "currency": bond.currency,
                "issue_date": bond.issue_date,
                "maturity_date": bond.maturity_date,
            }
        )

        self.assertRaises(ValidationError, sale.insert)

    def test_allows_settlement_on_issue_and_maturity_dates(self):
        bond = make_bond()

        issue_date_transaction = make_transaction(
            bond,
            make_portfolio(),
            trade_date=bond.issue_date,
            settlement_date=bond.issue_date,
        )
        maturity_date_transaction = make_transaction(
            bond, make_portfolio(), settlement_date=bond.maturity_date
        )

        self.assertEqual(issue_date_transaction.settlement_date, bond.issue_date)
        self.assertEqual(maturity_date_transaction.settlement_date, bond.maturity_date)

    def test_rejects_dates_outside_bond_and_trade_after_settlement(self):
        bond = make_bond()
        portfolio = make_portfolio()

        for trade_date, settlement_date, message in (
            ("2024-12-31", "2025-01-01", "Trade Date must be on or after"),
            ("2025-01-01", "2024-12-31", "Settlement Date must be on or after"),
            ("2027-01-02", "2027-01-02", "Trade Date must be on or before"),
            ("2027-01-01", "2027-01-02", "Settlement Date must be on or before"),
            ("2026-01-02", "2026-01-01", "Trade Date must be on or before Settlement"),
        ):
            with self.subTest(trade_date=trade_date, settlement_date=settlement_date):
                transaction = make_transaction(
                    bond,
                    portfolio,
                    insert=False,
                    trade_date=trade_date,
                    settlement_date=settlement_date,
                )
                with self.assertRaisesRegex(ValidationError, message):
                    transaction.insert()

    def test_sale_equal_to_position_and_same_day_purchase_is_allowed(self):
        bond = make_bond()
        portfolio = make_portfolio()
        purchase = make_transaction(bond, portfolio)
        sale = make_transaction(
            bond,
            portfolio,
            transaction_type="Sale",
            quantity_face_value=purchase.quantity_face_value,
        )

        self.assertEqual(get_position(bond.name, sale.settlement_date, portfolio.name), 0)

    def test_backdating_or_reducing_purchase_cannot_break_later_ledger(self):
        bond = make_bond()
        portfolio = make_portfolio()
        purchase = make_transaction(
            bond,
            portfolio,
            trade_date="2025-06-01",
            settlement_date="2025-06-02",
        )
        make_transaction(
            bond,
            portfolio,
            transaction_type="Sale",
            trade_date="2025-07-01",
            settlement_date="2025-07-02",
            quantity_face_value=10,
        )

        purchase.quantity_face_value = 9
        with self.assertRaisesRegex(ValidationError, "position negative"):
            purchase.save()

        purchase.reload()
        purchase.quantity_face_value = 10
        purchase.trade_date = "2025-08-01"
        purchase.settlement_date = "2025-08-02"
        with self.assertRaisesRegex(ValidationError, "position negative"):
            purchase.save()

    def test_purchase_cannot_be_deleted_or_moved_when_a_sale_depends_on_it(self):
        bond = make_bond()
        portfolio = make_portfolio()
        purchase = make_transaction(bond, portfolio)
        make_transaction(
            bond,
            portfolio,
            transaction_type="Sale",
            trade_date="2026-01-01",
            settlement_date="2026-01-02",
            quantity_face_value=10,
        )

        with self.assertRaisesRegex(ValidationError, "position negative"):
            purchase.delete()

        purchase.reload()
        purchase.portfolio_name = make_portfolio().name
        with self.assertRaisesRegex(ValidationError, "position negative"):
            purchase.save()

    def test_maturity_payment_position_is_inclusive_but_end_of_day_is_zero(self):
        bond = make_bond()
        portfolio = make_portfolio()
        make_transaction(
            bond,
            portfolio,
            trade_date=bond.maturity_date,
            settlement_date=bond.maturity_date,
        )

        self.assertEqual(get_position_for_payment(bond.name, bond.maturity_date, portfolio.name), 10)
        self.assertEqual(get_position(bond.name, bond.maturity_date, portfolio.name), 0)

    def _make_pdf_bond(self):
        isin = f"XS{frappe.generate_hash(length=10).upper()}"
        return make_bond(isin=isin, bond_name=isin)

    def _numeric_reference(self, prefix):
        return f"{prefix}{int(frappe.generate_hash(length=8), 36)}"

    def _attach_transaction_pdf(self, text, password):
        file_doc = frappe.get_doc(
            {
                "doctype": "File",
                "file_name": f"{unique_name('transaction-confirmation')}.pdf",
                "content": make_text_pdf(text, password),
                "is_private": 1,
            }
        ).insert()
        self.addCleanup(Path(file_doc.get_full_path()).unlink, missing_ok=True)
        return file_doc.file_url

    def _confirmation_text(
        self,
        account_no,
        reference,
        isin,
        *,
        transaction_label="Subscription",
        quantity="10.000000",
        price="105.000000",
        accrued_interest="1.00",
        commission="2.000000",
        principal=None,
        settlement_amount=None,
    ):
        return f"""
        Account No : {account_no}
        TRANSACTION DETAILS:
        {transaction_label}
        {
            self._confirmation_row_text(
                reference,
                isin,
                quantity=quantity,
                price=price,
                accrued_interest=accrued_interest,
                commission=commission,
                principal=principal,
                settlement_amount=settlement_amount,
            )
        }
        """

    def _confirmation_row_text(
        self,
        reference,
        isin,
        *,
        quantity="10.000000",
        price="105.000000",
        accrued_interest="1.00",
        commission="2.000000",
        principal=None,
        settlement_amount=None,
    ):
        quantity_value = Decimal(quantity.replace(",", ""))
        price_value = Decimal(price.replace(",", ""))
        accrued_interest_value = Decimal(accrued_interest.replace(",", ""))
        principal_value = principal.replace(",", "") if isinstance(principal, str) else principal
        principal_value = (
            Decimal(principal_value)
            if principal_value is not None
            else quantity_value * Decimal("100") * price_value / Decimal("100")
        )
        settlement_value = (
            settlement_amount.replace(",", "") if isinstance(settlement_amount, str) else settlement_amount
        )
        settlement_value = (
            Decimal(settlement_value)
            if settlement_value is not None
            else principal_value + accrued_interest_value
        )
        return f"""
        Bonds Name : REPUBLIC OF KENYA - {isin}
        ISIN : {isin}
        Currency : USD Quantity : {quantity}
        Price : {price} Face Value : 1,000.00 Principal : {principal_value:,.2f}
        Trade Date : 30/12/2025 Settlement Amount in Currency : {settlement_value:,.2f}
        Settlement Date : 31/12/2025 Commission % : {commission}%
        Accrued Interest : {accrued_interest} Commission Amount : 20.00
        Transaction Reference : {reference}
        """
