import os
from unittest.mock import patch

import frappe
from frappe.tests import IntegrationTestCase
from frappe.utils import getdate

from bond_management.bond_management.tests.investor_ui_seed import (
    DEFAULT_INVESTOR_EMAIL,
    TEST_BOND_ISIN,
    TEST_EXCHANGE_RATE_DATE,
    TEST_EXCHANGE_RATE_FROM_CURRENCY,
    TEST_EXCHANGE_RATE_VALUE,
    TEST_MARKET_DATE,
    TEST_PORTFOLIO_NAME,
    TEST_STATEMENT_DATE,
    TEST_TRANSACTION_REFERENCE,
    TEST_YIELD_BOND_ISIN,
    TEST_YIELD_FROM_DATE,
    TEST_YIELD_MIDDLE_DATE,
    TEST_YIELD_TO_DATE,
    seed_investor_ui_browser_test_data,
    seed_investor_ui_test_data,
)
from bond_management.bond_management.utils.investor_permissions import INVESTOR_ROLE


class TestInvestorUITestSeed(IntegrationTestCase):
    def test_browser_seed_requires_caller_provided_credentials(self):
        with patch.dict(os.environ, {}, clear=True):
            with self.assertRaisesRegex(RuntimeError, "FRAPPE_USER must be set"):
                seed_investor_ui_browser_test_data()

    @patch("bond_management.bond_management.tests.investor_ui_seed.seed_investor_ui_test_data")
    def test_browser_seed_passes_environment_credentials_to_the_fixture(self, seed_fixture):
        seed_fixture.return_value = {
            "user": "investor@example.com",
            "portfolio": TEST_PORTFOLIO_NAME,
            "bond": TEST_BOND_ISIN,
            "yield_bond": TEST_YIELD_BOND_ISIN,
            "market_date": "BMD-0001",
            "exchange_rate": "EXR-.00001",
            "transaction": TEST_TRANSACTION_REFERENCE,
            "statement": "BS-0001",
        }

        with patch.dict(
            os.environ,
            {
                "FRAPPE_USER": "investor@example.com",
                "FRAPPE_PASSWORD": "caller-provided-password",
            },
            clear=True,
        ):
            result = seed_investor_ui_browser_test_data()

        seed_fixture.assert_called_once_with(
            email="investor@example.com",
            password="caller-provided-password",
        )
        self.assertEqual(result, seed_fixture.return_value)

    def test_seed_is_idempotent_and_assigns_the_fixture_portfolio(self):
        first = seed_investor_ui_test_data()
        second = seed_investor_ui_test_data()

        self.assertEqual(first, second)
        self.assertEqual(first["user"], DEFAULT_INVESTOR_EMAIL)
        self.assertEqual(first["portfolio"], TEST_PORTFOLIO_NAME)
        self.assertEqual(first["bond"], TEST_BOND_ISIN)
        self.assertEqual(first["yield_bond"], TEST_YIELD_BOND_ISIN)
        self.assertEqual(
            frappe.db.get_value(
                "Bond Exchange Rate",
                first["exchange_rate"],
                [
                    "rate_date",
                    "from_currency",
                    "to_currency",
                    "rate",
                    "reverse_rate",
                    "source",
                    "statement",
                ],
            ),
            (
                getdate(TEST_EXCHANGE_RATE_DATE),
                TEST_EXCHANGE_RATE_FROM_CURRENCY,
                "USD",
                float(TEST_EXCHANGE_RATE_VALUE),
                0.8,
                "Manual",
                None,
            ),
        )
        self.assertEqual(
            frappe.db.get_value("Bond Market Date", first["market_date"], "date"),
            getdate(TEST_MARKET_DATE),
        )
        market_price = frappe.db.get_value(
            "Bond Market Prices",
            {"parent": first["market_date"], "isin": TEST_BOND_ISIN},
            ["market_price", "currency", "future_xirr", "weighted_avg_repayment_date"],
        )
        self.assertEqual(market_price[0], 102.5)
        self.assertEqual(market_price[1], "USD")
        self.assertIsNotNone(market_price[2])
        self.assertIsNotNone(market_price[3])
        self.assertEqual(first["transaction"], TEST_TRANSACTION_REFERENCE)
        self.assertEqual(
            frappe.db.get_value(
                "Bond Statement",
                first["statement"],
                ["portfolio_name", "statement_date", "reconciliation_status"],
            ),
            (TEST_PORTFOLIO_NAME, getdate(TEST_STATEMENT_DATE), "Matched"),
        )
        self.assertTrue(
            frappe.db.exists(
                "Bond Statement Details",
                {"parent": first["statement"], "isin": TEST_BOND_ISIN},
            )
        )
        self.assertEqual(
            frappe.db.get_value(
                "Bond Master",
                TEST_YIELD_BOND_ISIN,
                ["bond_name", "currency"],
            ),
            ("Investor UI Yield Test Bond", "KES"),
        )
        self.assertEqual(
            frappe.db.count(
                "Bond Market Prices",
                {
                    "parent": [
                        "in",
                        frappe.qb.get_query(
                            "Bond Market Date",
                            fields=["name"],
                            filters={"date": ["between", [TEST_YIELD_FROM_DATE, TEST_YIELD_TO_DATE]]},
                        ).run(pluck=True),
                    ],
                    "isin": TEST_YIELD_BOND_ISIN,
                },
            ),
            2,
        )
        self.assertTrue(frappe.db.exists("Bond Market Date", {"date": TEST_YIELD_MIDDLE_DATE}))
        self.assertEqual(
            frappe.db.get_value(
                "Bond Master",
                TEST_BOND_ISIN,
                ["bond_name", "currency", "issue_date", "maturity_date"],
            ),
            (
                "Investor UI Test Bond",
                "USD",
                getdate("2025-01-01"),
                getdate("2027-01-01"),
            ),
        )
        self.assertTrue(
            frappe.db.exists(
                "Bond Principal Schedule",
                {"parent": TEST_BOND_ISIN, "repayment_date": "2027-01-01"},
            )
        )
        self.assertTrue(
            frappe.db.exists(
                "Bond Coupon Schedule",
                {"parent": TEST_BOND_ISIN, "coupon_date": "2025-07-01"},
            )
        )
        self.assertEqual(
            frappe.db.get_value(
                "Bond Transaction",
                TEST_TRANSACTION_REFERENCE,
                ["portfolio_name", "isin"],
            ),
            (TEST_PORTFOLIO_NAME, TEST_BOND_ISIN),
        )
        self.assertTrue(
            frappe.db.exists(
                "Has Role",
                {"parent": DEFAULT_INVESTOR_EMAIL, "role": INVESTOR_ROLE},
            )
        )
        self.assertTrue(
            frappe.db.exists(
                "User Permission",
                {
                    "user": DEFAULT_INVESTOR_EMAIL,
                    "allow": "Bond Portfolio",
                    "for_value": TEST_PORTFOLIO_NAME,
                    "apply_to_all_doctypes": 1,
                },
            )
        )
