"""Financial documents are never shared, and investors stay read-only (decision 0012)."""

from types import SimpleNamespace

import frappe
from frappe.api.v1 import read_doc
from frappe.client import get as client_get
from frappe.client import set_value
from frappe.core.doctype.user_permission.user_permission import get_user_permissions
from frappe.share import add_docshare
from frappe.tests import IntegrationTestCase

from bond_management import hooks
from bond_management.bond_management.tests.factories import (
    allow_user,
    make_bond,
    make_exchange_rate,
    make_market_date,
    make_portfolio,
    make_private_file,
    make_statement,
    make_transaction,
    make_user,
    unique_name,
)
from bond_management.bond_management.utils.investor_permissions import (
    BOND_MANAGER_ROLE,
    FINANCIAL_DOCTYPES,
    INVESTOR_ROLE,
    SOURCE_DOCTYPE,
)
from bond_management.bond_management.utils.statement_exchange_rates import sync_statement_exchange_rates

SHARE_PATCHES = (
    "remove_financial_document_shares",
    "enforce_investor_share_boundary",
    "cleanup_incompatible_file_shares",
    "add_bond_exchange_rate_source_permission",
)


class TestInvestorShares(IntegrationTestCase):
    def setUp(self):
        self.assigned = make_portfolio()
        self.other = make_portfolio()
        self.investor = make_user([INVESTOR_ROLE])
        self.manager = make_user([BOND_MANAGER_ROLE])
        self.assignment = allow_user(self.investor.name, "Bond Portfolio", self.assigned.name)

    def test_hooks_cover_every_financial_doctype_and_share(self):
        # hooks.py keeps its own copy so it stays free of app imports; keep both in sync.
        self.assertEqual(set(hooks._financial_doctypes), set(FINANCIAL_DOCTYPES))
        share_hooks = hooks.doc_events["DocShare"]
        self.assertEqual(set(share_hooks), {"before_insert", "before_validate"})
        self.assertNotIn("override_whitelisted_methods", vars(hooks))

    def test_financial_documents_cannot_be_shared_by_anyone(self):
        for document in self.financial_documents():
            for recipient in ({"user": self.manager.name}, {"user": self.investor.name}, {"everyone": 1}):
                with self.subTest(doctype=document.doctype, **recipient):
                    # The test runs as Administrator; server flags cannot skip the rule either.
                    with self.assertRaises(frappe.PermissionError):
                        add_docshare(
                            document.doctype,
                            document.name,
                            flags={"ignore_share_permission": True},
                            **recipient,
                        )

    def test_only_files_attached_to_financial_documents_cannot_be_shared(self):
        transaction = make_transaction(make_bond(), self.assigned)
        with self.assertRaises(frappe.PermissionError):
            add_docshare(
                "File", make_private_file("Bond Transaction", transaction.name).name, self.manager.name
            )
        for file in (make_private_file("User", "Administrator"), make_private_file()):
            with self.subTest(attached_to=file.attached_to_doctype):
                self.assertTrue(add_docshare("File", file.name, self.manager.name).read)

    def test_attaching_a_shared_file_to_a_financial_document_removes_its_shares(self):
        file = make_private_file()
        share = add_docshare("File", file.name, self.manager.name)
        statement = make_statement(self.assigned)

        file.attached_to_doctype = statement.doctype
        file.attached_to_name = statement.name
        file.save(ignore_permissions=True)

        self.assertFalse(frappe.db.exists("DocShare", share.name))
        self.assertEqual(
            frappe.db.get_value("File", file.name, ["attached_to_doctype", "attached_to_name"]),
            (statement.doctype, statement.name),
        )

    def test_share_patches_remove_only_financial_shares_and_rerun(self):
        financial_file = make_private_file("Bond Portfolio", self.other.name)
        financial = [
            self.legacy_share(self.assigned, self.investor.name, write=1),
            self.legacy_share(self.other, everyone=1),
            self.legacy_share(make_bond(), self.manager.name),
            self.legacy_share(self.make_statement_source(make_statement(self.other)), self.investor.name),
            self.legacy_share(financial_file, self.investor.name),
            self.legacy_share(
                frappe._dict(doctype="Bond Statement", name=unique_name("missing")), self.manager.name
            ),
        ]
        unrelated_file = make_private_file("User", "Administrator")
        kept = [
            add_docshare("File", unrelated_file.name, self.investor.name),
            add_docshare("User", self.manager.name, self.investor.name),
        ]

        for patch in SHARE_PATCHES:
            frappe.get_attr(f"bond_management.patches.{patch}.execute")()

        for share in financial:
            self.assertFalse(frappe.db.exists("DocShare", share.name), share.share_doctype)
        for share in kept:
            self.assertTrue(frappe.db.exists("DocShare", share.name), share.share_doctype)
        self.assertTrue(frappe.db.exists("File", financial_file.name))

    def test_investor_mutations_are_rejected_even_with_a_manager_role(self):
        self.investor.append("roles", {"role": BOND_MANAGER_ROLE})
        self.investor.save(ignore_permissions=True)
        for document in self.financial_documents():
            with self.subTest(doctype=document.doctype), self.set_user(self.investor.name):
                self.assertFalse(document.has_permission("write"))
                with self.assertRaises(frappe.PermissionError):
                    document.save(ignore_permissions=True)
                # Source rows validate their own deletion before the investor hook runs.
                delete_error = (
                    frappe.ValidationError if document.doctype == SOURCE_DOCTYPE else frappe.PermissionError
                )
                with self.assertRaises(delete_error):
                    document.delete(ignore_permissions=True)
                with self.assertRaises(frappe.PermissionError):
                    frappe.new_doc(document.doctype).insert(ignore_permissions=True)

    def test_stale_role_cache_cannot_restore_manager_access_for_an_investor(self):
        self.investor.append("roles", {"role": BOND_MANAGER_ROLE})
        self.investor.save(ignore_permissions=True)
        try:
            # A role cache refilled before a concurrent role save commits can
            # retain the prior manager roles after the investor role is saved.
            frappe.cache.hset("roles", self.investor.name, [BOND_MANAGER_ROLE, "All"])
            with self.set_user(self.investor.name):
                self.assertNotIn(self.other.name, self.visible_portfolios())
                with self.assertRaises(frappe.PermissionError):
                    read_doc("Bond Portfolio", self.other.name)
                with self.assertRaises(frappe.PermissionError):
                    self.assigned.save(ignore_permissions=True)
        finally:
            frappe.clear_cache(user=self.investor.name)

    def test_stray_shares_cannot_widen_investor_reads_or_grant_writes(self):
        self.legacy_share(self.other, self.investor.name)
        self.legacy_share(self.assigned, self.investor.name, write=1)
        with self.set_user(self.investor.name):
            with self.assertRaises(frappe.PermissionError):
                self.visible_portfolios()
            with self.assertRaises(frappe.PermissionError):
                client_get("Bond Portfolio", self.other.name)
            with self.assertRaises(frappe.PermissionError):
                set_value("Bond Portfolio", self.assigned.name, "account_no", "changed")
        self.assigned.reload()
        self.assertNotEqual(self.assigned.account_no, "changed")

    def test_investors_cannot_read_exchange_rate_source_even_with_a_stray_share(self):
        source = self.make_statement_source(make_statement(self.assigned))
        with self.set_user(self.investor.name):
            with self.assertRaises(frappe.PermissionError):
                read_doc(SOURCE_DOCTYPE, source.name)
            with self.assertRaises(frappe.PermissionError):
                frappe.qb.get_query(SOURCE_DOCTYPE, fields=["name"], ignore_permissions=False).run()

        # Without a Source DocPerm Frappe skips list hooks, so only the document check applies.
        self.legacy_share(source, self.investor.name)
        with self.set_user(self.investor.name):
            with self.assertRaises(frappe.PermissionError):
                read_doc(SOURCE_DOCTYPE, source.name)

    def test_moving_an_assignment_refreshes_the_previous_users_permission_cache(self):
        next_investor = make_user([INVESTOR_ROLE])
        self.assertTrue(get_user_permissions(self.investor.name).get("Bond Portfolio"))
        self.assignment.user = next_investor.name
        self.assignment.save(ignore_permissions=True)
        self.assertFalse(get_user_permissions(self.investor.name).get("Bond Portfolio"))
        self.assertTrue(get_user_permissions(next_investor.name).get("Bond Portfolio"))
        with self.set_user(self.investor.name):
            self.assertNotIn(self.assigned.name, self.visible_portfolios())
        with self.set_user(next_investor.name):
            self.assertIn(self.assigned.name, self.visible_portfolios())

    def financial_documents(self):
        bond = make_bond()
        documents = (
            self.assigned,
            make_transaction(bond, self.assigned),
            make_statement(self.assigned),
            bond,
            make_market_date(bond),
            make_exchange_rate(),
            self.make_statement_source(make_statement(self.assigned, statement_date="2091-04-06")),
        )
        self.assertEqual({doc.doctype for doc in documents}, set(FINANCIAL_DOCTYPES))
        return documents

    def visible_portfolios(self):
        return frappe.qb.get_query("Bond Portfolio", fields=["name"], ignore_permissions=False).run(
            pluck=True
        )

    def legacy_share(self, document, user=None, **permissions):
        # db_insert deliberately bypasses hooks to represent shares made before decision 0012.
        share = frappe.get_doc(
            {
                "doctype": "DocShare",
                "name": unique_name("legacy-share"),
                "share_doctype": document.doctype,
                "share_name": document.name,
                "user": user,
                "read": 1,
                "owner": "Administrator",
                **permissions,
            }
        )
        share.db_insert()
        return share

    def make_statement_source(self, statement):
        sync_statement_exchange_rates(
            statement,
            [SimpleNamespace(from_currency="EUR", to_currency="USD", rate="0.91")],
        )
        source_name = frappe.db.get_value(SOURCE_DOCTYPE, {"statement": statement.name}, "name")
        return frappe.get_doc(SOURCE_DOCTYPE, source_name)
