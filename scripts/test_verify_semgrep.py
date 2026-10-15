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


class FrappeRulesCacheTests(unittest.TestCase):
    def setUp(self):
        temporary_directory = tempfile.TemporaryDirectory(prefix="bond-semgrep-cache-")
        self.addCleanup(temporary_directory.cleanup)
        self.root = Path(temporary_directory.name)
        self.temporary_root = self.root / "tmp"
        self.temporary_root.mkdir()
        self.cache = self.root / "cache" / "rules"
        self.remote = self.root / "remote"
        self.remote_sha = self.create_remote(self.remote)
        self.verify_script = Path(__file__).resolve().parent / "verify.sh"

    def test_unreachable_remote_leaves_no_cache_entry(self):
        result = self.resolve(self.missing_remote())
        self.assertNotEqual(result.returncode, 0, result.stdout)
        self.assertFalse(self.cache.exists())
        self.assertIn("nothing was cached", result.stdout)
        self.assert_no_staging_left()

    def test_fetch_populates_cache_at_pinned_revision(self):
        result = self.resolve(self.reachable_remote())
        self.assertEqual(result.returncode, 0, result.stdout)
        self.assertEqual(result.stdout.strip(), str(self.cache))
        self.assert_cache_is_pinned()
        self.assert_no_staging_left()

    def test_clean_cache_entry_is_reused_without_fetching(self):
        self.assertEqual(self.resolve(self.reachable_remote()).returncode, 0)
        result = self.resolve(self.missing_remote())
        self.assertEqual(result.returncode, 0, result.stdout)
        self.assert_cache_is_pinned()

    def test_unborn_cache_entry_is_replaced(self):
        self.git("init", "-q", str(self.cache))
        result = self.resolve(self.reachable_remote())
        self.assertEqual(result.returncode, 0, result.stdout)
        self.assert_cache_is_pinned()
        self.assert_no_staging_left()

    def test_dirty_cache_entry_is_replaced(self):
        changes = {
            "deleted": lambda: (self.cache / "rules" / "rule.yml").unlink(),
            "modified": lambda: (self.cache / "rules" / "rule.yml").write_text("rules: [x]\n"),
            "untracked": lambda: (self.cache / "rules" / "extra.yml").write_text("rules: []\n"),
            "ignored": lambda: (self.cache / "rules" / "extra.pyc").write_text("cached\n"),
        }
        for name, change in changes.items():
            with self.subTest(name):
                self.assertEqual(self.resolve(self.reachable_remote()).returncode, 0)
                change()
                result = self.resolve(self.reachable_remote())
                self.assertEqual(result.returncode, 0, result.stdout)
                self.assert_cache_is_pinned()
                self.assert_no_staging_left()

    def test_failed_repair_cleans_up_staging(self):
        self.git("init", "-q", str(self.cache))
        result = self.resolve(self.missing_remote())
        self.assertNotEqual(result.returncode, 0, result.stdout)
        self.assert_no_staging_left()

    def test_entry_published_by_another_run_during_fetch_is_kept(self):
        # A git wrapper publishes the cache entry, marked as another run's, as
        # soon as this run starts its fetch.
        wrapper_root = self.root / "bin"
        wrapper_root.mkdir()
        wrapper = wrapper_root / "git"
        wrapper.write_text(
            "#!/usr/bin/env bash\n"
            'if [[ " $* " == *" fetch "* && ! -e "${PUBLISH_CACHE}" ]]; then\n'
            '    "${REAL_GIT}" clone -q "${PUBLISH_FROM}" "${PUBLISH_CACHE}" &&\n'
            '        touch "${PUBLISH_CACHE}/.git/published-by-another-run"\n'
            "fi\n"
            'exec "${REAL_GIT}" "$@"\n',
            encoding="utf-8",
        )
        wrapper.chmod(0o755)

        result = self.resolve(
            self.reachable_remote(),
            {
                "PATH": f"{wrapper_root}{os.pathsep}{os.environ['PATH']}",
                "REAL_GIT": shutil.which("git"),
                "PUBLISH_FROM": str(self.remote),
                "PUBLISH_CACHE": str(self.cache),
            },
        )
        self.assertEqual(result.returncode, 0, result.stdout)
        self.assertTrue((self.cache / ".git" / "published-by-another-run").exists())
        self.assert_cache_is_pinned()
        self.assert_no_staging_left()

    def test_publication_waits_for_another_run_holding_the_lock(self):
        # Another run takes the publish lock as this run starts its fetch. This
        # run must wait instead of renaming the entry; its first wait publishes
        # the other run's entry and releases the lock, and that entry is kept.
        wrapper_root = self.root / "bin"
        wrapper_root.mkdir()
        git_wrapper = wrapper_root / "git"
        git_wrapper.write_text(
            "#!/usr/bin/env bash\n"
            'if [[ " $* " == *" fetch "* ]]; then\n'
            '    mkdir -p "$(dirname "${PUBLISH_CACHE}")" && mkdir "${PUBLISH_CACHE}.lock"\n'
            "fi\n"
            'exec "${REAL_GIT}" "$@"\n',
            encoding="utf-8",
        )
        sleep_wrapper = wrapper_root / "sleep"
        sleep_wrapper.write_text(
            "#!/usr/bin/env bash\n"
            'if [[ -d "${PUBLISH_CACHE}.lock" && ! -e "${PUBLISH_CACHE}" ]]; then\n'
            '    "${REAL_GIT}" clone -q "${PUBLISH_FROM}" "${PUBLISH_CACHE}" &&\n'
            '        touch "${PUBLISH_CACHE}/.git/published-by-another-run" &&\n'
            '        rmdir "${PUBLISH_CACHE}.lock"\n'
            "fi\n",
            encoding="utf-8",
        )
        for wrapper in (git_wrapper, sleep_wrapper):
            wrapper.chmod(0o755)

        result = self.resolve(
            self.reachable_remote(),
            {
                "PATH": f"{wrapper_root}{os.pathsep}{os.environ['PATH']}",
                "REAL_GIT": shutil.which("git"),
                "PUBLISH_FROM": str(self.remote),
                "PUBLISH_CACHE": str(self.cache),
            },
        )
        self.assertEqual(result.returncode, 0, result.stdout)
        self.assertTrue((self.cache / ".git" / "published-by-another-run").exists())
        self.assert_cache_is_pinned()
        self.assert_no_staging_left()

    def test_held_lock_times_out_without_publishing(self):
        self.cache.parent.mkdir(parents=True)
        lock = self.cache.parent / f"{self.cache.name}.lock"
        lock.mkdir()
        result = self.resolve(self.reachable_remote(), {"FRAPPE_SEMGREP_RULES_LOCK_TIMEOUT": "0"})
        self.assertNotEqual(result.returncode, 0, result.stdout)
        self.assertIn(f"Timed out waiting for {lock}", result.stdout)
        self.assertFalse(self.cache.exists())
        lock.rmdir()
        self.assert_no_staging_left()

    def resolve(self, repository, extra_environment=None):
        script = (
            'source "$1"; '
            'FRAPPE_SEMGREP_RULES_REPOSITORY="$2"; '
            'FRAPPE_SEMGREP_RULES_SHA="$3"; '
            'FRAPPE_SEMGREP_RULES_CACHE="$4"; '
            'rules_dir="$(frappe_semgrep_rules_dir)"; '
            'printf "%s\\n" "${rules_dir}"'
        )
        environment = (
            {key: value for key, value in os.environ.items() if key != "FRAPPE_SEMGREP_RULES_DIR"}
            | {"TMPDIR": str(self.temporary_root)}
            | (extra_environment or {})
        )
        return subprocess.run(
            [
                "bash",
                "-c",
                script,
                "semgrep-rules-cache-test",
                str(self.verify_script),
                repository,
                self.remote_sha,
                str(self.cache),
            ],
            env=environment,
            stdout=subprocess.PIPE,
            stderr=subprocess.STDOUT,
            text=True,
            timeout=60,
            check=False,
        )

    def reachable_remote(self):
        return f"file://{self.remote}"

    def missing_remote(self):
        return f"file://{self.root / 'missing'}"

    def assert_cache_is_pinned(self):
        self.assertEqual(self.head(self.cache), self.remote_sha)
        status = self.git(
            "-C", str(self.cache), "status", "--porcelain", "--untracked-files=all", "--ignored"
        )
        self.assertEqual(status.stdout, "")

    def assert_no_staging_left(self):
        self.assertEqual(list(self.temporary_root.iterdir()), [])
        cache_parent = self.cache.parent
        leftovers = [p.name for p in cache_parent.iterdir()] if cache_parent.exists() else []
        self.assertEqual([name for name in leftovers if name != self.cache.name], [])

    def create_remote(self, path):
        self.git("init", "-q", str(path))
        (path / "rules").mkdir()
        (path / "rules" / "rule.yml").write_text("rules: []\n", encoding="utf-8")
        (path / ".gitignore").write_text("*.pyc\n", encoding="utf-8")
        self.git("-C", str(path), "add", "rules", ".gitignore")
        self.git(
            "-C",
            str(path),
            "-c",
            "user.name=Semgrep Cache Test",
            "-c",
            "user.email=semgrep-cache-test@example.invalid",
            "-c",
            "commit.gpgsign=false",
            "commit",
            "-q",
            "-m",
            "rules",
        )
        return self.head(path)

    def head(self, path):
        return self.git("-C", str(path), "rev-parse", "HEAD").stdout.strip()

    def git(self, *arguments):
        return subprocess.run(
            ["git", *arguments],
            capture_output=True,
            text=True,
            check=True,
        )


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--semgrep", required=True)
    parser.add_argument("--frappe-rules", required=True)
    arguments, unittest_arguments = parser.parse_known_args()
    SemgrepGateTests.semgrep_binary = str(Path(arguments.semgrep).resolve())
    SemgrepGateTests.frappe_rules = str(Path(arguments.frappe_rules).resolve())
    unittest.main(argv=[__file__, *unittest_arguments])
