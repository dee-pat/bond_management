"""Safety tests; these never connect to a site or run a migration."""

import tempfile
from pathlib import Path
from unittest import TestCase
from unittest.mock import patch

from bond_management.bond_management.tests.migration_lifecycle import (
    OPT_IN,
    validate_environment,
)
from bond_management.bond_management.tests.migration_lifecycle_fixtures import prepare_legacy_rows
from bond_management.bond_management.tests.temporary_site_guard import validate_temporary_site

LIFECYCLE_SITE = "bond-management-lifecycle-0123456789abcdef0123456789abcdef.localhost"


class TestMigrationLifecycleGuard(TestCase):
    def setUp(self):
        self.temporary = tempfile.TemporaryDirectory(prefix="bond-lifecycle-guard-")
        self.addCleanup(self.temporary.cleanup)
        self.bench = Path(self.temporary.name) / "bench"
        self.bench.mkdir()
        self.arguments = {
            "bench_path": self.bench,
            "site_path": self.bench / "sites" / LIFECYCLE_SITE,
            "site": LIFECYCLE_SITE,
            "user": "Administrator",
            "config": {"allow_tests": True, OPT_IN: True},
        }

    def test_accepts_a_lifecycle_site_with_parsed_true_flags(self):
        self.assertEqual(validate_environment(**self.arguments), self.bench.resolve())
        self.arguments["config"] = {"allow_tests": "true", OPT_IN: "1"}
        self.assertEqual(validate_environment(**self.arguments), self.bench.resolve())
        for key in ("allow_tests", OPT_IN):
            for value in (False, 0, "false", "0", "", "yes", {}, [], None):
                with self.subTest(key=key, value=value):
                    self.arguments["config"] = {"allow_tests": True, OPT_IN: True, key: value}
                    with self.assertRaisesRegex(RuntimeError, "true"):
                        validate_environment(**self.arguments)

    def test_accepts_a_temporary_site_in_the_configured_bench(self):
        bench = Path(__file__).resolve().parents[5]
        self.arguments.update(bench_path=bench, site_path=bench / "sites" / LIFECYCLE_SITE)
        self.assertEqual(validate_environment(**self.arguments), bench.resolve())

    def test_accepts_the_concurrency_harness_site_prefix(self):
        site = "bond-management-race-0123456789abcdef0123456789abcdef.localhost"
        self.arguments.update(site=site, site_path=self.bench / "sites" / site)
        self.arguments["config"] = {"allow_tests": True}
        self.assertEqual(
            validate_temporary_site(
                **self.arguments,
                site_prefix="bond-management-race-",
            ),
            self.bench.resolve(),
        )

    def test_rejects_persistent_and_legacy_site_names(self):
        for site in (
            "bond-management-dev.localhost",
            "bond-management-test.localhost",
            "dev.local",
            "test_site",
        ):
            with self.subTest(site=site):
                self.arguments.update(site=site, site_path=self.bench / "sites" / site)
                with self.assertRaisesRegex(RuntimeError, "unique bond-management-lifecycle"):
                    validate_environment(**self.arguments)

    def test_rejects_a_site_outside_the_configured_bench(self):
        self.arguments["site_path"] = Path(self.temporary.name) / "other-bench" / "sites" / LIFECYCLE_SITE
        with self.assertRaisesRegex(RuntimeError, "directly under the configured bench"):
            validate_environment(**self.arguments)

    def test_rejects_a_sites_directory_symlinked_outside_the_bench(self):
        outside_sites = Path(self.temporary.name) / "outside" / "sites"
        outside_sites.mkdir(parents=True)
        linked_bench = Path(self.temporary.name) / "linked-bench"
        linked_bench.mkdir()
        (linked_bench / "sites").symlink_to(outside_sites, target_is_directory=True)
        self.arguments.update(
            bench_path=linked_bench,
            site_path=linked_bench / "sites" / LIFECYCLE_SITE,
        )
        with self.assertRaisesRegex(RuntimeError, "inside the configured bench"):
            validate_environment(**self.arguments)

    def test_rejects_callers_other_than_administrator(self):
        for user in ("Guest", "test@example.com", None):
            with self.subTest(user=user):
                self.arguments["user"] = user
                with self.assertRaisesRegex(RuntimeError, "Administrator"):
                    validate_environment(**self.arguments)

    def test_direct_fixture_entry_requires_the_same_temporary_site_guard(self):
        with patch(
            "bond_management.bond_management.tests.migration_lifecycle._guard",
            side_effect=RuntimeError("Temporary lifecycle site required"),
        ):
            with self.assertRaisesRegex(RuntimeError, "Temporary lifecycle site"):
                prepare_legacy_rows()
