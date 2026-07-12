from frappe.tests import IntegrationTestCase

from bond_management.bond_management.utils.accrual import get_coupon_period


class TestAccrual(IntegrationTestCase):
    def test_coupon_period_includes_start_and_end_dates(self):
        schedule = [{"period_start": "2025-01-01", "period_end": "2025-06-30"}]

        self.assertIsNotNone(get_coupon_period(schedule, "2025-01-01"))
        self.assertIsNotNone(get_coupon_period(schedule, "2025-06-30"))
        self.assertIsNone(get_coupon_period(schedule, "2024-12-31"))
