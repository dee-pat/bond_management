from pathlib import Path
from tempfile import TemporaryDirectory
from unittest.mock import Mock, patch

import frappe
from frappe.tests import UnitTestCase

from bond_management.bond_management.utils.private_attachment import (
    _standardization_lock,
    read_private_pdf_attachment,
    standardize_private_pdf_attachment,
)


class TestPrivateAttachment(UnitTestCase):
    def tearDown(self):
        frappe.db.after_commit.reset()
        frappe.db.after_rollback.reset()
        frappe.local._bond_private_attachment_locks = {}
        super().tearDown()

    def test_reads_binary_pdf_bytes_through_file_api(self):
        file_doc = Mock(
            file_name="statement.pdf",
            file_size=0,
            is_private=True,
        )
        expected_content = b"%PDF-\x00\xffbinary"
        file_doc.get_content.return_value = expected_content

        with (
            patch(
                "bond_management.bond_management.utils.private_attachment._get_file_rows",
                return_value=[frappe._dict(name="FILE-1")],
            ),
            patch(
                "bond_management.bond_management.utils.private_attachment.frappe.get_doc",
                return_value=file_doc,
            ),
        ):
            content, filename = read_private_pdf_attachment(
                "/private/files/statement.pdf",
                max_bytes=1024,
                missing_message="Attach a PDF.",
                extension_message="PDF required.",
                private_message="Private PDF required.",
                size_message="PDF too large.",
            )

        self.assertEqual(content, expected_content)
        self.assertEqual(filename, "statement.pdf")
        file_doc.check_permission.assert_called_once_with("read")
        file_doc.get_content.assert_called_once_with(encodings=())

    def test_rejects_non_string_attachment_url_before_query(self):
        with self.assertRaisesRegex(frappe.ValidationError, "attachment URL must be a string"):
            read_private_pdf_attachment(
                {"file_url": "/private/files/statement.pdf"},
                max_bytes=1024,
                missing_message="Attach a PDF.",
                extension_message="PDF required.",
                private_message="Private PDF required.",
                size_message="PDF too large.",
            )

    def test_rejects_non_private_attachment(self):
        file_doc = Mock(file_name="statement.pdf", file_size=10, is_private=False)

        with (
            patch(
                "bond_management.bond_management.utils.private_attachment._get_file_rows",
                return_value=[frappe._dict(name="FILE-1")],
            ),
            patch(
                "bond_management.bond_management.utils.private_attachment.frappe.get_doc",
                return_value=file_doc,
            ),
            self.assertRaisesRegex(frappe.ValidationError, "Private PDF required"),
        ):
            read_private_pdf_attachment(
                "/private/files/statement.pdf",
                max_bytes=1024,
                missing_message="Attach a PDF.",
                extension_message="PDF required.",
                private_message="Private PDF required.",
                size_message="PDF too large.",
            )

    def test_standardization_renames_local_file_and_updates_attachment(self):
        with TemporaryDirectory() as temporary_directory:
            root = Path(temporary_directory)
            private_files = root / "private" / "files"
            private_files.mkdir(parents=True)
            source_path = private_files / "uploaded.pdf"
            source_path.write_bytes(b"%PDF-1.7\nfixture")

            document = Mock()
            document.doctype = "Bond Statement"
            document.name = "STATEMENT-1"
            document.get.return_value = "/private/files/uploaded.pdf"
            file_doc = Mock(
                file_name="uploaded.pdf",
                file_url="/private/files/uploaded.pdf",
                is_private=True,
                is_remote_file=False,
            )
            file_doc.get_full_path.return_value = str(source_path)

            with (
                patch(
                    "bond_management.bond_management.utils.private_attachment._get_file_rows",
                    return_value=[
                        frappe._dict(
                            name="FILE-1",
                            file_url="/private/files/uploaded.pdf",
                            attached_to_doctype="Bond Statement",
                            attached_to_name="STATEMENT-1",
                            attached_to_field="attachment",
                        )
                    ],
                ),
                patch(
                    "bond_management.bond_management.utils.private_attachment.frappe.get_doc",
                    return_value=file_doc,
                ),
                patch(
                    "bond_management.bond_management.utils.private_attachment.frappe.get_site_path",
                    side_effect=lambda *parts: str(root.joinpath(*parts)),
                ),
            ):
                result = standardize_private_pdf_attachment(document, "PortfolioStatement-1.pdf")

            target_path = private_files / "PortfolioStatement-1.pdf"
            self.assertEqual(result, "/private/files/PortfolioStatement-1.pdf")
            self.assertFalse(source_path.exists())
            self.assertEqual(target_path.read_bytes(), b"%PDF-1.7\nfixture")
            document.set.assert_called_once_with("attachment", result)
            file_doc.save.assert_called_once_with()

            frappe.db.after_commit.run()

    def test_standardization_rejects_remote_file(self):
        document = Mock()
        document.doctype = "Bond Statement"
        document.name = "STATEMENT-1"
        document.get.return_value = "/private/files/uploaded.pdf"
        file_doc = Mock(is_private=True, is_remote_file=True)

        with (
            patch(
                "bond_management.bond_management.utils.private_attachment._get_file_rows",
                return_value=[
                    frappe._dict(
                        name="FILE-1",
                        file_url="/private/files/uploaded.pdf",
                        attached_to_doctype="Bond Statement",
                        attached_to_name="STATEMENT-1",
                        attached_to_field="attachment",
                    )
                ],
            ),
            patch(
                "bond_management.bond_management.utils.private_attachment.frappe.get_doc",
                return_value=file_doc,
            ),
            self.assertRaisesRegex(frappe.ValidationError, "local private file"),
        ):
            standardize_private_pdf_attachment(document, "PortfolioStatement-1.pdf")

        frappe.db.after_rollback.run()

    @patch("bond_management.bond_management.utils.private_attachment.FileLock")
    def test_standardization_lock_is_reentrant_and_releases_after_commit(self, file_lock):
        frappe.db.after_commit.reset()
        frappe.db.after_rollback.reset()
        frappe.local._bond_private_attachment_locks = {}

        with _standardization_lock("/private/files/canonical.pdf"):
            with _standardization_lock("/private/files/canonical.pdf"):
                pass
            file_lock.return_value.release.assert_not_called()

        file_lock.return_value.acquire.assert_called_once_with(timeout=30)
        frappe.db.after_commit.run()
        file_lock.return_value.release.assert_called_once_with()
