from types import SimpleNamespace
from unittest import TestCase

from bond_management.patches.prepare_bond_exchange_rate_scope import (
    format_exchange_rate_conflicts,
    get_exchange_rate_conflicts,
)


class TestBondExchangeRateScope(TestCase):
    def test_conflicts_are_grouped_by_global_date_and_currency_key(self):
        rows = [
            SimpleNamespace(
                name="EXR-1",
                portfolio_name="PORT-1",
                rate_date="2025-12-30",
                from_currency="KES",
                to_currency="USD",
                rate="0.0077",
            ),
            SimpleNamespace(
                name="EXR-2",
                portfolio_name="PORT-2",
                rate_date="2025-12-30",
                from_currency="KES",
                to_currency="USD",
                rate="0.0078",
            ),
            SimpleNamespace(
                name="EXR-3",
                portfolio_name="PORT-2",
                rate_date="2025-12-31",
                from_currency="KES",
                to_currency="USD",
                rate="0.0078",
            ),
        ]

        conflicts = get_exchange_rate_conflicts(rows)

        self.assertEqual([[row.name for row in group] for group in conflicts], [["EXR-1", "EXR-2"]])

    def test_conflict_message_identifies_rows_and_requires_manual_resolution(self):
        conflicts = [
            [
                SimpleNamespace(
                    name="EXR-1",
                    portfolio_name="PORT-1",
                    rate_date="2025-12-30",
                    from_currency="KES",
                    to_currency="USD",
                    rate="0.0077",
                ),
                SimpleNamespace(
                    name="EXR-2",
                    portfolio_name="PORT-2",
                    rate_date="2025-12-30",
                    from_currency="KES",
                    to_currency="USD",
                    rate="0.0078",
                ),
            ]
        ]

        message = format_exchange_rate_conflicts(conflicts)

        self.assertIn("EXR-1", message)
        self.assertIn("EXR-2", message)
        self.assertIn("Choose one row", message)
