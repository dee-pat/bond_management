# Copyright (c) 2026, Deepak Patel and Contributors
# See license.txt

from frappe.exceptions import ValidationError
from frappe.tests import IntegrationTestCase

from bond_management.bond_management.tests.factories import make_bond


class TestBondMaster(IntegrationTestCase):
    def test_generates_coupon_schedule_and_principal_percentages(self):
        bond = make_bond()

        self.assertEqual(bond.maturity_date.isoformat(), "2027-01-01")
        self.assertEqual(len(bond.coupon_schedule), 4)
        self.assertEqual(bond.principal_schedule[0].repayment_percent, 100)
        self.assertEqual(bond.coupon_schedule[-1].coupon_date.isoformat(), "2027-01-01")

    def test_rejects_non_positive_principal_schedule(self):
        bond = make_bond()
        bond.principal_schedule[0].principal_units = 0

        self.assertRaises(ValidationError, bond.save)

    def test_maturity_date_boundary_rules(self):
        bond = make_bond()
        bond.maturity_date = "2025-01-02"
        bond.validate_dates()

        bond.maturity_date = "2025-01-01"
        self.assertRaises(ValidationError, bond.validate_dates)

        bond.maturity_date = "2024-12-31"
        self.assertRaises(ValidationError, bond.validate_dates)
