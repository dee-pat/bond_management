from datetime import date

import frappe
from frappe.tests import IntegrationTestCase

from bond_management.bond_management.utils.coupon_schedule import (
    generate_coupon_schedule,
    year_fraction,
)


class TestCouponSchedule(IntegrationTestCase):
    def test_generates_schedule_and_honours_first_coupon_date(self):
        schedule = generate_coupon_schedule(
            "2025-01-01", "2026-01-01", 2, 10, "2025-07-01", "30E/360"
        )

        self.assertEqual([row["coupon_date"] for row in schedule], [date(2025, 7, 1), date(2026, 1, 1)])
        self.assertEqual(schedule[0]["coupon_factor"], 5)

    def test_year_fraction_supports_configured_conventions(self):
        self.assertEqual(year_fraction("30E/360", "2025-01-01", "2025-07-01", 2), 0.5)
        self.assertEqual(year_fraction("Actual/364(Kenya)", "2025-01-01", "2025-01-02", 2), 1 / 364)
        self.assertEqual(year_fraction("30E/360", "2025-01-01", "2025-01-01", 2), 0)

    def test_actual_actual_icma_handles_string_frequency_and_eom_periods(self):
        self.assertEqual(
            year_fraction("Actual/Actual(ICMA)", "2024-08-31", "2025-02-28", "2"),
            0.5,
        )

    def test_rejects_invalid_coupon_frequency_and_keeps_zero_coupon_factor(self):
        self.assertRaises(
            frappe.ValidationError,
            generate_coupon_schedule,
            "2025-01-01",
            "2026-01-01",
            0,
            10,
            "2025-07-01",
            "30E/360",
        )
        schedule = generate_coupon_schedule(
            "2025-01-01", "2026-01-01", 2, 0, "2025-07-01", "30E/360"
        )

        self.assertEqual(schedule[0]["coupon_factor"], 0)
