import inspect

from frappe.tests import UnitTestCase

from bond_management.bond_management.api import investor, investor_reports

EXPECTED_FIELD_ALLOWLISTS = {
    "BOND_COUPON_FIELDS",
    "BOND_DETAIL_FIELDS",
    "BOND_LIST_FIELDS",
    "BOND_PRINCIPAL_FIELDS",
    "BOND_SCALAR_FIELDS",
    "BOND_YIELD_COMPARISON_FIELDS",
    "EXCHANGE_RATE_DETAIL_FIELDS",
    "EXCHANGE_RATE_LIST_FIELDS",
    "MARKET_DATE_DETAIL_FIELDS",
    "MARKET_DATE_LIST_FIELDS",
    "MARKET_PRICE_FIELDS",
    "PORTFOLIO_CASHFLOW_FIELDS",
    "PORTFOLIO_PERFORMANCE_COLUMN_FIELDS",
    "PORTFOLIO_PERFORMANCE_ROW_FIELDS",
    "STATEMENT_DETAIL_FIELDS",
    "STATEMENT_HOLDING_FIELDS",
    "STATEMENT_LIST_FIELDS",
    "TRANSACTION_DETAIL_FIELDS",
    "TRANSACTION_LIST_FIELDS",
}
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


class TestInvestorResponseBoundary(UnitTestCase):
    def test_every_response_field_allowlist_omits_attachment_metadata(self):
        allowlists = self._field_allowlists()

        self.assertEqual(set(allowlists), EXPECTED_FIELD_ALLOWLISTS)
        for allowlist_name, fields in allowlists.items():
            with self.subTest(allowlist=allowlist_name):
                for field in fields:
                    self.assertFalse(
                        any(part in field for part in FORBIDDEN_FILE_FIELD_PARTS),
                        f"{allowlist_name} exposes attachment or private-file field {field!r}",
                    )

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
