"""Safety tests; these never connect to a site or run a migration."""

import tempfile
from pathlib import Path
from unittest import TestCase
from unittest.mock import patch

from bond_management.bond_management.tests.migration_lifecycle import (
    OPT_IN,
    _snapshot_files,
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


class TestMigrationLifecycleSnapshots(TestCase):
    def test_snapshot_ignores_obsolete_statement_report_queued_for_deletion(self):
        fixtures = {"statement": "statement-1", "transaction": "transaction-1"}
        document_values = {
            ("Bond Statement", "statement-1"): {
                "attachment": "/private/files/statement.pdf",
                "quantity_reconciliation_report": "/private/files/QuantityBasis-v8.pdf",
            },
            ("Bond Transaction", "transaction-1"): {"attachment": "/private/files/transaction.pdf"},
        }
        file_rows = [
            {
                "file_url": file_url,
                "file_name": file_url.rsplit("/", 1)[-1],
                "is_private": 1,
                "attached_to_doctype": doctype,
                "attached_to_name": name,
                "attached_to_field": field,
            }
            for doctype, name, field, file_url in (
                (
                    "Bond Statement",
                    "statement-1",
                    "attachment",
                    "/private/files/statement.pdf",
                ),
                (
                    "Bond Statement",
                    "statement-1",
                    "quantity_reconciliation_report",
                    "/private/files/FaceValue-v2.pdf",
                ),
                (
                    "Bond Statement",
                    "statement-1",
                    "quantity_reconciliation_report",
                    "/private/files/QuantityBasis-v8.pdf",
                ),
                (
                    "Bond Transaction",
                    "transaction-1",
                    "attachment",
                    "/private/files/transaction.pdf",
                ),
            )
        ]

        def get_doc(doctype, name):
            return document_values[(doctype, name)]

        def get_rows(_doctype, fields, filters):
            return [
                {field: row[field] for field in fields}
                for row in file_rows
                if all(row.get(field) == value for field, value in filters.items())
            ]

        with (
            patch(
                "bond_management.bond_management.tests.migration_lifecycle.frappe.get_doc",
                side_effect=get_doc,
            ),
            patch("bond_management.bond_management.tests.migration_lifecycle._rows", side_effect=get_rows),
        ):
            snapshot = _snapshot_files(fixtures)

        report_files = snapshot["Bond Statement:statement-1:quantity_reconciliation_report"]
        self.assertEqual([file["file_url"] for file in report_files], ["/private/files/QuantityBasis-v8.pdf"])
