from decimal import Decimal

import frappe
from frappe.tests import IntegrationTestCase

from bond_management.bond_management.report.bond_yield_comparison.bond_yield_comparison import (
    execute,
    get_columns,
)
from bond_management.bond_management.tests.factories import make_bond, make_market_date


class TestBondYieldComparison(IntegrationTestCase):
    def test_columns_describe_market_snapshot_and_stored_future_xirr(self):
        columns = get_columns()
        fieldnames = [column["fieldname"] for column in columns]

        self.assertEqual(fieldnames, ["date", "isin", "currency", "market_price", "future_xirr"])
        self.assertEqual(
            next(column for column in columns if column["fieldname"] == "future_xirr")["fieldtype"],
            "Percent",
        )

    def test_selected_bonds_are_ordered_and_date_bounds_are_inclusive(self):
        usd_bond = make_bond()
        kes_bond = make_bond(currency="KES")
        first_date = make_market_date(usd_bond, date="2025-01-01")
        make_market_date(kes_bond, market_date=first_date)
        second_date = make_market_date(usd_bond, date="2025-02-01")
        make_market_date(kes_bond, market_date=second_date)

        rows = execute(
            {
                "bonds": [kes_bond.name, usd_bond.name],
                "from_date": "2025-01-01",
                "to_date": "2025-01-01",
            }
        )[1]

        self.assertEqual(
            [(row.date.isoformat(), row.isin) for row in rows],
            [("2025-01-01", isin) for isin in sorted((kes_bond.name, usd_bond.name))],
        )
        self.assertEqual({row.currency for row in rows}, {"USD", "KES"})

    def test_report_returns_persisted_future_xirr_without_recalculation(self):
        bond = make_bond()
        market_date = make_market_date(bond, date="2025-03-01")
        price_row = market_date.bond_market_prices[-1]
        frappe.db.set_value(
            "Bond Market Prices",
            price_row.name,
            "future_xirr",
            "17.125",
            update_modified=False,
        )

        rows = execute({"bonds": [bond.name]})[1]

        self.assertEqual(len(rows), 1)
        self.assertEqual(Decimal(str(rows[0].future_xirr)), Decimal("17.125"))

    def test_empty_selection_returns_all_readable_bonds(self):
        usd_bond = make_bond()
        kes_bond = make_bond(currency="KES")
        market_date = make_market_date(usd_bond, date="2025-04-01")
        make_market_date(kes_bond, market_date=market_date)

        rows = execute({"bonds": []})[1]

        self.assertEqual({row.isin for row in rows}, {usd_bond.name, kes_bond.name})

    def test_report_filters_reject_invalid_types_and_ranges(self):
        invalid_filters = [
            ({"bonds": "not-a-list"}, "Bonds must be a list"),
            ({"bonds": [[]]}, "Every selected bond must be a non-empty string"),
            (
                {"from_date": "2025-02-01", "to_date": "2025-01-01"},
                "From Date must be on or before To Date",
            ),
        ]
        for filters, message in invalid_filters:
            with self.subTest(filters=filters):
                with self.assertRaisesRegex(frappe.ValidationError, message):
                    execute(filters)

        with self.assertRaisesRegex(frappe.ValidationError, "From Date must be a string"):
            execute({"from_date": []})

    def test_selected_unknown_bond_is_rejected_at_permission_boundary(self):
        with self.assertRaises(frappe.PermissionError):
            execute({"bonds": ["UNKNOWN-BOND"]})
