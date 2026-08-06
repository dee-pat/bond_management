# Copyright (c) 2026, Deepak Patel and Contributors
# See license.txt

from decimal import Decimal
from itertools import pairwise

import frappe
from frappe.exceptions import ValidationError
from frappe.tests import IntegrationTestCase

from bond_management.bond_management.doctype.bond_master.bond_master import (
    get_recalculated_schedules,
)
from bond_management.bond_management.tests.factories import make_bond
from bond_management.patches.regenerate_kenya_coupon_schedules import (
    execute as regenerate_kenya_coupon_schedules,
)
from bond_management.patches.set_kenya_quantity_change_flags import (
    execute as synchronize_quantity_change_flags,
)


class TestBondMaster(IntegrationTestCase):
    def test_generates_coupon_schedule_and_principal_percentages(self):
        bond = make_bond()

        self.assertEqual(bond.maturity_date.isoformat(), "2027-01-01")
        self.assertEqual(len(bond.coupon_schedule), 4)
        self.assertEqual(bond.principal_schedule[0].repayment_percent, 100)
        self.assertEqual(bond.coupon_schedule[-1].coupon_date.isoformat(), "2027-01-01")

    def test_kenya_convention_uses_maturity_anchored_182_day_periods(self):
        bond = make_bond(day_count_convention="Actual/364(Kenya)")
        coupon_dates = [row.coupon_date for row in bond.coupon_schedule]

        self.assertEqual(bond.first_coupon_date.isoformat(), "2025-01-03")
        self.assertEqual(
            [(later - earlier).days for earlier, later in pairwise(coupon_dates)],
            [182, 182, 182, 182],
        )
        self.assertEqual(
            Decimal(str(bond.coupon_schedule[0].coupon_factor)),
            Decimal(7) * Decimal(2) / Decimal(364),
        )
        self.assertEqual(
            [Decimal(str(row.coupon_factor)) for row in bond.coupon_schedule[1:]],
            [Decimal("3.5")] * 4,
        )

    def test_kenya_convention_rejects_repayments_outside_anchored_cadence(self):
        bond = make_bond(day_count_convention="Actual/364(Kenya)")
        bond.append(
            "principal_schedule",
            {"repayment_date": "2026-07-01", "principal_units": 100},
        )

        with self.assertRaisesRegex(
            ValidationError,
            "Repayment Date 2026-07-01 must match the 182-day coupon schedule",
        ):
            bond.save()

    def test_quantity_change_is_derived_only_for_kes_kenya_bonds(self):
        bond = make_bond(currency="KES", day_count_convention="Actual/364(Kenya)")
        self.assertEqual(bond.quantity_change, 1)

        bond.currency = "USD"
        bond.save()
        self.assertEqual(bond.quantity_change, 0)

    def test_quantity_change_patch_is_idempotent(self):
        bond = make_bond(currency="KES", day_count_convention="Actual/364(Kenya)")
        frappe.db.set_value("Bond Master", bond.name, "quantity_change", 0, update_modified=False)

        synchronize_quantity_change_flags()
        bond.reload()
        self.assertEqual(bond.quantity_change, 1)

        synchronize_quantity_change_flags()
        bond.reload()
        self.assertEqual(bond.quantity_change, 1)

        bond.currency = "KES"
        bond.day_count_convention = "30E/360"
        bond.save()
        self.assertEqual(bond.quantity_change, 0)

    def test_kenya_schedule_patch_is_idempotent(self):
        bond = make_bond(day_count_convention="Actual/364(Kenya)")
        frappe.db.set_value(
            "Bond Master",
            bond.name,
            "first_coupon_date",
            "2025-07-01",
            update_modified=False,
        )
        frappe.db.set_value(
            "Bond Coupon Schedule",
            bond.coupon_schedule[0].name,
            {"coupon_date": "2025-07-01", "coupon_factor": "3.5"},
            update_modified=False,
        )

        regenerate_kenya_coupon_schedules([bond.name])
        bond.reload()
        self.assertEqual(bond.first_coupon_date.isoformat(), "2025-01-03")
        self.assertEqual(bond.coupon_schedule[0].coupon_date.isoformat(), "2025-01-03")

        regenerate_kenya_coupon_schedules([bond.name])
        bond.reload()
        self.assertEqual(bond.first_coupon_date.isoformat(), "2025-01-03")

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
        self.assertEqual(str(result["first_coupon_date"]), "2025-07-01")
        self.assertEqual(
            [row["repayment_percent"] for row in result["principal_schedule"]],
            [50, 50],
        )
        self.assertEqual(result["quantity_change"], 0)
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
