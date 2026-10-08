"""Exercise the shared security gate with real Semgrep findings in temporary apps."""

import argparse
import os
import shutil
import subprocess
import tempfile
import unittest
from pathlib import Path


class SemgrepGateTests(unittest.TestCase):
    semgrep_binary: str
    frappe_rules: str

    def setUp(self):
        temporary_directory = tempfile.TemporaryDirectory(prefix="bond-semgrep-gate-")
        self.addCleanup(temporary_directory.cleanup)
        self.app_root = Path(temporary_directory.name) / "apps" / "bond_management"
        self.app_root.mkdir(parents=True)
        source_root = Path(__file__).resolve().parent.parent
        (self.app_root / "scripts").mkdir()
        shutil.copy2(source_root / "scripts" / "verify.sh", self.app_root / "scripts" / "verify.sh")
        shutil.copytree(source_root / "semgrep", self.app_root / "semgrep")

    def test_clean_source_passes(self):
        result = self.scan("value = 1\n")
        self.assertEqual(result.returncode, 0, result.stdout)
        self.assertIn("Running Bond Management Semgrep rule tests.", result.stdout)

    def test_frappe_error_blocks_before_advisory_and_app_scans(self):
        result = self.scan("value = eval(user_input)\n")
        self.assertEqual(result.returncode, 1, result.stdout)
        self.assertIn("frappe-codeinjection-eval", "".join(result.stdout.split()))
        self.assertNotIn("Running advisory Frappe Semgrep rules.", result.stdout)

    def test_app_error_blocks_before_rule_tests(self):
        result = self.scan("import frappe\nfrappe.db.commit()\n")
        self.assertEqual(result.returncode, 1, result.stdout)
        self.assertIn(
            "bond-management-no-manual-transaction-boundary",
            "".join(result.stdout.split()),
        )
        self.assertNotIn("Running Bond Management Semgrep rule tests.", result.stdout)

    def test_advisory_warning_does_not_block(self):
        result = self.scan('import frappe\nfrappe.db.sql(f"SELECT {user_input}")\n')
        self.assertEqual(result.returncode, 0, result.stdout)
        self.assertIn("frappe-sql-format-injection", "".join(result.stdout.split()))
        self.assertIn("Running Bond Management Semgrep rule tests.", result.stdout)

    def scan(self, source):
        (self.app_root / "violation.py").write_text(source, encoding="utf-8")
        environment = os.environ | {
            "SEMGREP_BIN": self.semgrep_binary,
            "FRAPPE_SEMGREP_RULES_DIR": self.frappe_rules,
        }
        return subprocess.run(
            [
                "bash",
                "-c",
                'source "$1"; run_semgrep',
                "semgrep-gate-test",
                str(self.app_root / "scripts" / "verify.sh"),
            ],
            cwd=self.app_root,
            env=environment,
            stdout=subprocess.PIPE,
            stderr=subprocess.STDOUT,
            text=True,
            timeout=120,
            check=False,
        )


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--semgrep", required=True)
    parser.add_argument("--frappe-rules", required=True)
    arguments, unittest_arguments = parser.parse_known_args()
    SemgrepGateTests.semgrep_binary = str(Path(arguments.semgrep).resolve())
    SemgrepGateTests.frappe_rules = str(Path(arguments.frappe_rules).resolve())
    unittest.main(argv=[__file__, *unittest_arguments])
