# Copyright (c) 2026, Deepak Patel and Contributors
# See license.txt

import frappe
from frappe.exceptions import ValidationError
from frappe.tests import IntegrationTestCase

from bond_management.bond_management.doctype.bond_master.bond_master import (
    get_recalculated_schedules,
)
from bond_management.bond_management.tests.factories import make_bond


class TestBondMaster(IntegrationTestCase):
    def test_generates_coupon_schedule_and_principal_percentages(self):
        bond = make_bond()

        self.assertEqual(bond.maturity_date.isoformat(), "2027-01-01")
        self.assertEqual(len(bond.coupon_schedule), 4)
        self.assertEqual(bond.principal_schedule[0].repayment_percent, 100)
        self.assertEqual(bond.coupon_schedule[-1].coupon_date.isoformat(), "2027-01-01")

    def test_rejects_empty_principal_schedule(self):
        bond = make_bond()
        bond.set("principal_schedule", [])

        with self.assertRaisesRegex(ValidationError, "At least one"):
            bond.save()

    def test_each_principal_row_must_be_positive(self):
        bond = make_bond()
        bond.principal_schedule[0].principal_units = 0

        with self.assertRaisesRegex(ValidationError, "greater than zero"):
            bond.save()

        bond.reload()
        bond.principal_schedule[0].principal_units = -1
        with self.assertRaisesRegex(ValidationError, "greater than zero"):
            bond.save()

    def test_rejects_mixed_sign_principal_rows_even_when_total_is_positive(self):
        bond = make_bond()
        bond.set(
            "principal_schedule",
            [
                {"repayment_date": "2026-01-01", "principal_units": -50},
                {"repayment_date": "2027-01-01", "principal_units": 100},
            ],
        )

        with self.assertRaisesRegex(ValidationError, "greater than zero"):
            bond.save()

    def test_rejects_missing_and_duplicate_repayment_dates(self):
        bond = make_bond()
        bond.principal_schedule[0].repayment_date = None
        with self.assertRaisesRegex(ValidationError, "Repayment Date is required"):
            bond.save()

        bond.reload()
        bond.set(
            "principal_schedule",
            [
                {"repayment_date": "2027-01-01", "principal_units": 50},
                {"repayment_date": "2027-01-01", "principal_units": 50},
            ],
        )
        with self.assertRaisesRegex(ValidationError, "cannot be duplicated"):
            bond.save()

    def test_face_value_and_coupon_rate_zero_boundaries(self):
        bond = make_bond(coupon_rate=0)
        self.assertEqual(bond.coupon_rate, 0)

        bond.face_value_per_unit = 0
        with self.assertRaisesRegex(ValidationError, "Face Value.*greater than zero"):
            bond.save()

        bond.reload()
        bond.face_value_per_unit = -1
        with self.assertRaisesRegex(ValidationError, "Face Value.*greater than zero"):
            bond.save()

        bond.reload()
        bond.face_value_per_unit = 1
        bond.coupon_rate = -0.01
        with self.assertRaisesRegex(ValidationError, "Coupon Rate must be zero"):
            bond.save()

    def test_value_only_schedule_endpoint_returns_authoritative_rows(self):
        bond = make_bond()
        bond.append(
            "principal_schedule",
            {"repayment_date": "2026-01-01", "principal_units": 100},
        )

        result = get_recalculated_schedules(frappe.as_json(bond.as_dict()))

        self.assertEqual(result["maturity_date"].isoformat(), "2027-01-01")
        self.assertEqual(
            [row["repayment_percent"] for row in result["principal_schedule"]],
            [50, 50],
        )
        self.assertTrue(result["principal_schedule"][0]["name"])
        self.assertEqual(result["principal_schedule"][1]["idx"], 2)
        self.assertEqual(result["coupon_schedule"][-1]["coupon_date"].isoformat(), "2027-01-01")

    def test_value_only_schedule_endpoint_rejects_complex_document_names(self):
        values = make_bond().as_dict()
        values["name"] = []

        with self.assertRaisesRegex(frappe.ValidationError, "Bond Master name must be a string"):
            get_recalculated_schedules(frappe.as_json(values))

    def test_maturity_date_boundary_rules(self):
        bond = make_bond()
        bond.maturity_date = "2025-01-02"
        bond.validate_dates()

        bond.maturity_date = "2025-01-01"
        self.assertRaises(ValidationError, bond.validate_dates)

        bond.maturity_date = "2024-12-31"
        self.assertRaises(ValidationError, bond.validate_dates)
