"""Cases for the stdlib-only policy core, bond_management/agent_policy.py."""

import ast
import subprocess
import sys
import unittest
from pathlib import Path

from claude_guard import agent_policy

APP_ROOT = Path(__file__).resolve().parent.parent
CORE = APP_ROOT / "bond_management" / "agent_policy.py"
CONSUMERS = (
    APP_ROOT / "scripts" / "claude_guard.py",
    APP_ROOT / "bond_management" / "bond_management" / "tests" / "temporary_site_guard.py",
)
PERSISTENT_REASON = "Never destroy or overwrite the persistent Bond Management sites."
FOREIGN_REASON = "Destructive bench commands require one literal temporary Bond Management site."
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
DESTRUCTIVE = (*sorted(agent_policy.DESTRUCTIVE_VERBS), "new-site")


def spellings(verb, site):
    """Every canonical bench spelling that names one site for verb."""
    force = ["--force"] if verb == "new-site" else []
    if verb in agent_policy.POSITIONAL_SITE_VERBS:
        return (["bench", verb, site, *force],)
    return (
        ["bench", "--site", site, verb],
        ["bench", f"--site={site}", verb],
        ["bench", verb, "--site", site],
    )


class AgentPolicyTests(unittest.TestCase):
    def assert_violation(self, argv, expected):
        self.assertEqual(agent_policy.destructive_site_violation(argv), expected, argv)

    def test_core_imports_only_the_standard_library(self):
        tree = ast.parse(CORE.read_text())
        modules = {
            alias.name for node in ast.walk(tree) if isinstance(node, ast.Import) for alias in node.names
        }
        modules |= {node.module for node in ast.walk(tree) if isinstance(node, ast.ImportFrom)}
        self.assertTrue(modules)
        for module in modules:
            self.assertIn(module.partition(".")[0], sys.stdlib_module_names, module)

    def test_constants_are_defined_once(self):
        for site in agent_policy.PERSISTENT_SITES:
            for path in CONSUMERS:
                self.assertNotIn(f'"{site}"', path.read_text(), path)
        for path in CONSUMERS:
            self.assertNotIn("[0-9a-f]{32}", path.read_text(), path)

    def test_classify_site(self):
        for site in agent_policy.PERSISTENT_SITES:
            self.assertEqual(agent_policy.classify_site(site), agent_policy.PERSISTENT)
        self.assertEqual(agent_policy.classify_site(TEMPORARY), agent_policy.TEMPORARY)
        self.assertEqual(agent_policy.classify_site(f"bond-management-race-{HEX}.localhost"), "temporary")
        for site in (*FOREIGN, None, 1, ["bond-management-dev.localhost"]):
            self.assertEqual(agent_policy.classify_site(site), agent_policy.FOREIGN, site)

    def test_hex_suffix_boundary(self):
        # Less than, equal to and greater than the 32 hex characters.
        for length, kind in ((31, "foreign"), (32, "temporary"), (33, "foreign")):
            site = f"bond-management-x-{('a' * length)}.localhost"
            self.assertEqual(agent_policy.classify_site(site), kind, length)

    def test_every_destructive_verb_against_every_site_class(self):
        cases = [(site, PERSISTENT_REASON) for site in sorted(agent_policy.PERSISTENT_SITES)]
        cases += [(TEMPORARY, None)] + [(site, FOREIGN_REASON) for site in FOREIGN]
        for verb in DESTRUCTIVE:
            for site, expected in cases:
                for argv in spellings(verb, site):
                    with self.subTest(verb=verb, site=site, argv=argv):
                        self.assert_violation(argv, expected)
                        self.assert_violation(["cd", "../..", *argv], expected)

    def test_destructive_verb_without_one_site(self):
        for verb in DESTRUCTIVE:
            force = ["--force"] if verb == "new-site" else []
            with self.subTest(verb=verb):
                self.assert_violation(["bench", verb, *force], FOREIGN_REASON)
                self.assert_violation(
                    ["bench", "--site", TEMPORARY, "--site", TEMPORARY, verb, *force], FOREIGN_REASON
                )
                self.assert_violation(["bench", verb, *force, "--site"], FOREIGN_REASON)

    def test_positional_verbs_reject_a_site_option(self):
        for verb in sorted(agent_policy.POSITIONAL_SITE_VERBS):
            force = ["--force"] if verb == "new-site" else []
            self.assert_violation(["bench", "--site", TEMPORARY, verb, TEMPORARY, *force], FOREIGN_REASON)
            self.assert_violation(["bench", verb, "--no-backup", TEMPORARY, *force], FOREIGN_REASON)

    def test_two_destructive_verbs_are_ambiguous(self):
        argv = ["bench", "--site", TEMPORARY, "restore", "reinstall"]
        self.assert_violation(argv, "Ambiguous destructive bench command.")

    def test_non_destructive_calls_are_not_checked(self):
        for site in agent_policy.PERSISTENT_SITES:
            self.assert_violation(["bench", "--site", site, "migrate"], None)
            self.assert_violation(["bench", "new-site", site], None)
            self.assert_violation(["echo", "drop-site", site], None)
        self.assert_violation([], None)

    def test_bench_is_matched_by_path_name(self):
        site = "bond-management-dev.localhost"
        for program in ("bench", "/usr/local/bin/bench", "env/bin/BENCH"):
            self.assert_violation([program, "drop-site", site], PERSISTENT_REASON)

    def test_secret_names(self):
        # The observer socket and user are scrubbed by name, not by pattern.
        for name in agent_policy.SECRET_ENV_VARS:
            if name.endswith("PASSWORD"):
                self.assertRegex(name, agent_policy.SECRET_NAME)
        for name in ("db_password", "API_KEY", "GITHUB_TOKEN", "CLIENT_SECRET"):
            self.assertRegex(name, agent_policy.SECRET_NAME)
        self.assertIsNone(agent_policy.SECRET_NAME.search("FRAPPE_USER"))

    def test_script_accepts_only_one_temporary_site(self):
        # scripts/verify.sh runs the core this way before every temporary-site bench call.
        cases = [([TEMPORARY], 0), ([], 1), ([TEMPORARY, TEMPORARY], 1)]
        cases += [([site], 1) for site in (*sorted(agent_policy.PERSISTENT_SITES), *FOREIGN)]
        for argv, expected in cases:
            with self.subTest(argv=argv):
                result = subprocess.run(
                    [sys.executable, "-I", str(CORE), *argv], capture_output=True, text=True, check=False
                )
                self.assertEqual(result.returncode, expected)
                self.assertEqual(result.stdout, "")
                for site in argv:
                    self.assertNotIn(site or "\0", result.stderr)

    def test_protected_files(self):
        expected = {"site_config.json", "common_site_config.json", "test-browser.env"}
        self.assertEqual(agent_policy.PROTECTED_FILES, expected)


if __name__ == "__main__":
    unittest.main()
