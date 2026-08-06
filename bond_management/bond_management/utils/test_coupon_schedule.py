from datetime import date
from decimal import Decimal
from itertools import pairwise
from unittest.mock import patch

import frappe
from frappe.tests import IntegrationTestCase

from bond_management.bond_management.utils.coupon_schedule import (
    generate_coupon_schedule,
    get_coupon_schedule,
    year_fraction,
)


class TestCouponSchedule(IntegrationTestCase):
    def test_generates_schedule_and_honours_first_coupon_date(self):
        schedule = generate_coupon_schedule("2025-01-01", "2026-01-01", 2, 10, "2025-07-01", "30E/360")

        self.assertEqual([row["coupon_date"] for row in schedule], [date(2025, 7, 1), date(2026, 1, 1)])
        self.assertEqual(schedule[0]["coupon_factor"], 5)

    def test_kenya_schedule_uses_backward_182_day_cadence_and_equal_factors(self):
        schedule = generate_coupon_schedule("2025-01-01", "2027-01-01", 2, 10, None, "Actual/364(Kenya)")
        coupon_dates = [row["coupon_date"] for row in schedule]

        self.assertEqual(
            [(later - earlier).days for earlier, later in pairwise(coupon_dates)],
            [182, 182, 182, 182],
        )
        self.assertEqual(
            {Decimal(str(row["coupon_factor"])) for row in schedule},
            {Decimal("5")},
        )

    def test_kenya_schedule_keeps_first_coupon_and_principal_dates_as_boundaries(self):
        schedule = generate_coupon_schedule(
            "2025-01-01",
            "2027-01-01",
            2,
            10,
            "2025-07-01",
            "Actual/364(Kenya)",
            principal_dates=["2026-07-01"],
        )

        self.assertEqual(
            [row["coupon_date"] for row in schedule],
            [
                date(2025, 7, 1),
                date(2025, 7, 4),
                date(2026, 1, 2),
                date(2026, 7, 1),
                date(2026, 7, 3),
                date(2027, 1, 1),
            ],
        )
        self.assertEqual(
            {Decimal(str(row["coupon_factor"])) for row in schedule},
            {Decimal("5")},
        )

    def test_year_fraction_supports_configured_conventions(self):
        self.assertEqual(year_fraction("30E/360", "2025-01-01", "2025-07-01", 2), 0.5)
        self.assertEqual(
            year_fraction("Actual/364(Kenya)", "2025-01-01", "2025-01-02", 2),
            Decimal(1) / Decimal(364),
        )
        self.assertEqual(year_fraction("30E/360", "2025-01-01", "2025-01-01", 2), 0)

    def test_actual_actual_icma_handles_string_frequency_and_eom_periods(self):
        self.assertEqual(
            year_fraction("Actual/Actual(ICMA)", "2024-08-31", "2025-02-28", "2"),
            0.5,
        )

    def test_actual_actual_icma_handles_short_and_long_stubs(self):
        short_stub = year_fraction(
            "Actual/Actual(ICMA)",
            "2025-04-01",
            "2025-07-01",
            2,
            reference_end_date="2025-07-01",
        )
        self.assertAlmostEqual(float(short_stub), 91 / (181 * 2))

        # This long stub spans two notional semi-annual periods of different
        # lengths. Each contributes exactly one half-year under ICMA.
        long_stub = year_fraction(
            "Actual/Actual(ICMA)",
            "2024-01-01",
            "2025-01-01",
            2,
            reference_end_date="2025-01-01",
        )
        self.assertEqual(long_stub, 1)

    def test_actual_actual_icma_long_stub_preserves_end_of_month(self):
        fraction = year_fraction(
            "Actual/Actual(ICMA)",
            "2024-05-15",
            "2025-02-28",
            2,
            reference_end_date="2025-02-28",
        )

        expected = (date(2024, 8, 31) - date(2024, 5, 15)).days / (184 * 2) + 0.5
        self.assertAlmostEqual(float(fraction), expected)

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
        schedule = generate_coupon_schedule("2025-01-01", "2026-01-01", 2, 0, "2025-07-01", "30E/360")

        self.assertEqual(schedule[0]["coupon_factor"], 0)

    def test_child_schedule_query_checks_permissions_through_bond_master(self):
        with patch("bond_management.bond_management.utils.coupon_schedule.frappe.qb.get_query") as get_query:
            get_query.return_value.run.return_value = []

            self.assertEqual(get_coupon_schedule("TEST-ISIN"), [])

        self.assertEqual(get_query.call_args.kwargs["parent_doctype"], "Bond Master")
        self.assertFalse(get_query.call_args.kwargs["ignore_permissions"])
