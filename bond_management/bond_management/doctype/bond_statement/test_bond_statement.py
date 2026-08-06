# Copyright (c) 2026, Deepak Patel and Contributors
# See license.txt

from decimal import Decimal
from io import BytesIO
from pathlib import Path
from unittest.mock import patch

import frappe
from frappe.tests import IntegrationTestCase
from pypdf import PdfReader

from bond_management.bond_management.tests.factories import (
    make_bond,
    make_exchange_rate,
    make_market_date,
    make_portfolio,
    make_statement,
    make_transaction,
    unique_name,
)
from bond_management.bond_management.tests.pdf_factory import make_text_pdf
from bond_management.bond_management.utils.statement_quantity_reconciliation import (
    StatementQuantityComparison,
)
from bond_management.bond_management.utils.statement_quantity_report import (
    build_quantity_reconciliation_pdf,
)
from bond_management.patches.add_bond_query_indexes import STATEMENT_ATTACHMENT_UNIQUE
from bond_management.patches.backfill_statement_reconciliation_statuses import (
    execute as backfill_reconciliation_statuses,
)
from bond_management.patches.regenerate_legacy_face_value_reconciliations import (
    execute as regenerate_legacy_reconciliations,
)
from bond_management.patches.remove_duplicate_bond_statements import (
    execute as remove_duplicate_statements,
)
from bond_management.patches.remove_duplicate_bond_statements import (
    get_redundant_statement_names,
)
from bond_management.patches.standardize_bond_statement_attachment_names import (
    execute as standardize_existing_statement_attachments,
)


class TestBondStatement(IntegrationTestCase):
    def setUp(self):
        super().setUp()
        self._report_files_before = set(self._quantity_report_files())

    def tearDown(self):
        try:
            for report_path in set(self._quantity_report_files()) - self._report_files_before:
                report_path.unlink(missing_ok=True)
        finally:
            super().tearDown()

    def test_populates_holdings_from_portfolio_position(self):
        bond = make_bond()
        portfolio = make_portfolio()
        make_transaction(bond, portfolio)
        make_market_date(bond)

        statement = make_statement(portfolio)

        self.assertEqual(len(statement.bond_statement_details), 1)
        detail = statement.bond_statement_details[0]
        self.assertEqual(detail.isin, bond.name)
        self.assertEqual(detail.quantity, 10)
        self.assertEqual(detail.market_price, 100)

    def test_missing_market_price_is_blank_instead_of_zero(self):
        bond = make_bond()
        portfolio = make_portfolio()
        make_transaction(bond, portfolio)

        statement = make_statement(portfolio)

        self.assertIsNone(statement.bond_statement_details[0].market_price)

    def test_clearing_an_input_clears_previously_generated_rows(self):
        statement = frappe.get_doc(
            {
                "doctype": "Bond Statement",
                "portfolio_name": make_portfolio().name,
                "statement_date": "2025-12-31",
                "bond_statement_details": [{"isin": make_bond().name, "quantity": 10, "market_price": 100}],
            }
        )

        statement.portfolio_name = None
        statement.populate_holdings()

        self.assertEqual(statement.bond_statement_details, [])

    def test_attachment_populates_current_and_legacy_statement_formats(self):
        cases = (
            (
                "Portfolio Summary as of 30/06/2026\nProduct Account No.: {account_no}",
                "2026-06-30",
            ),
            (
                "SUMMARY OF ACCOUNT As of 30/09/2021\nIS Account : {account_no}",
                "2021-09-30",
            ),
        )
        for statement_text, expected_date in cases:
            with self.subTest(statement_date=expected_date):
                account_no = unique_name("PDF-ACCOUNT")
                password = unique_name("PDF-PASSWORD")
                portfolio = make_portfolio(
                    account_no=account_no,
                    statement_pdf_password=password,
                )
                attachment = self._attach_pdf(
                    statement_text.format(account_no=account_no),
                    password,
                )
                statement = frappe.get_doc(
                    {
                        "doctype": "Bond Statement",
                        "attachment": attachment,
                    }
                )

                preview = statement.read_statement_pdf()
                self.assertEqual(preview["portfolio_name"], portfolio.name)
                self.assertEqual(preview["statement_date"].isoformat(), expected_date)
                self.assertEqual(preview["account_no"], account_no)

                statement.insert()
                self.assertEqual(statement.portfolio_name, portfolio.name)
                self.assertEqual(statement.statement_date.isoformat(), expected_date)
                self.assertEqual(
                    statement.attachment,
                    f"/private/files/PortfolioStatement-{account_no}-{expected_date.replace('-', '')}.pdf",
                )

                attachment_files = frappe.qb.get_query(
                    "File",
                    fields=[
                        "file_name",
                        "attached_to_doctype",
                        "attached_to_name",
                        "attached_to_field",
                    ],
                    filters={"file_url": statement.attachment},
                    limit=1,
                    ignore_permissions=False,
                ).run(as_dict=True)
                self.assertEqual(len(attachment_files), 1)
                self.assertEqual(
                    attachment_files[0].file_name,
                    statement.attachment.removeprefix("/private/files/"),
                )
                self.assertEqual(attachment_files[0].attached_to_doctype, "Bond Statement")
                self.assertEqual(attachment_files[0].attached_to_name, statement.name)
                self.assertEqual(attachment_files[0].attached_to_field, "attachment")

    def test_attachment_upserts_exchange_rates_and_preserves_manual_fallbacks(self):
        account_no = unique_name("FX-ACCOUNT")
        password = unique_name("FX-PASSWORD")
        portfolio = make_portfolio(
            account_no=account_no,
            statement_pdf_password=password,
        )
        manual_rate = make_exchange_rate(
            portfolio,
            rate_date="2026-05-31",
            rate="0.00770000",
        )
        attachment = self._attach_pdf(
            "\n".join(
                [
                    "Portfolio Summary as of 30/06/2026",
                    f"Product Account No.: {account_no}",
                    "Currency Pair Rate",
                    "KES / USD 0.00772499",
                ]
            ),
            password,
        )

        statement = frappe.get_doc({"doctype": "Bond Statement", "attachment": attachment}).insert()

        parsed_rate = frappe.qb.get_query(
            "Bond Exchange Rate",
            fields=["rate", "source", "statement"],
            filters={
                "portfolio_name": portfolio.name,
                "rate_date": "2026-06-30",
                "from_currency": "KES",
            },
            limit=1,
            ignore_permissions=False,
        ).run(as_dict=True)[0]
        self.assertEqual(parsed_rate.rate, 0.00772499)
        self.assertEqual(parsed_rate.source, "Statement PDF")
        self.assertEqual(parsed_rate.statement, statement.name)

        manual_rate.reload()
        self.assertEqual(manual_rate.source, "Manual")
        self.assertEqual(manual_rate.rate, 0.0077)

    def test_attachment_accepts_transaction_account_and_keeps_product_account_filename(self):
        product_account_no = unique_name("PRODUCT-ACCOUNT")
        transaction_account_no = unique_name("TRANSACTION-ACCOUNT")
        password = unique_name("PDF-PASSWORD")
        portfolio = make_portfolio(
            account_no=product_account_no,
            transaction_account_no=transaction_account_no,
            statement_pdf_password=password,
        )
        attachment = self._attach_pdf(
            f"Portfolio Summary as of 30/06/2026\nProduct Account No.: {transaction_account_no}",
            password,
        )

        statement = frappe.get_doc(
            {
                "doctype": "Bond Statement",
                "attachment": attachment,
            }
        ).insert()

        self.assertEqual(statement.portfolio_name, portfolio.name)
        self.assertEqual(statement.statement_date.isoformat(), "2026-06-30")
        self.assertEqual(
            statement.attachment,
            f"/private/files/PortfolioStatement-{product_account_no}-20260630.pdf",
        )

    def test_accountless_pdf_uses_explicitly_selected_portfolio(self):
        portfolio = make_portfolio(statement_pdf_password="test-password")
        attachment = self._attach_pdf(
            "SUMMARY OF ACCOUNT As of 30/11/2020",
            "test-password",
            file_name="KEUTS03Dec20075717763794.pdf",
        )

        statement = frappe.get_doc(
            {
                "doctype": "Bond Statement",
                "portfolio_name": portfolio.name,
                "attachment": attachment,
            }
        )

        preview = statement.read_statement_pdf()

        self.assertEqual(preview["portfolio_name"], portfolio.name)
        self.assertEqual(preview["account_no"], portfolio.account_no)
        self.assertEqual(preview["statement_date"].isoformat(), "2020-11-30")
        statement.insert()

    def test_legacy_named_bond_row_populates_market_price(self):
        bond = make_bond(bond_name="Kenya Treasury Bond FXD3-2019-15")
        portfolio = make_portfolio()
        make_transaction(bond, portfolio)
        attachment = self._attach_pdf(
            "\n".join(
                [
                    f"Portfolio Summary as of 31/12/2025 Product Account No.: {portfolio.account_no}",
                    "FXD3/2019/15 USD 10 104.000000 0.00000000 98.965410 1,040.00 989.65 01/01/2027",
                ]
            ),
            "test-password",
        )

        statement = frappe.get_doc({"doctype": "Bond Statement", "attachment": attachment}).insert()

        self.assertEqual(statement.bond_statement_details[0].isin, bond.name)
        self.assertEqual(statement.bond_statement_details[0].market_price, Decimal("98.965410"))

    def test_rejects_duplicate_attachment_in_controller_and_database(self):
        account_no = unique_name("DUPLICATE-ACCOUNT")
        password = unique_name("PDF-PASSWORD")
        portfolio = make_portfolio(
            account_no=account_no,
            statement_pdf_password=password,
        )
        attachment = self._attach_pdf(
            f"Portfolio Summary as of 30/06/2026\nProduct Account No.: {account_no}",
            password,
        )
        statement = frappe.get_doc(
            {
                "doctype": "Bond Statement",
                "attachment": attachment,
            }
        ).insert()

        duplicate = frappe.get_doc(
            {
                "doctype": "Bond Statement",
                "attachment": statement.attachment,
            }
        )
        with self.assertRaisesRegex(frappe.ValidationError, f"already used.*{statement.name}"):
            duplicate.insert()

        self.assertTrue(frappe.db.has_index("tabBond Statement", STATEMENT_ATTACHMENT_UNIQUE))
        database_duplicate = frappe.get_doc(
            {
                "doctype": "Bond Statement",
                "portfolio_name": portfolio.name,
                "statement_date": statement.statement_date,
                "attachment": statement.attachment,
            }
        )
        with self.assertRaises(frappe.UniqueValidationError):
            database_duplicate.db_insert()

    def test_duplicate_cleanup_keeps_the_earliest_statement(self):
        rows = [
            frappe._dict(
                name="BS-NEWER",
                attachment="/private/files/duplicate.pdf",
                creation="2026-07-31 18:20:00",
            ),
            frappe._dict(
                name="BS-ONLY",
                attachment="/private/files/only.pdf",
                creation="2026-07-31 18:21:00",
            ),
            frappe._dict(
                name="BS-OLDER",
                attachment="/private/files/duplicate.pdf",
                creation="2026-07-31 18:10:00",
            ),
        ]

        self.assertEqual(get_redundant_statement_names(rows), ["BS-NEWER"])

    def test_duplicate_cleanup_runs_before_unique_index_patch(self):
        patch_lines = Path(frappe.get_app_path("bond_management", "patches.txt")).read_text().splitlines()
        cleanup_index = patch_lines.index("bond_management.patches.remove_duplicate_bond_statements")
        index_patch_index = patch_lines.index("bond_management.patches.add_bond_query_indexes")
        self.assertLess(cleanup_index, index_patch_index)

        events = []
        rows = [
            frappe._dict(
                name="BS-NEWER",
                attachment="/private/files/duplicate.pdf",
                creation="2026-07-31 18:20:00",
            ),
            frappe._dict(
                name="BS-OLDER",
                attachment="/private/files/duplicate.pdf",
                creation="2026-07-31 18:10:00",
            ),
        ]
        with (
            patch(
                "bond_management.patches.remove_duplicate_bond_statements.frappe.qb.get_query"
            ) as get_query,
            patch("bond_management.patches.remove_duplicate_bond_statements.frappe.delete_doc") as delete_doc,
            patch(
                "bond_management.patches.remove_duplicate_bond_statements.ensure_bond_query_indexes"
            ) as ensure_indexes,
        ):
            get_query.return_value.run.return_value = rows
            delete_doc.side_effect = lambda *args, **kwargs: events.append("delete")
            ensure_indexes.side_effect = lambda: events.append("index")

            remove_duplicate_statements()

        self.assertEqual(events, ["delete", "index"])

    def test_rejects_unconfigured_passwords_and_unknown_accounts(self):
        configured_password = unique_name("CONFIGURED-PASSWORD")
        portfolio = make_portfolio(statement_pdf_password=configured_password)
        wrong_password_attachment = self._attach_pdf(
            f"Portfolio Summary as of 30/06/2026\nProduct Account No.: {portfolio.account_no}",
            unique_name("OTHER-PASSWORD"),
        )

        with self.assertRaisesRegex(
            frappe.ValidationError,
            "configured Bond Portfolio password",
        ):
            frappe.get_doc(
                {
                    "doctype": "Bond Statement",
                    "attachment": wrong_password_attachment,
                }
            ).insert()

        unknown_account_attachment = self._attach_pdf(
            "Portfolio Summary as of 30/06/2026\nProduct Account No.: UNKNOWN-ACCOUNT",
            configured_password,
        )
        with self.assertRaisesRegex(frappe.ValidationError, "No accessible Bond Portfolio"):
            frappe.get_doc(
                {
                    "doctype": "Bond Statement",
                    "attachment": unknown_account_attachment,
                }
            ).insert()

    def test_legacy_statement_uses_original_filename_when_pdf_omits_account(self):
        account_no = unique_name("LEGACY-ACCOUNT")
        portfolio = make_portfolio(
            account_no=account_no,
            statement_pdf_password="test-password",
        )
        attachment = self._attach_pdf(
            "SUMMARY OF ACCOUNT As of 31/10/2022",
            "test-password",
            file_name=f"PortfolioStatement-{portfolio.account_no}-20221031.pdf",
        )

        statement = frappe.get_doc(
            {
                "doctype": "Bond Statement",
                "attachment": attachment,
            }
        ).insert()

        self.assertEqual(statement.portfolio_name, portfolio.name)
        self.assertEqual(statement.statement_date.isoformat(), "2022-10-31")

    def test_patch_standardizes_an_existing_statement_attachment(self):
        account_no = unique_name("PATCH-ACCOUNT")
        portfolio = make_portfolio(account_no=account_no)
        attachment = self._attach_pdf(
            f"Portfolio Summary as of 31/03/2034\nProduct Account No.: {account_no}",
            "test-password",
            file_name=f"{unique_name('old-statement-name')}.pdf",
        )
        statement = frappe.get_doc(
            {
                "doctype": "Bond Statement",
                "portfolio_name": portfolio.name,
                "statement_date": "2034-03-31",
                "attachment": attachment,
            }
        )
        statement.flags.ignore_statement_pdf = True
        statement.insert()
        self.assertEqual(statement.attachment, attachment)

        standardize_existing_statement_attachments([statement.name])
        statement.reload()

        expected_url = f"/private/files/PortfolioStatement-{account_no}-20340331.pdf"
        self.assertEqual(statement.attachment, expected_url)
        standardized_files = frappe.qb.get_query(
            "File",
            fields=["file_name", "attached_to_name", "attached_to_field"],
            filters={"file_url": expected_url},
            limit=1,
            ignore_permissions=False,
        ).run(as_dict=True)
        self.assertEqual(len(standardized_files), 1)
        self.assertEqual(standardized_files[0].file_name, expected_url.removeprefix("/private/files/"))
        self.assertEqual(standardized_files[0].attached_to_name, statement.name)
        self.assertEqual(standardized_files[0].attached_to_field, "attachment")

        standardize_existing_statement_attachments([statement.name])
        statement.reload()
        self.assertEqual(statement.attachment, expected_url)

    def test_pdf_managed_fields_are_read_only_and_cannot_be_changed_directly(self):
        account_no = unique_name("PDF-ACCOUNT")
        password = unique_name("PDF-PASSWORD")
        make_portfolio(
            account_no=account_no,
            statement_pdf_password=password,
        )
        attachment = self._attach_pdf(
            f"Portfolio Summary as of 30/06/2026\nProduct Account No.: {account_no}",
            password,
        )
        statement = frappe.get_doc(
            {
                "doctype": "Bond Statement",
                "attachment": attachment,
            }
        ).insert()

        self.assertTrue(statement.meta.get_field("portfolio_name").read_only)
        self.assertTrue(statement.meta.get_field("statement_date").read_only)
        self.assertTrue(statement.meta.get_field("market_price_posting").read_only)
        self.assertTrue(statement.meta.get_field("quantity_reconciliation_report").read_only)
        self.assertTrue(statement.meta.get_field("reconciliation_status").read_only)
        self.assertTrue(statement.meta.get_field("attachment").reqd)

        statement.statement_date = "2026-05-31"
        with self.assertRaisesRegex(frappe.ValidationError, "managed from the attached PDF"):
            statement.save()

    def test_requires_a_pdf_attachment(self):
        with self.assertRaisesRegex(frappe.ValidationError, "Attach a PDF statement"):
            frappe.get_doc({"doctype": "Bond Statement"}).insert()

    def test_attachment_updates_existing_prices_adds_rows_and_links_posting(self):
        statement_date = "2040-06-30"
        portfolio = make_portfolio()
        first_bond = self._make_long_dated_bond()
        second_bond = self._make_long_dated_bond()
        unrelated_bond = self._make_long_dated_bond()
        unmanaged_isin = f"XS{frappe.generate_hash(length=10).upper()}"
        make_transaction(first_bond, portfolio)
        make_transaction(second_bond, portfolio)
        market_date = make_market_date(first_bond, market_price=90, date=statement_date)
        make_market_date(unrelated_bond, market_price=88, date=statement_date)
        attachment = self._attach_pdf(
            self._current_statement_text(
                portfolio.account_no,
                statement_date="30/06/2040",
                prices={
                    first_bond.name: "101.123456",
                    second_bond.name: "99.654321",
                    unmanaged_isin: "98.500000",
                },
            ),
            "test-password",
        )

        statement = frappe.get_doc(
            {
                "doctype": "Bond Statement",
                "attachment": attachment,
            }
        ).insert()

        self.assertEqual(statement.market_price_posting, market_date.name)
        statement_prices = {
            row.isin: Decimal(str(row.market_price)) for row in statement.bond_statement_details
        }
        self.assertEqual(statement_prices[first_bond.name], Decimal("101.123456"))
        self.assertEqual(statement_prices[second_bond.name], Decimal("99.654321"))

        market_date.reload()
        posted_prices = {row.isin: Decimal(str(row.market_price)) for row in market_date.bond_market_prices}
        self.assertEqual(posted_prices[first_bond.name], Decimal("101.123456"))
        self.assertEqual(posted_prices[second_bond.name], Decimal("99.654321"))
        self.assertEqual(posted_prices[unrelated_bond.name], Decimal("88"))
        self.assertNotIn(unmanaged_isin, posted_prices)

    def test_attachment_creates_and_links_a_missing_market_price_posting(self):
        portfolio = make_portfolio()
        bond = self._make_long_dated_bond(maturity_date="2043-01-01")
        make_transaction(bond, portfolio)
        attachment = self._attach_pdf(
            self._current_statement_text(
                portfolio.account_no,
                statement_date="30/06/2041",
                prices={bond.name: "102.750000"},
            ),
            "test-password",
        )

        statement = frappe.get_doc(
            {
                "doctype": "Bond Statement",
                "attachment": attachment,
            }
        ).insert()

        self.assertTrue(statement.market_price_posting)
        market_date = frappe.get_doc("Bond Market Date", statement.market_price_posting)
        self.assertEqual(market_date.date.isoformat(), "2041-06-30")
        self.assertEqual(len(market_date.bond_market_prices), 1)
        self.assertEqual(market_date.bond_market_prices[0].isin, bond.name)
        self.assertEqual(
            Decimal(str(market_date.bond_market_prices[0].market_price)),
            Decimal("102.750000"),
        )

    def test_reports_quantity_mismatch_on_insert_and_unchanged_update(self):
        portfolio = make_portfolio()
        bond = self._make_long_dated_bond()
        make_transaction(bond, portfolio, quantity_face_value=15)
        attachment = self._attach_pdf(
            self._current_statement_text(
                portfolio.account_no,
                statement_date="30/06/2039",
                prices={bond.name: "101.250000"},
            ),
            "test-password",
        )
        statement = frappe.get_doc(
            {
                "doctype": "Bond Statement",
                "attachment": attachment,
            }
        )

        with patch("frappe.msgprint") as msgprint:
            statement.insert()

        msgprint.assert_called_once()
        rows = msgprint.call_args.args[0]
        self.assertEqual(rows[0], ["ISIN", "PDF Quantity", "Calculated Quantity", "Difference"])
        self.assertEqual(rows[1], [bond.name, "10", "15", "-5"])
        self.assertEqual(msgprint.call_args.kwargs["indicator"], "orange")
        self.assertTrue(msgprint.call_args.kwargs["as_table"])
        first_report_url = statement.quantity_reconciliation_report
        report_text = self._read_reconciliation_report(first_report_url, "test-password")
        self.assertIn("DISCREPANCIES FOUND", report_text)
        self.assertIn(bond.name, report_text)
        self.assertIn("-5", report_text)
        self.assertIn("MISMATCH", report_text)
        self.assertEqual(statement.reconciliation_status, "Mismatched")

        statement.reload()
        with patch("frappe.msgprint") as update_msgprint:
            statement.save()

        update_msgprint.assert_called_once()
        self.assertEqual(update_msgprint.call_args.args[0][1], [bond.name, "10", "15", "-5"])
        self.assertNotEqual(statement.quantity_reconciliation_report, first_report_url)
        self._read_reconciliation_report(statement.quantity_reconciliation_report, "test-password")

    def test_legacy_face_value_is_rescaled_by_face_value_per_unit(self):
        portfolio = make_portfolio()
        bond = self._make_long_dated_bond(face_value_per_unit=100)
        make_transaction(bond, portfolio, quantity_face_value=2000)
        attachment = self._attach_pdf(
            "\n".join(
                [
                    f"SUMMARY OF ACCOUNT As of 30/06/2038 IS Account: {portfolio.account_no}",
                    bond.name,
                    "USD 200,000.00 99.000000 7.000000 101.250000 198,000.00 202,500.00 01/01/2042",
                ]
            ),
            "test-password",
        )

        with patch("frappe.msgprint") as msgprint:
            statement = frappe.get_doc(
                {
                    "doctype": "Bond Statement",
                    "attachment": attachment,
                }
            ).insert()

        msgprint.assert_not_called()
        report_text = self._read_reconciliation_report(
            statement.quantity_reconciliation_report,
            "test-password",
        )
        self.assertIn("Status:     MATCHED", report_text)
        self.assertIn("No quantity discrepancies found.", report_text)
        self.assertIn("Matched:    1", report_text)
        self.assertIn(f"{bond.name}", report_text)
        self.assertIn("2,000", report_text)
        self.assertIn("MATCHED", report_text)
        self.assertEqual(statement.reconciliation_status, "Matched")

        regenerate_legacy_reconciliations([statement.name])
        statement.reload()
        versioned_report_url = statement.quantity_reconciliation_report
        self.assertIn("FaceValue-v2", versioned_report_url)
        self._read_reconciliation_report(versioned_report_url, "test-password")

        regenerate_legacy_reconciliations([statement.name])
        statement.reload()
        self.assertEqual(statement.quantity_reconciliation_report, versioned_report_url)

        backfill_reconciliation_statuses([statement.name])
        statement.reload()
        quantity_basis_report_url = statement.quantity_reconciliation_report
        self.assertIn("QuantityBasis-v4", quantity_basis_report_url)
        self.assertEqual(statement.reconciliation_status, "Matched")

        backfill_reconciliation_statuses([statement.name])
        statement.reload()
        self.assertEqual(statement.quantity_reconciliation_report, quantity_basis_report_url)

    def test_legacy_face_value_column_can_contain_units_without_rescaling(self):
        portfolio = make_portfolio()
        bond = self._make_long_dated_bond(face_value_per_unit=100)
        make_transaction(bond, portfolio, quantity_face_value=2000)
        attachment = self._attach_pdf(
            "\n".join(
                [
                    f"SUMMARY OF ACCOUNT As of 31/03/2038 IS Account: {portfolio.account_no}",
                    bond.name,
                    "USD 2,000.00 99.250000 0.00000000 110.000000 198,500.00 220,000.00 01/01/2042",
                ]
            ),
            "test-password",
        )

        statement = frappe.get_doc(
            {
                "doctype": "Bond Statement",
                "attachment": attachment,
            }
        ).insert()

        self.assertEqual(statement.reconciliation_status, "Matched")
        report_text = self._read_reconciliation_report(
            statement.quantity_reconciliation_report,
            "test-password",
        )
        self.assertRegex(report_text, rf"{bond.name}.*2,000.*2,000.*0.*MATCHED")

    def test_reconciliation_report_lists_matched_and_mismatched_isins(self):
        portfolio = make_portfolio()
        matched_bond = self._make_long_dated_bond()
        mismatched_bond = self._make_long_dated_bond()
        make_transaction(matched_bond, portfolio, quantity_face_value=10)
        make_transaction(mismatched_bond, portfolio, quantity_face_value=15)
        attachment = self._attach_pdf(
            self._current_statement_text(
                portfolio.account_no,
                statement_date="30/06/2035",
                prices={
                    matched_bond.name: "101.250000",
                    mismatched_bond.name: "102.500000",
                },
            ),
            "test-password",
        )

        statement = frappe.get_doc(
            {
                "doctype": "Bond Statement",
                "attachment": attachment,
            }
        ).insert()

        report_text = self._read_reconciliation_report(
            statement.quantity_reconciliation_report,
            "test-password",
        )
        self.assertIn("Matched:    1", report_text)
        self.assertIn("Mismatched: 1", report_text)
        self.assertRegex(report_text, rf"{matched_bond.name}.*0\s+MATCHED")
        self.assertRegex(report_text, rf"{mismatched_bond.name}.*-5\s+MISMATCH")

    def test_reconciliation_report_shows_calculated_only_isin(self):
        comparison = StatementQuantityComparison(
            isin="KE6000008430",
            pdf_quantity=None,
            calculated_quantity=Decimal("200000"),
            difference=Decimal("-200000"),
        )

        content = build_quantity_reconciliation_pdf(
            statement_name="BS-TEST",
            portfolio_name="Amrat",
            statement_date="2025-04-30",
            generated_at="2026-08-06 12:00:00",
            comparisons=(comparison,),
            password="test-password",
        )
        reader = PdfReader(BytesIO(content))
        self.assertGreater(reader.decrypt("test-password"), 0)
        report_text = "\n".join(page.extract_text() or "" for page in reader.pages)

        self.assertIn("Not present", report_text)
        self.assertIn("200,000", report_text)
        self.assertIn("-200,000", report_text)
        self.assertIn("MISMATCH", report_text)

    def test_reports_when_pdf_quantity_is_greater_than_calculated_quantity(self):
        portfolio = make_portfolio()
        bond = self._make_long_dated_bond()
        make_transaction(bond, portfolio, quantity_face_value=5)
        attachment = self._attach_pdf(
            self._current_statement_text(
                portfolio.account_no,
                statement_date="30/06/2036",
                prices={bond.name: "101.250000"},
            ),
            "test-password",
        )

        with patch("frappe.msgprint") as msgprint:
            statement = frappe.get_doc(
                {
                    "doctype": "Bond Statement",
                    "attachment": attachment,
                }
            ).insert()

        self.assertEqual(msgprint.call_args.args[0][1], [bond.name, "10", "5", "5"])
        report_text = self._read_reconciliation_report(
            statement.quantity_reconciliation_report,
            "test-password",
        )
        self.assertIn("5", report_text)

    def test_reconciliation_report_requires_portfolio_password(self):
        portfolio = make_portfolio(statement_pdf_password=None)
        attachment = self._attach_pdf(
            f"Portfolio Summary as of 30/06/2037\nProduct Account No.: {portfolio.account_no}",
            None,
        )

        with self.assertRaisesRegex(frappe.ValidationError, "Configure Statement PDF Password"):
            frappe.get_doc(
                {
                    "doctype": "Bond Statement",
                    "attachment": attachment,
                }
            ).insert()

    def _attach_pdf(self, text, password, file_name=None):
        file_doc = frappe.get_doc(
            {
                "doctype": "File",
                "file_name": file_name or f"{unique_name('statement')}.pdf",
                "content": make_text_pdf(text, password),
                "is_private": 1,
            }
        ).insert()
        self.addCleanup(Path(file_doc.get_full_path()).unlink, missing_ok=True)
        return file_doc.file_url

    def _quantity_report_files(self):
        private_files = Path(frappe.get_site_path("private", "files"))
        return private_files.glob("Bond-Quantity-Reconciliation-*.pdf")

    def _read_reconciliation_report(self, file_url, password):
        file_names = frappe.qb.get_query(
            "File",
            fields=["name"],
            filters={"file_url": file_url},
            limit=1,
            ignore_permissions=False,
        ).run(pluck=True)
        self.assertTrue(file_names)
        content = Path(frappe.get_doc("File", file_names[0]).get_full_path()).read_bytes()
        reader = PdfReader(BytesIO(content))
        self.assertTrue(reader.is_encrypted)
        self.assertEqual(reader.decrypt("wrong-password"), 0)
        reader = PdfReader(BytesIO(content))
        self.assertGreater(reader.decrypt(password), 0)
        return "\n".join(page.extract_text() or "" for page in reader.pages)

    def _make_long_dated_bond(self, **overrides):
        isin = f"XS{frappe.generate_hash(length=10).upper()}"
        values = {
            "isin": isin,
            "bond_name": isin,
            "maturity_date": "2042-01-01",
            "principal_schedule": [
                {
                    "repayment_date": "2042-01-01",
                    "principal_units": 100,
                }
            ],
        }
        values.update(overrides)
        return make_bond(**values)

    def _current_statement_text(self, account_no, statement_date, prices):
        rows = []
        for isin, market_price in prices.items():
            rows.append(
                f"REPUBLIC OF KENYA - {isin} USD {isin} "
                f"10.000000 100 99.000000 990.00 "
                f"{statement_date} {market_price} 1,000.00"
            )
        return "\n".join(
            [
                f"Portfolio Summary as of {statement_date}",
                f"Product Account No.: {account_no}",
                *rows,
            ]
        )
