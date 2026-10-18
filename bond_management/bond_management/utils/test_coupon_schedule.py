from datetime import date
from decimal import Decimal
from itertools import pairwise
from unittest.mock import patch

import frappe
from frappe.tests import IntegrationTestCase

from bond_management.bond_management.utils.coupon_schedule import (
    generate_coupon_schedule,
    year_fraction,
)


class TestCouponSchedule(IntegrationTestCase):
    def test_generates_schedule_and_honours_first_coupon_date(self):
        schedule = generate_coupon_schedule("2025-01-01", "2026-01-01", 2, 10, "2025-07-01", "30E/360")

        self.assertEqual([row["coupon_date"] for row in schedule], [date(2025, 7, 1), date(2026, 1, 1)])
        self.assertEqual(schedule[0]["coupon_factor"], 5)

    def test_kenya_schedule_uses_maturity_anchored_182_day_cadence(self):
        schedule = generate_coupon_schedule("2025-01-01", "2027-01-01", 2, 10, None, "Actual/364(Kenya)")
        coupon_dates = [row["coupon_date"] for row in schedule]

        self.assertEqual(coupon_dates[0], date(2025, 1, 3))
        self.assertEqual(
            [(later - earlier).days for earlier, later in pairwise(coupon_dates)],
            [182, 182, 182, 182],
        )
        self.assertEqual(schedule[0]["coupon_factor"], Decimal(10) * Decimal(2) / Decimal(364))
        self.assertEqual(
            [Decimal(str(row["coupon_factor"])) for row in schedule[1:]],
            [Decimal("5")] * 4,
        )

    def test_kenya_schedule_derives_first_coupon_and_validates_principal_dates(self):
        schedule = generate_coupon_schedule(
            "2025-01-01",
            "2027-01-01",
            2,
            10,
            "2025-07-01",
            "Actual/364(Kenya)",
            principal_dates=["2026-07-03", "2027-01-01"],
        )

        self.assertEqual(
            [row["coupon_date"] for row in schedule],
            [
                date(2025, 1, 3),
                date(2025, 7, 4),
                date(2026, 1, 2),
                date(2026, 7, 3),
                date(2027, 1, 1),
            ],
        )

        with self.assertRaisesRegex(
            frappe.ValidationError,
            "Repayment Date 2026-07-01 must match the 182-day coupon schedule",
        ):
            generate_coupon_schedule(
                "2025-01-01",
                "2027-01-01",
                2,
                10,
                "2025-07-01",
                "Actual/364(Kenya)",
                principal_dates=["2026-07-01", "2027-01-01"],
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

    def test_pins_schedule_for_each_supported_frequency(self):
        cases = {
            1: (
                "2027-01-15",
                [
                    ("2026-01-15", "2025-01-15", "2026-01-14", "6"),
                    ("2027-01-15", "2026-01-15", "2027-01-14", "6"),
                ],
            ),
            2: (
                "2026-01-15",
                [
                    ("2025-07-15", "2025-01-15", "2025-07-14", "3.0"),
                    ("2026-01-15", "2025-07-15", "2026-01-14", "3.0"),
                ],
            ),
            4: (
                "2026-01-15",
                [
                    ("2025-04-15", "2025-01-15", "2025-04-14", "1.50"),
                    ("2025-07-15", "2025-04-15", "2025-07-14", "1.50"),
                    ("2025-10-15", "2025-07-15", "2025-10-14", "1.50"),
                    ("2026-01-15", "2025-10-15", "2026-01-14", "1.50"),
                ],
            ),
            12: (
                "2025-07-15",
                [
                    (f"2025-{month + 1:02d}-15", f"2025-{month:02d}-15", f"2025-{month + 1:02d}-14", "0.5")
                    for month in range(1, 7)
                ],
            ),
        }
        for frequency, (maturity_date, expected) in cases.items():
            with self.subTest(frequency=frequency):
                schedule = generate_coupon_schedule(
                    "2025-01-15", maturity_date, frequency, 6, None, "30E/360"
                )
                self.assertSchedule(schedule, expected)

    def test_pins_end_of_month_and_clipped_day_cadence(self):
        self.assertSchedule(
            generate_coupon_schedule("2024-01-10", "2025-08-31", 2, 6, None, "30E/360"),
            [
                ("2024-02-29", "2024-01-10", "2024-02-28", "0.8166666666666666666666666666"),
                ("2024-08-31", "2024-02-29", "2024-08-30", "3.016666666666666666666666667"),
                ("2025-02-28", "2024-08-31", "2025-02-27", "2.966666666666666666666666666"),
                ("2025-08-31", "2025-02-28", "2025-08-30", "3.033333333333333333333333334"),
            ],
        )
        self.assertSchedule(
            generate_coupon_schedule("2024-01-10", "2025-08-31", 2, 6, None, "Actual/Actual(ICMA)"),
            [
                ("2024-02-29", "2024-01-10", "2024-02-28", "0.8241758241758241758241758244"),
                ("2024-08-31", "2024-02-29", "2024-08-30", "3.0"),
                ("2025-02-28", "2024-08-31", "2025-02-27", "3.0"),
                ("2025-08-31", "2025-02-28", "2025-08-30", "3.0"),
            ],
        )
        # Steps run from the previous generated date, so a clipped 28 February
        # carries into earlier dates when maturity is not a month end.
        self.assertSchedule(
            generate_coupon_schedule("2024-01-10", "2025-08-30", 2, 6, None, "30E/360"),
            [
                ("2024-02-28", "2024-01-10", "2024-02-27", "0.7999999999999999999999999998"),
                ("2024-08-28", "2024-02-28", "2024-08-27", "3.0"),
                ("2025-02-28", "2024-08-28", "2025-02-27", "3.0"),
                ("2025-08-30", "2025-02-28", "2025-08-29", "3.033333333333333333333333334"),
            ],
        )

    def test_pins_short_and_long_first_coupon_stubs(self):
        self.assertSchedule(
            generate_coupon_schedule("2025-01-01", "2026-07-01", 2, 6, "2025-03-15", "30E/360"),
            [
                ("2025-03-15", "2025-01-01", "2025-03-14", "1.233333333333333333333333334"),
                ("2025-07-01", "2025-03-15", "2025-06-30", "1.766666666666666666666666666"),
                ("2026-01-01", "2025-07-01", "2025-12-31", "3.0"),
                ("2026-07-01", "2026-01-01", "2026-06-30", "3.0"),
            ],
        )
        self.assertSchedule(
            generate_coupon_schedule("2025-01-01", "2026-07-01", 2, 6, "2025-09-01", "Actual/Actual(ICMA)"),
            [
                ("2025-09-01", "2025-01-01", "2025-08-31", "3.977900552486187845303867404"),
                ("2026-01-01", "2025-09-01", "2025-12-31", "1.989130434782608695652173913"),
                ("2026-07-01", "2026-01-01", "2026-06-30", "3.0"),
            ],
        )

    def test_rejects_first_coupon_date_on_issue_or_maturity_boundary(self):
        for first_coupon_date, message in (
            ("2025-01-01", "First Coupon Date must be after Issue Date"),
            ("2024-12-31", "First Coupon Date must be after Issue Date"),
            ("2026-07-01", "First Coupon Date must be before Maturity Date"),
            ("2026-07-02", "First Coupon Date must be before Maturity Date"),
        ):
            with self.subTest(first_coupon_date=first_coupon_date):
                with self.assertRaisesRegex(frappe.ValidationError, f"^{message}$"):
                    generate_coupon_schedule("2025-01-01", "2026-07-01", 2, 6, first_coupon_date, "30E/360")

    def test_pins_kenya_schedule_and_principal_date_validation(self):
        # The convention name is matched case-insensitively and an entered
        # first coupon date is ignored, even one before the issue date.
        for convention, first_coupon_date in (
            ("actual/364(kenya)", None),
            ("Actual/364(Kenya)", "2024-01-01"),
        ):
            with self.subTest(convention=convention):
                self.assertSchedule(
                    generate_coupon_schedule(
                        "2025-01-01",
                        "2026-01-01",
                        2,
                        10,
                        first_coupon_date,
                        convention,
                        principal_dates=["2025-07-03", "2026-01-01", None],
                    ),
                    [
                        ("2025-01-02", "2025-01-01", "2025-01-01", "0.02747252747252747252747252747"),
                        ("2025-07-03", "2025-01-02", "2025-07-02", "5.0"),
                        ("2026-01-01", "2025-07-03", "2025-12-31", "5.0"),
                    ],
                )

        # The earliest invalid repayment date is reported.
        with self.assertRaisesRegex(
            frappe.ValidationError,
            "^Repayment Date 2026-07-01 must match the 182-day coupon schedule$",
        ):
            generate_coupon_schedule(
                "2025-01-01",
                "2027-01-01",
                2,
                10,
                None,
                "Actual/364(Kenya)",
                principal_dates=["2026-08-01", "2026-07-01", "2027-01-01"],
            )

        with self.assertRaisesRegex(
            frappe.ValidationError,
            r"^Actual/364\(Kenya\) requires a semi-annual coupon frequency of 2$",
        ):
            generate_coupon_schedule("2025-01-01", "2027-01-01", 4, 10, None, "Actual/364(Kenya)")

    def test_rejects_issue_date_on_or_after_maturity(self):
        for issue_date in ("2025-01-01", "2025-06-01"):
            with self.subTest(issue_date=issue_date):
                with self.assertRaisesRegex(
                    frappe.ValidationError, "^Issue date must be before maturity date$"
                ):
                    generate_coupon_schedule(issue_date, "2025-01-01", 2, 10, None, "30E/360")

        # The date check runs before frequency validation.
        with self.assertRaisesRegex(frappe.ValidationError, "^Issue date must be before maturity date$"):
            generate_coupon_schedule("2025-06-01", "2025-01-01", 0, 10, None, "30E/360")

    def test_pins_frequency_validation_and_missing_inputs(self):
        for frequency, message in (
            (5, "Coupon Frequency must be a positive divisor of 12"),
            (-2, "Coupon Frequency must be a positive divisor of 12"),
            ("x", "Coupon Frequency must be a number"),
        ):
            with self.subTest(frequency=frequency):
                with self.assertRaisesRegex(frappe.ValidationError, f"^{message}$"):
                    generate_coupon_schedule("2025-01-01", "2026-01-01", frequency, 10, None, "30E/360")

        self.assertEqual(generate_coupon_schedule("2025-01-01", "2026-01-01", None, 10, None, "30E/360"), [])
        self.assertSchedule(
            generate_coupon_schedule("2025-01-01", "2026-01-01", "2", 10, None, "30E/360"),
            [
                ("2025-07-01", "2025-01-01", "2025-06-30", "5.0"),
                ("2026-01-01", "2025-07-01", "2025-12-31", "5.0"),
            ],
        )

    def test_rejects_unsupported_day_count_convention(self):
        with self.assertRaisesRegex(frappe.ValidationError, "^Unsupported day count convention: BOGUS$"):
            generate_coupon_schedule("2025-01-01", "2026-01-01", 2, 10, None, "BOGUS")

    def assertSchedule(self, schedule, expected):
        for row in schedule:
            self.assertIsInstance(row["coupon_factor"], Decimal)
        self.assertEqual(
            [
                (row["coupon_date"], row["period_start"], row["period_end"], row["coupon_factor"])
                for row in schedule
            ],
            [
                (
                    date.fromisoformat(coupon),
                    date.fromisoformat(start),
                    date.fromisoformat(end),
                    Decimal(factor),
                )
                for coupon, start, end, factor in expected
            ],
        )
