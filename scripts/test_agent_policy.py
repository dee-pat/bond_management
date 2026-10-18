"""Cases for the site classification in bond_management/agent_policy.py."""

import importlib.util
import subprocess
import sys
import unittest
from pathlib import Path

APP_ROOT = Path(__file__).resolve().parent.parent
CORE = APP_ROOT / "bond_management" / "agent_policy.py"
HEX = "0123456789abcdef" * 2
TEMPORARY = f"bond-management-lifecycle-{HEX}.localhost"
FOREIGN = (
    "",
    "example.localhost",
    "bond-management.localhost",
    f"bond-management-{HEX}.localhost",
    f"bond-management-lifecycle-{HEX[:31]}.localhost",
    f"bond-management-lifecycle-{HEX}0.localhost",
    f"bond-management-lifecycle-{HEX.upper()}.localhost",
    f"Bond-Management-lifecycle-{HEX}.localhost",
    f"bond-management-lifecycle-{HEX}.localhost.evil",
    "BOND-MANAGEMENT-DEV.LOCALHOST",
)

# Load the file by path, as scripts/verify.sh does, without importing the app package.
_spec = importlib.util.spec_from_file_location("agent_policy", CORE)
agent_policy = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(agent_policy)


class SiteClassificationTests(unittest.TestCase):
    def test_persistent_sites(self):
        for site in agent_policy.PERSISTENT_SITES:
            self.assertEqual(agent_policy.classify_site(site), agent_policy.PERSISTENT, site)

    def test_temporary_sites(self):
        self.assertEqual(agent_policy.classify_site(TEMPORARY), agent_policy.TEMPORARY)
        self.assertEqual(agent_policy.classify_site(f"bond-management-race-{HEX}.localhost"), "temporary")

    def test_foreign_names(self):
        for site in (*FOREIGN, None, 1, ["bond-management-dev.localhost"]):
            self.assertEqual(agent_policy.classify_site(site), agent_policy.FOREIGN, site)

    def test_hex_suffix_boundary(self):
        # Less than, equal to and greater than the 32 hex characters.
        for length, kind in ((31, "foreign"), (32, "temporary"), (33, "foreign")):
            site = f"bond-management-x-{'a' * length}.localhost"
            self.assertEqual(agent_policy.classify_site(site), kind, length)


class MainExitCodeTests(unittest.TestCase):
    def run_main(self, *argv):
        return subprocess.run(
            [sys.executable, "-I", str(CORE), *argv], capture_output=True, text=True, check=False
        )

    def test_exits_zero_only_for_one_temporary_site(self):
        result = self.run_main(TEMPORARY)
        self.assertEqual((result.returncode, result.stdout), (0, ""))

    def test_refuses_everything_else(self):
        cases = [[], [TEMPORARY, TEMPORARY]]
        cases += [[site] for site in (*sorted(agent_policy.PERSISTENT_SITES), *FOREIGN)]
        for argv in cases:
            with self.subTest(argv=argv):
                result = self.run_main(*argv)
                self.assertEqual(result.returncode, 1)
                self.assertEqual(result.stdout, "")
                # The refusal never echoes the site name.
                for site in argv:
                    self.assertNotIn(site or "\0", result.stderr)


if __name__ == "__main__":
    unittest.main()
