import frappe
from frappe.tests import IntegrationTestCase

from bond_management.bond_management.tests.factories import make_bond, make_market_date
from bond_management.patches.backfill_market_xirr_availability import execute


class TestBackfillMarketXirrAvailability(IntegrationTestCase):
    def test_legacy_backfill_distinguishes_all_yields_and_preserves_other_fields_on_rerun(self):
        snapshot = None
        cases = []
        for price in (100, 90, 110):
            bond = make_bond(coupon_rate=0)
            snapshot = (
                make_market_date(bond, price, date="2025-11-22")
                if snapshot is None
                else make_market_date(bond, price, market_date=snapshot)
            )
            snapshot.reload()
            row = next(row for row in snapshot.bond_market_prices if row.isin == bond.name)
            cases.append((row.name, row.future_xirr, 1))
        matured = make_market_date(make_bond(coupon_rate=0), date="2027-01-05")
        cases.append((matured.bond_market_prices[0].name, 0, 0))
        # Legacy imports can contain snapshots without the now-required child rows.
        empty = frappe.get_doc({"doctype": "Bond Market Date", "date": "2025-11-23"}).insert(
            ignore_mandatory=True
        )

        for name, _, _ in cases:
            frappe.db.set_value(
                "Bond Market Prices",
                name,
                {"future_xirr": 0, "future_xirr_available": 0},
                update_modified=False,
            )
        before_rows = {name: self._other_fields(name) for name, _, _ in cases}
        before_parents = {
            parent.name: frappe.db.get_value("Bond Market Date", parent.name, "*", as_dict=True)
            for parent in (snapshot, matured, empty)
        }

        execute()
        first_pass = self._assert_backfilled(cases, before_rows, before_parents)
        execute()
        self.assertEqual(self._assert_backfilled(cases, before_rows, before_parents), first_pass)
        empty.reload()
        self.assertEqual(empty.bond_market_prices, [])

    def _assert_backfilled(self, cases, before_rows, before_parents):
        values = {}
        for name, expected_yield, expected_available in cases:
            row = frappe.get_doc("Bond Market Prices", name)
            self.assertAlmostEqual(row.future_xirr, expected_yield, places=8)
            self.assertEqual(row.future_xirr_available, expected_available)
            self.assertEqual(self._other_fields(name), before_rows[name])
            values[name] = (row.future_xirr, row.future_xirr_available)
        for name, expected in before_parents.items():
            self.assertEqual(frappe.db.get_value("Bond Market Date", name, "*", as_dict=True), expected)
        return values

    @staticmethod
    def _other_fields(name):
        row = frappe.db.get_value("Bond Market Prices", name, "*", as_dict=True)
        return {
            field: value
            for field, value in row.items()
            if field not in {"future_xirr", "future_xirr_available"}
        }
