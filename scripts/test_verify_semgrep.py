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
        self.assertIn("Running blocking frappe-agent-kit Semgrep rules.", result.stdout)
        # The kit's rule fixtures hold deliberate findings, so a pass shows they were not scanned.
        self.assertTrue((self.app_root / "semgrep" / "kit" / "tests" / "transactions.py").is_file())

    def test_frappe_error_blocks_before_advisory_and_kit_scans(self):
        result = self.scan("value = eval(user_input)\n")
        self.assertEqual(result.returncode, 1, result.stdout)
        self.assertIn("frappe-codeinjection-eval", "".join(result.stdout.split()))
        self.assertNotIn("Running advisory Frappe Semgrep rules.", result.stdout)
        self.assertNotIn("Running blocking frappe-agent-kit Semgrep rules.", result.stdout)

    def test_kit_transaction_rule_blocks(self):
        # frappe-manual-commit is a Frappe WARNING, so only the kit scan blocks this.
        result = self.scan("import frappe\nfrappe.db.commit()\n")
        self.assertEqual(result.returncode, 1, result.stdout)
        self.assertIn("Running blocking frappe-agent-kit Semgrep rules.", result.stdout)
        self.assertIn("frappe-kit-no-manual-transaction-boundary", "".join(result.stdout.split()))

    def test_kit_decimal_rule_blocks(self):
        result = self.scan("from decimal import Decimal\nvalue = Decimal(0.1)\n")
        self.assertEqual(result.returncode, 1, result.stdout)
        self.assertIn("frappe-kit-decimal-from-float-literal", "".join(result.stdout.split()))

    def test_advisory_warning_does_not_block(self):
        result = self.scan('import frappe\nfrappe.db.sql(f"SELECT {user_input}")\n')
        self.assertEqual(result.returncode, 0, result.stdout)
        self.assertIn("frappe-sql-format-injection", "".join(result.stdout.split()))
        self.assertIn("Running blocking frappe-agent-kit Semgrep rules.", result.stdout)

    def scan(self, source):
        (self.app_root / "violation.py").write_text(source, encoding="utf-8")
        environment = os.environ | {"SEMGREP_BIN": self.semgrep_binary}
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
    arguments, unittest_arguments = parser.parse_known_args()
    SemgrepGateTests.semgrep_binary = str(Path(arguments.semgrep).resolve())
    unittest.main(argv=[__file__, *unittest_arguments])
