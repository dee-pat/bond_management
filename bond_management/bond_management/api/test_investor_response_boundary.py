import inspect

from frappe.tests import UnitTestCase

from bond_management.bond_management.api import investor, investor_reports
from bond_management.bond_management.tests.investor_contracts import EXPECTED_FIELD_ALLOWLISTS

FORBIDDEN_FILE_FIELD_PARTS = (
    "attached_to_",
    "attachment",
    "content_hash",
    "file_",
    "folder",
    "is_private",
    "pdf_password",
    "private_file",
    "quantity_reconciliation_report",
    "uploaded_to_dropbox",
)
ATTACHMENT_ALLOWLISTS = {
    "STATEMENT_DETAIL_FIELDS",
    "STATEMENT_SCALAR_FIELDS",
    "TRANSACTION_DETAIL_FIELDS",
}
RECONCILIATION_REPORT_ALLOWLISTS = {
    "STATEMENT_DETAIL_FIELDS",
    "STATEMENT_SCALAR_FIELDS",
}


class TestInvestorResponseBoundary(UnitTestCase):
    def test_field_allowlists_match_independent_response_contracts(self):
        allowlists = self._field_allowlists()

        self.assertEqual(set(allowlists), set(EXPECTED_FIELD_ALLOWLISTS))
        for name, expected_fields in EXPECTED_FIELD_ALLOWLISTS.items():
            with self.subTest(allowlist=name):
                self.assertEqual(allowlists[name], expected_fields)

    def test_only_transaction_and_statement_projections_expose_approved_file_urls(self):
        allowlists = self._field_allowlists()

        self.assertEqual(set(allowlists), set(EXPECTED_FIELD_ALLOWLISTS))
        for allowlist_name, fields in allowlists.items():
            with self.subTest(allowlist=allowlist_name):
                for field in fields:
                    if field == "attachment" and allowlist_name in ATTACHMENT_ALLOWLISTS:
                        continue
                    if (
                        field == "quantity_reconciliation_report"
                        and allowlist_name in RECONCILIATION_REPORT_ALLOWLISTS
                    ):
                        continue
                    self.assertFalse(
                        any(part in field for part in FORBIDDEN_FILE_FIELD_PARTS),
                        f"{allowlist_name} exposes attachment or private-file field {field!r}",
                    )

        for allowlist_name in ATTACHMENT_ALLOWLISTS:
            self.assertIn("attachment", allowlists[allowlist_name])
        for allowlist_name in RECONCILIATION_REPORT_ALLOWLISTS:
            self.assertIn("quantity_reconciliation_report", allowlists[allowlist_name])

    @staticmethod
    def _field_allowlists() -> dict[str, tuple[str, ...]]:
        return {
            name: value
            for module in (investor, investor_reports)
            for name, value in inspect.getmembers(module)
            if name.endswith("_FIELDS")
            and isinstance(value, tuple)
            and all(isinstance(field, str) for field in value)
        }
