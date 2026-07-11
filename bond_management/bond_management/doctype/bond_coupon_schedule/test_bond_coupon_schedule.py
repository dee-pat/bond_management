# Copyright (c) 2026, Deepak Patel and Contributors
# See license.txt

from frappe.tests import IntegrationTestCase

from bond_management.bond_management.tests.factories import make_bond


class TestBondCouponSchedule(IntegrationTestCase):
    def test_coupon_rows_are_created_as_bond_master_children(self):
        bond = make_bond()
        coupon = bond.coupon_schedule[0]

        self.assertEqual(coupon.parent, bond.name)
        self.assertEqual(coupon.parenttype, "Bond Master")
        self.assertEqual(coupon.parentfield, "coupon_schedule")
        self.assertIsNotNone(coupon.coupon_factor)
