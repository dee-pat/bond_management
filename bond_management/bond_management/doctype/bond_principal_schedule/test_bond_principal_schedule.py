# Copyright (c) 2026, Deepak Patel and Contributors
# See license.txt

from frappe.tests import IntegrationTestCase

from bond_management.bond_management.tests.factories import make_bond


class TestBondPrincipalSchedule(IntegrationTestCase):
    def test_principal_rows_are_created_as_bond_master_children(self):
        bond = make_bond()
        repayment = bond.principal_schedule[0]

        self.assertEqual(repayment.parent, bond.name)
        self.assertEqual(repayment.parenttype, "Bond Master")
        self.assertEqual(repayment.parentfield, "principal_schedule")
        self.assertEqual(repayment.repayment_percent, 100)
