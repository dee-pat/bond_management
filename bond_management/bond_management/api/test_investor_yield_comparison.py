from contextlib import contextmanager
from decimal import Decimal
from unittest.mock import patch

import frappe
from frappe.exceptions import FrappeTypeError
from frappe.tests import IntegrationTestCase

from bond_management.bond_management.api import investor as investor_api
from bond_management.bond_management.api.investor_reports import (
    BOND_YIELD_COMPARISON_FIELDS,
    YIELD_COMPARISON_CHART,
    get_bond_yield_comparison,
    get_yield_comparison_defaults,
)
from bond_management.bond_management.report.bond_yield_comparison.bond_yield_comparison import (
    execute,
)
from bond_management.bond_management.tests.factories import make_bond, make_market_date, unique_name
from bond_management.bond_management.utils.investor_permissions import INVESTOR_ROLE
from bond_management.bond_management.utils.investor_ui import FEATURE_FLAG

COLUMN_FIELDS = {
    "fieldname",
    "label",
    "fieldtype",
    "options",
    "description",
    "precision",
}


class TestInvestorBondYieldComparison(IntegrationTestCase):
    def test_common_access_gate_protects_report(self):
        unapproved = self._make_user([])
        for method in (get_bond_yield_comparison, get_yield_comparison_defaults):
            with self.subTest(method=method.__name__):
                with self._as_user("Guest"):
                    with self.assertRaises(frappe.AuthenticationError):
                        method()

                with self._as_user(unapproved):
                    with self.assertRaises(frappe.PermissionError):
                        method()

                with self._as_user("Administrator", feature_enabled=False):
                    with self.assertRaises(frappe.PermissionError):
                        method()

    def test_standard_report_and_market_history_permissions_are_required(self):
        investor = self._make_user([INVESTOR_ROLE])

        with self._as_user(investor):
            for method in (get_bond_yield_comparison, get_yield_comparison_defaults):
                with self.subTest(method=method.__name__):
                    with (
                        patch(
                            "frappe.core.doctype.report.report.Report.is_permitted",
                            return_value=False,
                        ),
                        self.assertRaisesRegex(frappe.PermissionError, "access to Report"),
                    ):
                        method()

            original_has_permission = frappe.has_permission

            def deny_market_report(doctype, ptype=None, *args, **kwargs):
                if doctype == "Bond Market Date" and ptype == "report":
                    return False
                return original_has_permission(doctype, ptype, *args, **kwargs)

            with (
                patch.object(frappe, "has_permission", side_effect=deny_market_report),
                self.assertRaisesRegex(frappe.PermissionError, "report on: Bond Market Date"),
            ):
                get_bond_yield_comparison()

    def test_investor_without_portfolio_assignment_can_read_shared_history(self):
        bond, market_date = self._make_market_history()
        investor = self._make_user([INVESTOR_ROLE])
        report_date = market_date.date.isoformat()

        with self._as_user(investor):
            response = get_bond_yield_comparison(report_date, report_date)

        self.assertEqual([row["isin"] for row in response["report"]["rows"]], [bond.name])
        self.assertEqual(response["report"]["rows"][0]["date"], market_date.date)
        self.assertFalse(frappe.db.exists("User Permission", {"user": investor}))

    def test_projection_matches_authoritative_persisted_report(self):
        _, market_date = self._make_market_history()
        investor = self._make_user([INVESTOR_ROLE])
        report_date = market_date.date.isoformat()
        filters = {"from_date": report_date, "to_date": report_date}

        with self._as_user(investor):
            authoritative_columns, authoritative_rows = execute(filters)
            response = get_bond_yield_comparison(report_date, report_date)

        self.assertEqual(set(response), {"report"})
        report = response["report"]
        self.assertEqual(set(report), {"filters", "columns", "rows", "chart"})
        self.assertEqual(report["filters"], filters)
        self.assertEqual(report["chart"], YIELD_COMPARISON_CHART)
        self.assertEqual(
            [column["fieldname"] for column in report["columns"]],
            list(BOND_YIELD_COMPARISON_FIELDS),
        )
        self.assertTrue(all(set(column) == COLUMN_FIELDS for column in report["columns"]))
        self.assertEqual(
            report["rows"],
            [{field: row.get(field) for field in BOND_YIELD_COMPARISON_FIELDS} for row in authoritative_rows],
        )
        self.assertEqual(
            [column["fieldname"] for column in authoritative_columns],
            list(BOND_YIELD_COMPARISON_FIELDS),
        )
        self.assertTrue(all(set(row) == set(BOND_YIELD_COMPARISON_FIELDS) for row in report["rows"]))
        self.assertIs(investor_api.get_bond_yield_comparison, get_bond_yield_comparison)
        self.assertEqual(
            frappe.allowed_http_methods_for_whitelisted_func[get_bond_yield_comparison],
            ["GET"],
        )

    def test_default_dates_use_oldest_readable_history_and_current_date(self):
        bond = make_bond()
        newer = make_market_date(bond)
        older = make_market_date(bond)
        investor = self._make_user([INVESTOR_ROLE])

        with (
            self._as_user(investor),
            patch(
                "bond_management.bond_management.api.investor_reports.get_readable_isins",
                return_value=[bond.name],
            ),
            patch(
                "bond_management.bond_management.api.investor_reports.today",
                return_value="2026-08-26",
            ),
        ):
            response = get_yield_comparison_defaults()

        self.assertEqual(
            response,
            {
                "filters": {
                    "from_date": min(older.date, newer.date).isoformat(),
                    "to_date": "2026-08-26",
                }
            },
        )
        self.assertIs(investor_api.get_yield_comparison_defaults, get_yield_comparison_defaults)
        self.assertEqual(
            frappe.allowed_http_methods_for_whitelisted_func[get_yield_comparison_defaults],
            ["GET"],
        )

    def test_default_dates_allow_empty_readable_history(self):
        investor = self._make_user([INVESTOR_ROLE])

        with (
            self._as_user(investor),
            patch(
                "bond_management.bond_management.api.investor_reports.get_readable_isins",
                return_value=[],
            ),
            patch(
                "bond_management.bond_management.api.investor_reports.today",
                return_value="2026-08-26",
            ),
        ):
            response = get_yield_comparison_defaults()

        self.assertEqual(
            response,
            {"filters": {"from_date": None, "to_date": "2026-08-26"}},
        )

    def test_market_price_and_future_xirr_remain_persisted_values(self):
        _, market_date = self._make_market_history()
        market_row = market_date.bond_market_prices[-1]
        frappe.db.set_value(
            "Bond Market Prices",
            market_row.name,
            {"market_price": "104.625", "future_xirr": "13.875"},
            update_modified=False,
        )
        investor = self._make_user([INVESTOR_ROLE])
        report_date = market_date.date.isoformat()

        with self._as_user(investor):
            row = get_bond_yield_comparison(report_date, report_date)["report"]["rows"][0]

        self.assertEqual(Decimal(str(row["market_price"])), Decimal("104.625"))
        self.assertEqual(Decimal(str(row["future_xirr"])), Decimal("13.875"))

    def test_date_bounds_are_inclusive_and_open_ended(self):
        bond = make_bond()
        last = make_market_date(bond)
        first = make_market_date(bond)
        investor = self._make_user([INVESTOR_ROLE])
        from_date = first.date.isoformat()
        to_date = last.date.isoformat()

        with self._as_user(investor):
            bounded = get_bond_yield_comparison(from_date, to_date)["report"]["rows"]
            from_only = get_bond_yield_comparison(from_date, None)["report"]["rows"]
            to_only = get_bond_yield_comparison(None, to_date)["report"]["rows"]

        expected_dates = [first.date, last.date]
        self.assertEqual([row["date"] for row in bounded], expected_dates)
        self.assertTrue(set(expected_dates).issubset(row["date"] for row in from_only))
        self.assertTrue(set(expected_dates).issubset(row["date"] for row in to_only))

    def test_empty_history_returns_fixed_columns_and_no_rows(self):
        investor = self._make_user([INVESTOR_ROLE])

        with self._as_user(investor):
            report = get_bond_yield_comparison("2099-01-01", "2099-01-02")["report"]

        self.assertEqual(report["rows"], [])
        self.assertEqual(
            [column["fieldname"] for column in report["columns"]],
            list(BOND_YIELD_COMPARISON_FIELDS),
        )

    def test_rejects_invalid_dates_complex_values_and_arbitrary_arguments(self):
        investor = self._make_user([INVESTOR_ROLE])

        with self._as_user(investor):
            with self.assertRaises(frappe.ValidationError):
                get_bond_yield_comparison("not-a-date", None)
            with self.assertRaisesRegex(
                frappe.ValidationError,
                "From Date must be on or before To Date",
            ):
                get_bond_yield_comparison("2025-02-01", "2025-01-01")
            with self.assertRaises(FrappeTypeError):
                get_bond_yield_comparison([], None)
            with self.assertRaises(TypeError):
                get_bond_yield_comparison(None, None, bonds=[])

    @staticmethod
    def _make_market_history():
        bond = make_bond()
        market_date = make_market_date(bond)
        return bond, market_date

    @staticmethod
    def _make_user(roles):
        return (
            frappe.get_doc(
                {
                    "doctype": "User",
                    "email": f"{unique_name('investor-yield-ui').lower()}@example.com",
                    "first_name": "Investor Yield Test",
                    "send_welcome_email": 0,
                    "roles": [{"role": role} for role in roles],
                }
            )
            .insert(ignore_permissions=True)
            .name
        )

    @staticmethod
    @contextmanager
    def _as_user(user, *, feature_enabled=True):
        previous_user = frappe.session.user
        try:
            frappe.set_user(user)
            with patch.dict(frappe.conf, {FEATURE_FLAG: int(feature_enabled)}):
                yield
        finally:
            frappe.set_user(previous_user)
