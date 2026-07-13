from frappe.tests import IntegrationTestCase

from bond_management.bond_management.tests.factories import make_bond
from bond_management.bond_management.utils.accrual import (
    calculate_accrued_fraction,
    calculate_principal_factor,
    get_coupon_period,
)


class TestAccrual(IntegrationTestCase):
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

        self.assertAlmostEqual(accrued_interest, 10 * 90 / (181 * 2), places=10)

    def test_principal_repayment_applies_after_but_not_on_repayment_date(self):
        bond = make_bond(
            maturity_date="2026-01-01",
            principal_schedule=[
                {"repayment_date": "2025-07-01", "principal_units": 50},
                {"repayment_date": "2026-01-01", "principal_units": 50},
            ],
        )

        self.assertEqual(calculate_principal_factor(bond.name, "2025-06-30"), 1)
        self.assertEqual(calculate_principal_factor(bond.name, "2025-07-01"), 1)
        self.assertEqual(calculate_principal_factor(bond.name, "2025-07-02"), 0.5)
