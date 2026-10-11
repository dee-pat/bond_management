import json
from pathlib import Path
from unittest import TestCase

ROLE = "Bond Investor Read Only"
MANAGER_ROLE = "Bond Management Manager"
WORKSPACE_PATH = Path(__file__).parents[1] / "workspace" / "bond_investor" / "bond_investor.json"
SIDEBAR_PATH = Path(__file__).parents[1] / "sidebar" / "bond_investor" / "bond_investor.json"


class TestBondInvestorWorkspace(TestCase):
    def test_workspace_only_exposes_investor_navigation(self):
        workspace = json.loads(WORKSPACE_PATH.read_text())

        self.assertTrue(workspace["hide_custom"])
        self.assertEqual([role["role"] for role in workspace["roles"]], [ROLE, MANAGER_ROLE])
        self.assertEqual(
            {shortcut["link_to"] for shortcut in workspace["shortcuts"]},
            {
                "Bond Transaction",
                "Bond Statement",
                "Bond Master",
                "Bond Market Date",
                "Bond Exchange Rate",
                "Portfolio Performance",
                "Bond Yield Comparison",
                "Interest Difference by Portfolio",
            },
        )

    def test_interest_difference_report_is_in_investor_sidebar(self):
        sidebar = json.loads(SIDEBAR_PATH.read_text())

        self.assertTrue(
            any(
                item["link_type"] == "Report" and item["link_to"] == "Interest Difference by Portfolio"
                for item in sidebar["items"]
            )
        )
