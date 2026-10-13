from types import SimpleNamespace
from unittest.mock import patch

import frappe
from frappe.api.v1 import read_doc
from frappe.client import get as get_document
from frappe.client import get_list
from frappe.exceptions import FrappeTypeError
from frappe.tests import IntegrationTestCase

from bond_management.bond_management.api.investor import MAX_PAGE_START, get_exchange_rate, get_exchange_rates
from bond_management.bond_management.tests.factories import (
    as_investor_user,
    make_exchange_rate,
    make_investor_user,
    make_portfolio,
    make_statement,
    unique_name,
)
from bond_management.bond_management.tests.investor_contracts import (
    EXCHANGE_RATE_DETAIL_FIELDS,
    EXCHANGE_RATE_LIST_FIELDS,
)
from bond_management.bond_management.utils.investor_permissions import (
    BOND_MANAGER_ROLE,
    INVESTOR_ROLE,
)
from bond_management.bond_management.utils.statement_exchange_rates import (
    sync_statement_exchange_rates,
)


class TestInvestorExchangeRates(IntegrationTestCase):
    def test_investor_without_portfolio_assignment_can_read_shared_history(self):
        exchange_rate = make_exchange_rate()
        investor = make_investor_user([INVESTOR_ROLE])

        with as_investor_user(investor):
            response = get_exchange_rates()

        self.assertIn(exchange_rate.name, {row.name for row in response["data"]})

    def test_generic_list_keeps_rows_without_statement_provenance(self):
        exchange_rate = make_exchange_rate()
        investor = make_investor_user([INVESTOR_ROLE])

        with as_investor_user(investor):
            rows = get_list(
                "Bond Exchange Rate",
                fields=["name"],
                filters={"name": exchange_rate.name},
            )

        self.assertEqual(rows, [{"name": exchange_rate.name}])

    def test_list_has_exact_visible_projection(self):
        exchange_rate = make_exchange_rate()
        investor = make_investor_user([INVESTOR_ROLE])

        with as_investor_user(investor):
            response = get_exchange_rates()

        row = next(row for row in response["data"] if row.name == exchange_rate.name)
        self.assertEqual(set(response), {"data", "pagination"})
        self.assertEqual(set(response["pagination"]), {"start", "page_length", "has_more"})
        self.assertEqual(set(row), set(EXCHANGE_RATE_LIST_FIELDS))
        self.assertTrue(all(set(row) == set(EXCHANGE_RATE_LIST_FIELDS) for row in response["data"]))
        self.assertEqual(row.from_currency, exchange_rate.from_currency)
        self.assertNotIn("source", row)
        self.assertNotIn("statement", row)
        self.assertNotIn("modified", row)

    def test_detail_has_exact_visible_projection(self):
        exchange_rate = make_exchange_rate()
        investor = make_investor_user([INVESTOR_ROLE])

        with as_investor_user(investor):
            response = get_exchange_rate(exchange_rate.name)

        self.assertEqual(set(response), {"exchange_rate"})
        detail = response["exchange_rate"]
        self.assertEqual(set(detail), set(EXCHANGE_RATE_DETAIL_FIELDS))
        self.assertEqual(detail.from_currency, exchange_rate.from_currency)
        self.assertEqual(detail.source, "Manual")
        self.assertIsNone(detail.statement)
        self.assertNotIn("owner", str(response))
        self.assertNotIn("modified", str(response))

    def test_detail_keeps_a_readable_statement_reference(self):
        portfolio = make_portfolio()
        exchange_rate = self._make_statement_exchange_rate(portfolio)
        investor = make_investor_user([INVESTOR_ROLE])
        self._assign_user_permission(investor, "Bond Portfolio", portfolio.name)

        with as_investor_user(investor):
            response = get_exchange_rate(exchange_rate.name)
            self._assert_generic_apis_hide_statement(exchange_rate.name)

        detail = response["exchange_rate"]
        self.assertEqual(detail.source, "Statement PDF")
        self.assertEqual(detail.statement, exchange_rate.statement)

    def test_detail_masks_an_unreadable_cross_portfolio_statement_reference(self):
        assigned_portfolio = make_portfolio()
        other_portfolio = make_portfolio()
        exchange_rate = self._make_statement_exchange_rate(other_portfolio)
        investor = make_investor_user([INVESTOR_ROLE])
        self._assign_user_permission(investor, "Bond Portfolio", assigned_portfolio.name)

        with as_investor_user(investor):
            listed = get_exchange_rates()
            response = get_exchange_rate(exchange_rate.name)
            self._assert_generic_apis_hide_statement(exchange_rate.name, list_visible=False)
            try:
                rows = get_list(
                    "Bond Exchange Rate",
                    fields=["name"],
                    filters={"statement": exchange_rate.statement},
                )
            except frappe.PermissionError:
                # Frappe versions that reject high-permlevel filters stop the
                # probe before the app's row condition needs to apply.
                rows = None
            self.assertIn(rows, (None, []))

        self.assertIn(exchange_rate.name, {row.name for row in listed["data"]})
        detail = response["exchange_rate"]
        self.assertEqual(detail.source, "Statement PDF")
        self.assertIsNone(detail.statement)

    def test_generic_apis_keep_manager_statement_provenance(self):
        exchange_rate = self._make_statement_exchange_rate(make_portfolio())

        for roles in ([BOND_MANAGER_ROLE], ["System Manager"]):
            manager = make_investor_user(roles)
            with self.subTest(roles=roles), as_investor_user(manager):
                for api, response in self._generic_api_responses(exchange_rate.name).items():
                    with self.subTest(api=api):
                        if api == "frappe.client.get_list":
                            self.assertEqual(len(response), 1)
                            response = response[0]
                        self.assertEqual(response["statement"], exchange_rate.statement)

    def test_unreadable_and_unknown_detail_have_same_failure(self):
        readable = make_exchange_rate()
        unreadable = make_exchange_rate()
        investor = make_investor_user([INVESTOR_ROLE])
        self._assign_user_permission(investor, "Bond Exchange Rate", readable.name)
        messages = []

        with as_investor_user(investor):
            for name in (unreadable.name, unique_name("UNKNOWN-EXCHANGE-RATE")):
                with self.assertRaises(frappe.PermissionError) as error:
                    get_exchange_rate(name)
                messages.append(str(error.exception))

        self.assertEqual(messages[0], messages[1])

    def test_manager_and_administrator_use_normal_exchange_rate_permissions(self):
        first = make_exchange_rate()
        second = make_exchange_rate()
        exchange_rates = {first.name, second.name}
        manager = make_investor_user([BOND_MANAGER_ROLE])

        for user in (manager, "Administrator"):
            with self.subTest(user=user), as_investor_user(user):
                response = get_exchange_rates()
                self.assertTrue(exchange_rates.issubset({row.name for row in response["data"]}))

    def test_pagination_is_allow_listed_bounded_and_sorted_by_rate_date(self):
        newer = make_exchange_rate(from_currency="EUR", rate_date="2025-01-02")
        older = make_exchange_rate(from_currency="EUR", rate_date="2025-01-01")
        investor = make_investor_user([INVESTOR_ROLE])
        self._assign_user_permission(investor, "Bond Exchange Rate", older.name)
        self._assign_user_permission(investor, "Bond Exchange Rate", newer.name)

        with as_investor_user(investor):
            first_page = get_exchange_rates(page_length="1")

        self.assertGreater(newer.rate_date, older.rate_date)
        self.assertEqual(first_page["data"][0].name, newer.name)
        self.assertEqual(
            first_page["pagination"],
            {"start": 0, "page_length": 1, "has_more": True},
        )

    def test_visible_columns_can_sort_and_filter_with_server_controls(self):
        older = make_exchange_rate(from_currency="CHF", rate_date="2030-01-01")
        newer = make_exchange_rate(from_currency="CHF", rate_date="2030-01-02")
        investor = make_investor_user([INVESTOR_ROLE])

        with as_investor_user(investor):
            ascending = get_exchange_rates(sort_by="rate_date", sort_order="asc")
            filtered = get_exchange_rates(
                filter_field="from_currency",
                filter_value="CHF",
            )

        names = [row.name for row in ascending["data"]]
        self.assertLess(names.index(older.name), names.index(newer.name))
        self.assertEqual({row.name for row in filtered["data"]}, {older.name, newer.name})

    def _assert_generic_apis_hide_statement(self, name, *, list_visible=True):
        for api, response in self._generic_api_responses(name).items():
            with self.subTest(api=api):
                if api == "frappe.client.get_list":
                    if not list_visible:
                        self.assertEqual(response, [])
                        continue
                    self.assertEqual(len(response), 1)
                    response = response[0]
                    self.assertNotIn("statement", response)
                self.assertEqual(response["name"], name)
                self.assertIsNone(response.get("statement"))

    @staticmethod
    def _generic_api_responses(name):
        with patch.dict(frappe.form_dict, {}, clear=True):
            rest_document = read_doc("Bond Exchange Rate", name).as_dict()
        return {
            "frappe.client.get": get_document("Bond Exchange Rate", name),
            "frappe.client.get_list": get_list(
                "Bond Exchange Rate",
                fields=["name", "statement"],
                filters={"name": name},
            ),
            "frappe.api.v1.read_doc": rest_document,
        }

    @staticmethod
    def _make_statement_exchange_rate(portfolio):
        exchange_rate = make_exchange_rate()
        statement = make_statement(portfolio, statement_date=exchange_rate.rate_date)
        sync_statement_exchange_rates(
            statement,
            [
                SimpleNamespace(
                    from_currency=exchange_rate.from_currency,
                    to_currency=exchange_rate.to_currency,
                    rate=exchange_rate.rate,
                )
            ],
        )
        exchange_rate.reload()
        return exchange_rate

    @staticmethod
    def _assign_user_permission(user, allow, value):
        frappe.get_doc(
            {
                "doctype": "User Permission",
                "user": user,
                "allow": allow,
                "for_value": value,
                "apply_to_all_doctypes": 1,
            }
        ).insert(ignore_permissions=True)
