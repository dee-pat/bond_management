"""Safety tests; these never connect to a site or run a migration."""

import tempfile
from pathlib import Path
from unittest import TestCase
from unittest.mock import patch

from bond_management.bond_management.tests.migration_lifecycle import OPT_IN, validate_environment
from bond_management.bond_management.tests.migration_lifecycle_fixtures import prepare_legacy_rows


class TestMigrationLifecycleGuard(TestCase):
    def setUp(self):
        self.temporary = tempfile.TemporaryDirectory(prefix="bond-lifecycle-guard-")
        self.addCleanup(self.temporary.cleanup)
        self.bench = Path(self.temporary.name) / "bench"
        self.bench.mkdir()
        self.arguments = {
            "bench_path": self.bench,
            "site_path": self.bench / "sites" / "test_site",
            "site": "test_site",
            "user": "Administrator",
            "config": {"allow_tests": True, OPT_IN: True},
        }

    def test_accepts_only_a_resolved_disposable_bench_with_parsed_true_flags(self):
        self.assertEqual(validate_environment(**self.arguments), self.bench.resolve())
        self.arguments["config"] = {"allow_tests": "true", OPT_IN: "1"}
        self.assertEqual(validate_environment(**self.arguments), self.bench.resolve())
        for key in ("allow_tests", OPT_IN):
            for value in (False, 0, "false", "0", "", "yes", {}, [], None):
                with self.subTest(key=key, value=value):
                    self.arguments["config"] = {"allow_tests": True, OPT_IN: True, key: value}
                    with self.assertRaisesRegex(RuntimeError, "explicit"):
                        validate_environment(**self.arguments)

    def test_rejects_the_canonical_bench_even_with_both_flags_enabled(self):
        self.arguments.update(
            bench_path="/Users/example/frappe-bench", site_path="/Users/example/frappe-bench/sites/test_site"
        )
        with self.assertRaisesRegex(RuntimeError, "temporary"):
            validate_environment(**self.arguments)
        link = Path(self.temporary.name) / "canonical-link"
        link.symlink_to("/Users/example/frappe-bench")
        self.arguments.update(bench_path=link, site_path=link / "sites" / "test_site")
        with self.assertRaisesRegex(RuntimeError, "temporary"):
            validate_environment(**self.arguments)

    def test_rejects_non_test_sites_and_a_site_resolved_outside_the_bench(self):
        self.arguments["site"] = "dev.local"
        with self.assertRaisesRegex(RuntimeError, "test_site"):
            validate_environment(**self.arguments)
        self.arguments.update(
            site="test_site", site_path=Path(self.temporary.name) / "other-bench" / "sites" / "test_site"
        )
        with self.assertRaisesRegex(RuntimeError, "test_site"):
            validate_environment(**self.arguments)

    def test_rejects_callers_other_than_administrator(self):
        for user in ("Guest", "test@example.com", None):
            with self.subTest(user=user):
                self.arguments["user"] = user
                with self.assertRaisesRegex(RuntimeError, "Administrator"):
                    validate_environment(**self.arguments)

    def test_direct_fixture_entry_requires_the_same_disposable_bench_guard(self):
        with patch(
            "bond_management.bond_management.tests.migration_lifecycle._guard",
            side_effect=RuntimeError("Disposable bench required"),
        ):
            with self.assertRaisesRegex(RuntimeError, "Disposable bench"):
                prepare_legacy_rows()
