"""Cases for scripts/verify.sh credential loading and temporary-site checks.

Every credential value here is synthetic, and bench is replaced by a shell
function that only records its arguments, so no site is touched.
"""

import json
import os
import subprocess
import tempfile
import unittest
from pathlib import Path

SCRIPTS = Path(__file__).resolve().parent
VERIFY = SCRIPTS / "verify.sh"
PLAYWRIGHT = SCRIPTS.parent / "node_modules" / ".bin" / "playwright"
NAMES = ("FRAPPE_USER", "FRAPPE_PASSWORD", "FRAPPE_ADMIN_USER", "FRAPPE_ADMIN_PASSWORD")
FILE_VALUES = {
    "FRAPPE_USER": "synthetic-investor@example.com",
    "FRAPPE_PASSWORD": "synthetic-investor-value",
    "FRAPPE_ADMIN_USER": "Administrator",
    "FRAPPE_ADMIN_PASSWORD": "synthetic admin value",
}
HEX = "0123456789abcdef" * 2
TEMPORARY = f"bond-management-lifecycle-{HEX}.localhost"
# Prints the four variables as a child process sees them, then stops before bench.
REPORT_AND_STOP = (
    "prepare_playwright_site() { python3 -c 'import json, os; "
    f'print(json.dumps({{name: os.environ.get(name) for name in "{" ".join(NAMES)}".split()}}))'
    "'; exit 0; }"
)
RECORD_BENCH = 'bench() { printf "%s\\n" "$*" >> "${BENCH_LOG}"; }'


class VerifyHelperTests(unittest.TestCase):
    def setUp(self):
        directory = tempfile.TemporaryDirectory()
        self.addCleanup(directory.cleanup)
        self.home = Path(directory.name)
        self.credentials = self.home / ".config" / "bond_management" / "test-browser.env"
        self.bench_log = self.home / "bench.log"

    def write_credentials(self, text):
        self.credentials.parent.mkdir(parents=True)
        self.credentials.write_text(text)

    def run_verify(self, script, **environment):
        env = {key: value for key, value in os.environ.items() if key not in NAMES}
        env.update(HOME=str(self.home), BENCH_LOG=str(self.bench_log), **environment)
        return subprocess.run(
            ["bash", "-c", f'source "$1"; {script}', "bash", str(VERIFY)],
            env=env,
            capture_output=True,
            text=True,
            check=False,
        )

    def browser_environment(self, result):
        self.assertEqual(result.returncode, 0, result.stderr)
        return json.loads(result.stdout)

    def bench_calls(self):
        return self.bench_log.read_text().splitlines() if self.bench_log.exists() else []

    def test_ui_loads_the_credentials_file(self):
        self.write_credentials("".join(f'{name}="{value}"\n' for name, value in FILE_VALUES.items()))
        result = self.run_verify(f"{REPORT_AND_STOP}; run_playwright_tests")
        self.assertEqual(self.browser_environment(result), FILE_VALUES)
        self.assertEqual(result.stderr, "")

    def test_exported_variables_win_over_the_file(self):
        self.write_credentials("".join(f'{name}="{value}"\n' for name, value in FILE_VALUES.items()))
        caller = {"FRAPPE_USER": "caller@example.com", "FRAPPE_PASSWORD": "synthetic-caller-value"}
        result = self.run_verify(f"{REPORT_AND_STOP}; run_playwright_tests", **caller)
        self.assertEqual(self.browser_environment(result), {**FILE_VALUES, **caller})

    def test_file_is_not_read_when_every_variable_is_exported(self):
        marker = self.home / "sourced"
        self.write_credentials(f'touch "{marker}"\n')
        caller = {name: f"synthetic-caller-{index}" for index, name in enumerate(NAMES)}
        result = self.run_verify(f"{REPORT_AND_STOP}; run_playwright_tests", **caller)
        self.assertEqual(self.browser_environment(result), caller)
        self.assertFalse(marker.exists())

    def test_missing_file_and_variables_fail_with_a_hint(self):
        result = self.run_verify(f"{REPORT_AND_STOP}; run_playwright_tests")
        self.assertEqual(result.returncode, 1)
        self.assertIn("FRAPPE_USER and FRAPPE_PASSWORD are required", result.stderr)
        self.assertIn("test-browser.env", result.stderr)
        self.assertEqual(result.stdout, "")

    def test_partial_file_reports_the_missing_pair(self):
        self.write_credentials('FRAPPE_USER="u@example.com"\nFRAPPE_PASSWORD="synthetic-canary-a"\n')
        result = self.run_verify(f"{REPORT_AND_STOP}; run_playwright_tests")
        self.assertEqual(result.returncode, 1)
        self.assertIn("FRAPPE_ADMIN_USER and FRAPPE_ADMIN_PASSWORD are required", result.stderr)
        self.assertNotIn("synthetic-canary", result.stdout + result.stderr)

    def test_file_contents_are_never_echoed(self):
        self.write_credentials(
            "set -x\n"
            "echo synthetic-canary-a\n"
            "FRAPPE_PASSWORD= synthetic-canary-b\n"
            'FRAPPE_USER="synthetic-canary-c"\n'
            'FRAPPE_PASSWORD="synthetic-canary-d"\n'
            'FRAPPE_ADMIN_USER="synthetic-canary-e"\n'
            'FRAPPE_ADMIN_PASSWORD="$UNSET_IN_FILE synthetic-canary-f"\n'
        )
        # The caller's xtrace must not trace any value either.
        result = self.run_verify(
            "prepare_playwright_site() { exit 0; }; set -x; run_playwright_tests",
            FRAPPE_ADMIN_PASSWORD="synthetic-canary-g",
        )
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertNotIn("synthetic-canary", result.stdout + result.stderr)

    def test_unloadable_file_fails_closed_without_echoing(self):
        self.write_credentials('FRAPPE_PASSWORD="synthetic-canary-a"\nfalse synthetic-canary-b\n')
        result = self.run_verify(f"{REPORT_AND_STOP}; run_playwright_tests")
        self.assertEqual(result.returncode, 1)
        self.assertIn("Could not load browser test credentials", result.stderr)
        self.assertNotIn("synthetic-canary", result.stdout + result.stderr)

    @unittest.skipUnless(PLAYWRIGHT.exists(), "Playwright is not installed")
    def test_extra_ui_arguments_reach_playwright(self):
        caller = {name: f"synthetic-caller-{index}" for index, name in enumerate(NAMES)}
        result = self.run_verify(
            'prepare_playwright_site() { :; }; yarn() { printf "%s\\n" "$@"; }; '
            "run_playwright_tests e2e/investor/bonds.spec.ts --project=investor-desktop",
            **caller,
        )
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertEqual(
            result.stdout.splitlines(),
            ["test:e2e", "e2e/investor/bonds.spec.ts", "--project=investor-desktop"],
        )

    def test_drop_rejects_persistent_and_foreign_sites_before_bench(self):
        for site in ("bond-management-test.localhost", "bond-management-dev.localhost", "example.localhost"):
            with self.subTest(site=site):
                result = self.run_verify(f"{RECORD_BENCH}; TEMPORARY_SITE={site}; drop_temporary_site")
                self.assertEqual(result.returncode, 1)
                self.assertIn("not one temporary Bond Management site", result.stderr)
                self.assertNotIn(site, result.stdout + result.stderr)
                self.assertEqual(self.bench_calls(), [])

    def test_drop_runs_bench_for_a_temporary_site(self):
        result = self.run_verify(f"{RECORD_BENCH}; TEMPORARY_SITE={TEMPORARY}; drop_temporary_site")
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertEqual(len(self.bench_calls()), 1)
        self.assertTrue(self.bench_calls()[0].startswith(f"drop-site {TEMPORARY} --no-backup"))

    def test_create_rejects_a_prefix_that_cannot_name_a_temporary_site(self):
        for prefix in ("", "bond-management-", "bond-management-test.localhost#"):
            with self.subTest(prefix=prefix):
                result = self.run_verify(f'{RECORD_BENCH}; create_temporary_site "{prefix}"')
                self.assertEqual(result.returncode, 1)
                self.assertIn("not one temporary Bond Management site", result.stderr)
                self.assertEqual(self.bench_calls(), [])

    def test_create_and_exit_drop_the_same_temporary_site(self):
        result = self.run_verify(f"{RECORD_BENCH}; create_temporary_site bond-management-lifecycle-")
        self.assertEqual(result.returncode, 0, result.stderr)
        calls = self.bench_calls()
        site = calls[0].split()[1]
        self.assertRegex(site, r"\Abond-management-lifecycle-[0-9a-f]{32}\.localhost\Z")
        self.assertTrue(calls[0].startswith(f"new-site {site} --admin-password "))
        self.assertTrue(calls[-1].startswith(f"drop-site {site} --no-backup"))


if __name__ == "__main__":
    unittest.main()
