import frappe
from frappe.exceptions import FrappeTypeError
from frappe.tests import IntegrationTestCase

from bond_management.bond_management.api.investor import get_bond, get_bonds
from bond_management.bond_management.tests.factories import (
    as_investor_user,
    make_bond,
    make_investor_user,
    unique_name,
)
from bond_management.bond_management.tests.investor_contracts import (
    BOND_COUPON_FIELDS,
    BOND_DETAIL_FIELDS,
    BOND_LIST_FIELDS,
    BOND_PRINCIPAL_FIELDS,
)
from bond_management.bond_management.utils.investor_permissions import (
    BOND_MANAGER_ROLE,
    INVESTOR_ROLE,
)


class TestInvestorBonds(IntegrationTestCase):
    def test_investor_without_portfolio_assignment_can_read_shared_catalog(self):
        bond = make_bond()
        investor = make_investor_user([INVESTOR_ROLE])

        with as_investor_user(investor):
            response = get_bonds()

        self.assertIn(bond.name, {row.name for row in response["data"]})

    def test_list_has_exact_visible_projection(self):
        bond = make_bond()
        investor = make_investor_user([INVESTOR_ROLE])

        with as_investor_user(investor):
            response = get_bonds()

        row = next(row for row in response["data"] if row.name == bond.name)
        self.assertEqual(set(response), {"data", "pagination"})
        self.assertEqual(set(response["pagination"]), {"start", "page_length", "has_more"})
        self.assertEqual(set(row), set(BOND_LIST_FIELDS))
        self.assertTrue(all(set(row) == set(BOND_LIST_FIELDS) for row in response["data"]))
        self.assertEqual(row.isin, bond.isin)
        self.assertNotIn("principal_schedule", row)
        self.assertNotIn("modified", row)

    def test_detail_has_exact_visible_projection_and_schedules(self):
        bond = make_bond(withholding_tax="15")
        investor = make_investor_user([INVESTOR_ROLE])

        with as_investor_user(investor):
            response = get_bond(bond.name)

        self.assertEqual(set(response), {"bond"})
        detail = response["bond"]
        self.assertEqual(set(detail), set(BOND_DETAIL_FIELDS))
        self.assertEqual(detail.isin, bond.isin)
        self.assertTrue(detail.principal_schedule)
        for row in detail.principal_schedule:
            self.assertEqual(set(row), set(BOND_PRINCIPAL_FIELDS))
        self.assertTrue(detail.coupon_schedule)
        for row in detail.coupon_schedule:
            self.assertEqual(set(row), set(BOND_COUPON_FIELDS))
        self.assertNotIn("parent", str(response))
        self.assertNotIn("modified", str(response))

    def test_unreadable_and_unknown_detail_have_same_failure(self):
        readable = make_bond()
        unreadable = make_bond()
        investor = make_investor_user([INVESTOR_ROLE])
        frappe.get_doc(
            {
                "doctype": "User Permission",
                "user": investor,
                "allow": "Bond Master",
                "for_value": readable.name,
                "apply_to_all_doctypes": 1,
            }
        ).insert(ignore_permissions=True)
        messages = []

        with as_investor_user(investor):
            for name in (unreadable.name, unique_name("UNKNOWN-BOND")):
                with self.assertRaises(frappe.PermissionError) as error:
                    get_bond(name)
                messages.append(str(error.exception))

        self.assertEqual(messages[0], messages[1])

    def test_manager_and_administrator_use_normal_bond_permissions(self):
        first = make_bond()
        second = make_bond()
        bonds = {first.name, second.name}
        manager = make_investor_user([BOND_MANAGER_ROLE])

        for user in (manager, "Administrator"):
            with self.subTest(user=user), as_investor_user(user):
                response = get_bonds()
                self.assertTrue(bonds.issubset({row.name for row in response["data"]}))

    def test_pagination_is_allow_listed_and_bounded(self):
        newer = make_bond(
            issue_date="2099-01-01",
            first_coupon_date="2099-07-01",
            maturity_date="2101-01-01",
            principal_schedule=[{"repayment_date": "2101-01-01", "principal_units": 100}],
        )
        older = make_bond(
            issue_date="2098-01-01",
            first_coupon_date="2098-07-01",
            maturity_date="2100-01-01",
            principal_schedule=[{"repayment_date": "2100-01-01", "principal_units": 100}],
        )
        investor = make_investor_user([INVESTOR_ROLE])

        with as_investor_user(investor):
            first_page = get_bonds(page_length="1")

        self.assertEqual(first_page["data"][0].name, newer.name)
        self.assertNotEqual(first_page["data"][0].name, older.name)
        self.assertEqual(
            first_page["pagination"],
            {"start": 0, "page_length": 1, "has_more": True},
        )

    def test_visible_columns_can_sort_and_filter_with_server_controls(self):
        first = make_bond(bond_name="A-" + unique_name("TEST-BOND"))
        second = make_bond(bond_name="Z-" + unique_name("TEST-BOND"))
        investor = make_investor_user([INVESTOR_ROLE])

        with as_investor_user(investor):
            ascending = get_bonds(sort_by="bond_name", sort_order="asc")
            filtered = get_bonds(filter_field="isin", filter_value=first.isin)

        names = [row.name for row in ascending["data"]]
        self.assertLess(names.index(first.name), names.index(second.name))
        self.assertEqual([row.name for row in filtered["data"]], [first.name])
