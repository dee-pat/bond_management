from decimal import Decimal

import frappe
from frappe.tests import IntegrationTestCase

from bond_management.bond_management.tests.factories import make_bond
from bond_management.bond_management.utils.accrual import (
    calculate_accrued_fraction,
    calculate_coupon_principal_factor,
    calculate_principal_factor,
    calculate_quantity_factor_from_bond,
    calculate_weighted_average_repayment,
    get_coupon_period,
    unit_accrued_interest_from_bond,
)


class TestAccrual(IntegrationTestCase):
    def test_kenya_accrual_prorates_fixed_coupon_factor_over_stub_period(self):
        schedule = [
            {
                "period_start": "2025-01-01",
                "period_end": "2025-01-30",
                "coupon_date": "2025-01-31",
                "coupon_factor": 5,
            }
        ]

        accrued_interest = calculate_accrued_fraction(schedule, "2025-01-16", "Actual/364(Kenya)", 100, 2, 10)

        self.assertEqual(accrued_interest, Decimal("2.5"))

    def test_batched_frappe_dict_schedule_rows_are_accepted(self):
        bond = frappe._dict(
            {
                "coupon_schedule": [
                    frappe._dict(
                        {
                            "period_start": "2025-01-01",
                            "period_end": "2025-06-30",
                            "coupon_date": "2025-07-01",
                        }
                    )
                ],
                "principal_schedule": [],
                "day_count_convention": "30E/360",
                "face_value_per_unit": 100,
                "coupon_frequency": 2,
                "coupon_rate": 10,
            }
        )

        self.assertEqual(
            unit_accrued_interest_from_bond(bond, "2025-04-01"),
            Decimal("2.5"),
        )

    def test_coupon_period_includes_start_and_end_dates(self):
        schedule = [{"period_start": "2025-01-01", "period_end": "2025-06-30"}]

        self.assertIsNotNone(get_coupon_period(schedule, "2025-01-01"))
        self.assertIsNotNone(get_coupon_period(schedule, "2025-06-30"))
        self.assertIsNone(get_coupon_period(schedule, "2024-12-31"))

    def test_actual_actual_icma_uses_the_coupon_date_as_reference_end(self):
        schedule = [
            {
                "period_start": "2025-01-01",
                "period_end": "2025-06-30",
                "coupon_date": "2025-07-01",
            }
        ]
        accrued_interest = calculate_accrued_fraction(
            schedule, "2025-04-01", "Actual/Actual(ICMA)", 100, "2", 10
        )

        self.assertIsInstance(accrued_interest, Decimal)
        self.assertAlmostEqual(float(accrued_interest), 10 * 90 / (181 * 2), places=10)

    def test_outstanding_and_coupon_factors_have_explicit_repayment_day_semantics(self):
        bond = make_bond(
            maturity_date="2026-01-01",
            principal_schedule=[
                {"repayment_date": "2025-07-01", "principal_units": 50},
                {"repayment_date": "2026-01-01", "principal_units": 50},
            ],
        )

        self.assertEqual(calculate_principal_factor(bond.name, "2025-06-30"), 1)
        self.assertEqual(calculate_principal_factor(bond.name, "2025-07-01"), Decimal("0.5"))
        self.assertEqual(calculate_principal_factor(bond.name, "2025-07-02"), 0.5)
        self.assertEqual(calculate_coupon_principal_factor(bond.name, "2025-06-30"), 1)
        self.assertEqual(calculate_coupon_principal_factor(bond.name, "2025-07-01"), 1)
        self.assertEqual(calculate_coupon_principal_factor(bond.name, "2025-07-02"), Decimal("0.5"))

    def test_kes_quantity_change_uses_quantity_factor_and_keeps_principal_factor_at_one(self):
        bond = make_bond(
            currency="KES",
            day_count_convention="Actual/364(Kenya)",
            principal_schedule=[
                {"repayment_date": "2025-07-01", "principal_units": 50},
                {"repayment_date": "2027-01-01", "principal_units": 50},
            ],
        )

        self.assertEqual(calculate_principal_factor(bond.name, "2025-07-01"), Decimal("1"))
        self.assertEqual(calculate_quantity_factor_from_bond(bond, "2025-06-30"), Decimal("1"))
        self.assertEqual(calculate_quantity_factor_from_bond(bond, "2025-07-01"), Decimal("0.5"))
        self.assertEqual(
            calculate_quantity_factor_from_bond(bond, "2025-07-01", include_repayment_on_date=False),
            Decimal("1"),
        )

    def test_weighted_repayment_uses_remaining_principal_with_strict_future_boundary(self):
        schedule = [
            {"repayment_date": "2025-07-01", "principal_units": 25},
            {"repayment_date": "2025-07-05", "principal_units": 75},
        ]

        before_date, before_years = calculate_weighted_average_repayment(schedule, "2025-06-30")
        on_date, on_years = calculate_weighted_average_repayment(schedule, "2025-07-01")
        after_date, after_years = calculate_weighted_average_repayment(schedule, "2025-07-02")

        self.assertEqual(before_date.isoformat(), "2025-07-04")
        self.assertEqual(before_years, Decimal(4) / Decimal(365))
        self.assertEqual(on_date.isoformat(), "2025-07-05")
        self.assertEqual(on_years, Decimal(4) / Decimal(365))
        self.assertEqual(after_date.isoformat(), "2025-07-05")
        self.assertEqual(after_years, Decimal(3) / Decimal(365))
        self.assertEqual(calculate_weighted_average_repayment(schedule, "2025-07-05"), (None, None))
        self.assertEqual(calculate_weighted_average_repayment(schedule, "2025-07-06"), (None, None))

    def test_weighted_repayment_rounds_display_date_half_up_without_rounding_years(self):
        schedule = [
            {"repayment_date": "2025-07-01", "principal_units": 50},
            {"repayment_date": "2025-07-02", "principal_units": 50},
        ]

        weighted_date, weighted_years = calculate_weighted_average_repayment(schedule, "2025-06-30")

        self.assertEqual(weighted_date.isoformat(), "2025-07-02")
        self.assertEqual(weighted_years, Decimal("1.5") / Decimal(365))
