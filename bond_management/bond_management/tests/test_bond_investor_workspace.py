import json
from pathlib import Path
from unittest import TestCase

ROLE = "Bond Investor Read Only"
MANAGER_ROLE = "Bond Management Manager"
WORKSPACE_PATH = Path(__file__).parents[1] / "workspace" / "bond_investor" / "bond_investor.json"


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
            },
        )
