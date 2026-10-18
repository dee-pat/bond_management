import frappe
from frappe.tests import IntegrationTestCase

from bond_management.bond_management.api.investor import get_market_date, get_market_dates
from bond_management.bond_management.tests.factories import (
    allow_user,
    as_investor_user,
    make_bond,
    make_investor_user,
    make_market_date,
    unique_name,
)
from bond_management.bond_management.tests.investor_contracts import (
    MARKET_DATE_DETAIL_FIELDS,
    MARKET_DATE_LIST_FIELDS,
    MARKET_PRICE_FIELDS,
)
from bond_management.bond_management.utils.investor_permissions import (
    BOND_MANAGER_ROLE,
    INVESTOR_ROLE,
)


class TestInvestorMarketDates(IntegrationTestCase):
    def test_investor_without_portfolio_assignment_can_read_shared_history(self):
        market_date = make_market_date(make_bond())
        investor = make_investor_user([INVESTOR_ROLE])

        with as_investor_user(investor):
            response = get_market_dates()

        self.assertIn(market_date.name, {row.name for row in response["data"]})

    def test_list_has_exact_visible_projection(self):
        market_date = make_market_date(make_bond())
        investor = make_investor_user([INVESTOR_ROLE])

        with as_investor_user(investor):
            response = get_market_dates()

        row = next(row for row in response["data"] if row.name == market_date.name)
        self.assertEqual(set(response), {"data", "pagination"})
        self.assertEqual(set(response["pagination"]), {"start", "page_length", "has_more"})
        self.assertEqual(set(row), set(MARKET_DATE_LIST_FIELDS))
        self.assertTrue(all(set(row) == set(MARKET_DATE_LIST_FIELDS) for row in response["data"]))
        self.assertEqual(row.date, market_date.date)
        self.assertNotIn("bond_market_prices", row)
        self.assertNotIn("modified", row)

    def test_detail_has_exact_visible_projection_and_chart_coordinates(self):
        market_date = make_market_date(make_bond(), market_price=103.25)
        investor = make_investor_user([INVESTOR_ROLE])

        with as_investor_user(investor):
            response = get_market_date(market_date.name)

        self.assertEqual(set(response), {"market_date"})
        detail = response["market_date"]
        self.assertEqual(set(detail), set(MARKET_DATE_DETAIL_FIELDS))
        self.assertEqual(detail.date, market_date.date)
        self.assertTrue(detail.bond_market_prices)
        for row in detail.bond_market_prices:
            self.assertEqual(set(row), set(MARKET_PRICE_FIELDS))
        self.assertIsNotNone(detail.bond_market_prices[0]["future_xirr"])
        self.assertIsNotNone(detail.bond_market_prices[0]["weighted_avg_repayment_years"])
        self.assertNotIn("parent", str(response))
        self.assertNotIn("modified", str(response))

    def test_detail_masks_unavailable_stale_yield_and_keeps_available_zero(self):
        unavailable = make_bond(coupon_rate=0)
        available = make_bond(coupon_rate=0)
        snapshot = make_market_date(unavailable, date="2025-11-24")
        make_market_date(available, market_date=snapshot)
        snapshot.reload()
        stale_row = next(row for row in snapshot.bond_market_prices if row.isin == unavailable.name)
        frappe.db.set_value(
            "Bond Market Prices",
            stale_row.name,
            {"future_xirr": 17.125, "future_xirr_available": 0},
            update_modified=False,
        )
        investor = make_investor_user([INVESTOR_ROLE])

        with as_investor_user(investor):
            detail = get_market_date(snapshot.name)["market_date"]

        rows = {row["isin"]: row for row in detail.bond_market_prices}
        self.assertIsNone(rows[unavailable.name]["future_xirr"])
        self.assertEqual(rows[unavailable.name]["future_xirr_available"], 0)
        self.assertEqual(rows[available.name]["future_xirr"], 0)
        self.assertEqual(rows[available.name]["future_xirr_available"], 1)

    def test_detail_rejects_children_outside_bond_user_permissions(self):
        readable = make_bond()
        restricted = make_bond()
        readable_market_date = make_market_date(readable)
        market_date = make_market_date(readable)
        make_market_date(restricted, market_date=market_date)
        investor = make_investor_user([INVESTOR_ROLE])
        allow_user(investor, "Bond Master", readable.name)

        with as_investor_user(investor):
            response = get_market_date(readable_market_date.name)
            self.assertEqual(
                {row["isin"] for row in response["market_date"].bond_market_prices},
                {readable.name},
            )
            with self.assertRaises(frappe.PermissionError):
                get_market_date(market_date.name)

    def test_unreadable_and_unknown_detail_have_same_failure(self):
        readable = make_market_date(make_bond())
        unreadable = make_market_date(make_bond())
        investor = make_investor_user([INVESTOR_ROLE])
        allow_user(investor, "Bond Market Date", readable.name)
        messages = []

        with as_investor_user(investor):
            for name in (unreadable.name, unique_name("UNKNOWN-MARKET-DATE")):
                with self.assertRaises(frappe.PermissionError) as error:
                    get_market_date(name)
                messages.append(str(error.exception))

        self.assertEqual(messages[0], messages[1])

    def test_manager_and_administrator_use_normal_market_date_permissions(self):
        first = make_market_date(make_bond())
        second = make_market_date(make_bond())
        market_dates = {first.name, second.name}
        manager = make_investor_user([BOND_MANAGER_ROLE])

        for user in (manager, "Administrator"):
            with self.subTest(user=user), as_investor_user(user):
                response = get_market_dates()
                self.assertTrue(market_dates.issubset({row.name for row in response["data"]}))

    def test_pagination_is_allow_listed_and_bounded(self):
        newer = make_market_date(make_bond(), date="2099-06-02")
        older = make_market_date(make_bond(), date="2099-06-01")
        investor = make_investor_user([INVESTOR_ROLE])

        with as_investor_user(investor):
            first_page = get_market_dates(page_length="1")

        self.assertEqual(first_page["data"][0].name, newer.name)
        self.assertNotEqual(first_page["data"][0].name, older.name)
        self.assertEqual(
            first_page["pagination"],
            {"start": 0, "page_length": 1, "has_more": True},
        )

    def test_visible_columns_can_sort_and_filter_with_server_controls(self):
        older = make_market_date(make_bond(), date="2030-01-01")
        newer = make_market_date(make_bond(), date="2030-01-02")
        investor = make_investor_user([INVESTOR_ROLE])

        with as_investor_user(investor):
            ascending = get_market_dates(sort_by="date", sort_order="asc")

        names = [row.name for row in ascending["data"]]
        self.assertLess(names.index(older.name), names.index(newer.name))
