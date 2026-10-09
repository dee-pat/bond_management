"""Regressions for Frappe's share fallback and strict investor access."""

from contextlib import contextmanager
from unittest.mock import patch

import frappe
from frappe.api.v1 import read_doc
from frappe.client import get as client_get
from frappe.client import set_value
from frappe.core.doctype.user_permission.user_permission import get_user_permissions
from frappe.share import add, add_docshare, remove, set_docshare_permission
from frappe.tests import IntegrationTestCase

from bond_management import hooks
from bond_management.bond_management.tests.factories import (
    make_bond,
    make_exchange_rate,
    make_market_date,
    make_portfolio,
    make_statement,
    make_transaction,
    unique_name,
)
from bond_management.bond_management.utils import investor_shares
from bond_management.bond_management.utils.investor_permissions import (
    BOND_MANAGER_ROLE,
    INVESTOR_ROLE,
)
from bond_management.bond_management.utils.investor_shares import FINANCIAL_DOCTYPES
from bond_management.patches.enforce_investor_share_boundary import execute


class TestInvestorShares(IntegrationTestCase):
    def setUp(self):
        self.assigned = make_portfolio()
        self.other = make_portfolio()
        self.investor = self.make_user([INVESTOR_ROLE])
        self.manager = self.make_user([BOND_MANAGER_ROLE])
        self.assignment = frappe.get_doc(
            {
                "doctype": "User Permission",
                "user": self.investor.name,
                "allow": "Bond Portfolio",
                "for_value": self.assigned.name,
                "apply_to_all_doctypes": 1,
            }
        ).insert(ignore_permissions=True)

    def test_share_validation_allows_assigned_read_and_rejects_other_portfolio(self):
        share = add_docshare("Bond Portfolio", self.assigned.name, self.investor.name)
        self.assertTrue(share.read)
        with self.assertRaises(frappe.PermissionError):
            add_docshare("Bond Portfolio", self.other.name, self.investor.name)
        with self.assertRaises(frappe.PermissionError):
            set_docshare_permission("Bond Portfolio", self.assigned.name, self.investor.name, "write", 1)

    def test_everyone_cannot_share_portfolio_data_or_global_financial_writes(self):
        with self.assertRaises(frappe.PermissionError):
            add_docshare("Bond Portfolio", self.assigned.name, everyone=1)
        bond = make_bond()
        share = add_docshare("Bond Master", bond.name, everyone=1)
        self.assertTrue(share.read)
        with self.assertRaises(frappe.PermissionError):
            add_docshare("Bond Master", bond.name, everyone=1, write=1)

    def test_server_share_flags_cannot_skip_recipient_boundary(self):
        flags = {"ignore_share_permission": True, "ignore_validate": True}
        cases = (
            (self.other, {"user": self.investor.name}),
            (self.assigned, {"user": self.investor.name, "write": 1}),
            (self.assigned, {"everyone": 1}),
        )
        for document, permissions in cases:
            with self.subTest(permissions=permissions):
                with self.assertRaises(frappe.PermissionError):
                    add_docshare(document.doctype, document.name, flags=flags, **permissions)
                self.assertFalse(
                    frappe.db.exists(
                        "DocShare", {"share_doctype": document.doctype, "share_name": document.name}
                    )
                )
        # A compatible read remains valid through the same server lifecycle.
        share = add_docshare("Bond Portfolio", self.assigned.name, self.investor.name, flags=flags)
        with self.assertRaises(frappe.PermissionError):
            add_docshare("Bond Portfolio", self.assigned.name, self.investor.name, write=1, flags=flags)
        share.reload()
        self.assertTrue(share.read)
        self.assertFalse(share.write)
        with self.as_user(self.investor.name):
            self.assertIn(self.assigned.name, self.visible_portfolios())
            self.assertNotIn(self.other.name, self.visible_portfolios())

    def test_investor_actor_cannot_create_or_update_compatible_share_with_server_flags(self):
        flags = {"ignore_share_permission": True, "ignore_validate": True}
        share = add_docshare("Bond Portfolio", self.assigned.name, self.manager.name)
        with self.as_user(self.investor.name):
            with self.assertRaises(frappe.PermissionError):
                add_docshare("Bond Portfolio", self.assigned.name, self.investor.name, flags=flags)
            with self.assertRaises(frappe.PermissionError):
                add_docshare("Bond Portfolio", self.assigned.name, self.manager.name, write=1, flags=flags)
            self.assertIn(self.assigned.name, self.visible_portfolios())
            self.assertNotIn(self.other.name, self.visible_portfolios())
        self.assertFalse(
            frappe.db.exists(
                "DocShare",
                {
                    "share_doctype": "Bond Portfolio",
                    "share_name": self.assigned.name,
                    "user": self.investor.name,
                },
            )
        )
        share.reload()
        self.assertTrue(share.read)
        self.assertFalse(share.write)

    def test_investor_with_manager_role_cannot_share_global_financial_document(self):
        self.investor.append("roles", {"role": BOND_MANAGER_ROLE})
        self.investor.save(ignore_permissions=True)
        bond = make_bond()
        with self.as_user(self.investor.name):
            with self.assertRaises(frappe.PermissionError):
                add("Bond Master", bond.name, self.manager.name)
        self.assertFalse(
            frappe.db.exists("DocShare", {"share_doctype": bond.doctype, "share_name": bond.name})
        )

    def test_investor_actor_cannot_remove_financial_share_with_server_flags(self):
        share = add_docshare("Bond Portfolio", self.assigned.name, self.investor.name)
        other_app = add_docshare("User", self.manager.name, self.investor.name)
        with self.as_user(self.investor.name):
            with patch.object(investor_shares, "_lock_users") as lock_users:
                with self.assertRaises(frappe.PermissionError):
                    remove(
                        "Bond Portfolio",
                        self.assigned.name,
                        self.investor.name,
                        flags={"ignore_share_permission": True, "ignore_permissions": True},
                    )
                remove(
                    "User",
                    self.manager.name,
                    self.investor.name,
                    flags={"ignore_share_permission": True, "ignore_permissions": True},
                )
                lock_users.assert_not_called()
        self.assertTrue(frappe.db.exists("DocShare", share.name))
        self.assertFalse(frappe.db.exists("DocShare", other_app.name))

    def test_legacy_cleanup_is_idempotent_and_preserves_compatible_and_other_app_shares(self):
        inaccessible = self.legacy_share(self.other, self.investor.name)
        assigned = self.legacy_share(self.assigned, self.investor.name, write=1, share=1)
        manager = add_docshare("Bond Portfolio", self.other.name, self.manager.name, write=1)
        other_app = add_docshare("User", self.manager.name, self.investor.name)
        everyone = self.legacy_share(self.other, everyone=1)
        bond = make_bond()
        everyone_global = self.legacy_share(bond, everyone=1, write=1, share=1)
        execute()
        execute()
        self.assertFalse(frappe.db.exists("DocShare", inaccessible.name))
        self.assertFalse(frappe.db.exists("DocShare", everyone.name))
        assigned.reload()
        everyone_global.reload()
        for share in (assigned, everyone_global):
            self.assertTrue(share.read)
            self.assertFalse(share.write)
            self.assertFalse(share.share)
        manager.reload()
        self.assertTrue(manager.write)
        self.assertTrue(frappe.db.exists("DocShare", other_app.name))
        with self.as_user(self.investor.name):
            self.assertNotIn(self.other.name, self.visible_portfolios())
            self.assertIn(self.assigned.name, self.visible_portfolios())
            with self.assertRaises(frappe.PermissionError):
                client_get("Bond Portfolio", self.other.name)

    def test_legacy_orphan_shares_do_not_break_migration_or_safe_rerun(self):
        orphan = frappe._dict(doctype="Bond Statement", name=unique_name("missing-statement"))
        share = self.legacy_share(orphan, self.investor.name)
        unrelated_orphan = self.legacy_share(
            frappe._dict(doctype="User", name=unique_name("missing-user")), self.investor.name
        )
        execute()
        execute()
        self.assertFalse(frappe.db.exists("DocShare", share.name))
        self.assertTrue(frappe.db.exists("DocShare", unrelated_orphan.name))

    def test_cleanup_invalidates_cached_share_after_removing_write_permissions(self):
        share = self.legacy_share(self.assigned, self.investor.name, write=1, share=1)
        self.assertTrue(frappe.get_cached_doc("DocShare", share.name).write)
        execute()
        updated = frappe.get_cached_doc("DocShare", share.name)
        self.assertTrue(updated.read)
        self.assertFalse(updated.write)
        self.assertFalse(updated.share)

    def test_assignment_cleanup_and_compatible_grant_lock_target_before_recipient(self):
        share = add_docshare("Bond Portfolio", self.assigned.name, self.investor.name)
        events = []
        lock_target = investor_shares._lock_share_target
        lock_users = investor_shares._lock_users

        def trace_target(*args, **kwargs):
            events.append("target")
            return lock_target(*args, **kwargs)

        def trace_users(*args, **kwargs):
            events.append("recipient")
            return lock_users(*args, **kwargs)

        with (
            patch.object(investor_shares, "_lock_share_target", side_effect=trace_target),
            patch.object(investor_shares, "_lock_users", side_effect=trace_users),
        ):
            self.assignment.save(ignore_permissions=True)
            assignment_events = events.copy()
            events.clear()
            add_docshare("Bond Portfolio", self.assigned.name, self.investor.name)
            grant_events = events.copy()

        expected_order = ["target", "recipient", "target", "recipient"]
        self.assertEqual(assignment_events, expected_order)
        self.assertEqual(grant_events, expected_order)
        self.assertTrue(frappe.db.exists("DocShare", share.name))

    def test_cleanup_handles_a_compatible_grant_committed_after_target_discovery(self):
        add_grant = add_docshare
        lock_users = investor_shares._lock_users
        grant_created = False

        def grant_before_recipient_lock(users):
            nonlocal grant_created
            if not grant_created:
                grant_created = True
                add_grant("Bond Portfolio", self.assigned.name, self.investor.name)
            lock_users(users)

        with patch.object(investor_shares, "_lock_users", side_effect=grant_before_recipient_lock):
            investor_shares.cleanup_incompatible_shares(user=self.investor.name)

        self.assertTrue(grant_created)
        self.assertTrue(
            frappe.db.exists(
                "DocShare",
                {
                    "share_doctype": "Bond Portfolio",
                    "share_name": self.assigned.name,
                    "user": self.investor.name,
                },
            )
        )

    def test_locked_target_created_after_snapshot_is_retried_without_deleting_share(self):
        lock_users = investor_shares._lock_users
        lock_target = investor_shares._lock_share_target
        original_get_value = frappe.db.get_value
        created = {}
        stale_reads = []

        def create_target_after_discovery(users):
            if not created:
                target = make_bond()
                created["target"] = target
                created["share"] = self.legacy_share(target, self.manager.name)
            lock_users(users)

        def timeout_locked_target(doctype, name, *, wait=True):
            if (
                not wait
                and created
                and (doctype, name)
                == (
                    created["target"].doctype,
                    created["target"].name,
                )
            ):
                raise frappe.QueryTimeoutError
            return lock_target(doctype, name, wait=wait)

        def read_old_snapshot(doctype, name=None, fieldname=None, **kwargs):
            if (
                created
                and (doctype, name)
                == (
                    created["target"].doctype,
                    created["target"].name,
                )
                and not kwargs.get("for_update")
            ):
                stale_reads.append((doctype, name))
                return None
            return original_get_value(doctype, name, fieldname, **kwargs)

        with (
            patch.object(investor_shares, "_lock_users", side_effect=create_target_after_discovery),
            patch.object(investor_shares, "_lock_share_target", side_effect=timeout_locked_target),
            patch.object(frappe.db, "get_value", side_effect=read_old_snapshot),
            patch("frappe.enqueue") as enqueue,
        ):
            investor_shares.cleanup_incompatible_shares(user=self.manager.name)

        share = created["share"]
        self.assertTrue(frappe.db.exists("DocShare", share.name))
        self.assertEqual(stale_reads, [])
        enqueue.assert_called_once_with(
            investor_shares.cleanup_incompatible_shares,
            doctype=created["target"].doctype,
            name=created["target"].name,
            enqueue_after_commit=True,
        )

        # A fresh target-scoped pass keeps the compatible grant intact.
        investor_shares.cleanup_incompatible_shares(
            doctype=created["target"].doctype,
            name=created["target"].name,
        )
        self.assertTrue(frappe.db.exists("DocShare", share.name))

    def test_role_change_repairs_existing_shares(self):
        share = add_docshare("Bond Portfolio", self.other.name, self.manager.name, write=1)
        self.manager.append("roles", {"role": INVESTOR_ROLE})
        self.manager.save(ignore_permissions=True)
        self.assertFalse(frappe.db.exists("DocShare", share.name))
        with self.as_user(self.manager.name):
            self.assertNotIn(self.other.name, self.visible_portfolios())
            with self.assertRaises(frappe.PermissionError):
                read_doc("Bond Portfolio", self.other.name)

    def test_role_change_repair_uses_current_transaction_portfolio_for_list_access(self):
        frappe.get_doc(
            {
                "doctype": "User Permission",
                "user": self.manager.name,
                "allow": "Bond Portfolio",
                "for_value": self.assigned.name,
                "apply_to_all_doctypes": 1,
            }
        ).insert(ignore_permissions=True)
        transaction = make_transaction(make_bond(), self.assigned)
        share = add_docshare("Bond Transaction", transaction.name, self.manager.name)

        # Model a transaction moved by another request after this request's snapshot.
        frappe.db.set_value(
            "Bond Transaction", transaction.name, "portfolio_name", self.other.name, update_modified=False
        )
        stale_target = frappe._dict(
            doctype="Bond Transaction", name=transaction.name, portfolio_name=self.assigned.name
        )
        get_doc = frappe.get_doc

        def get_doc_with_stale_target(*args, **kwargs):
            doctype = args[0] if args else kwargs.get("doctype")
            name = args[1] if len(args) > 1 else kwargs.get("name")
            if doctype == "Bond Transaction" and name == transaction.name:
                return stale_target
            return get_doc(*args, **kwargs)

        self.manager.append("roles", {"role": INVESTOR_ROLE})
        with patch.object(frappe, "get_doc", side_effect=get_doc_with_stale_target):
            self.manager.save(ignore_permissions=True)

        self.assertFalse(frappe.db.exists("DocShare", share.name))
        with self.as_user(self.manager.name):
            visible_transactions = frappe.qb.get_query(
                "Bond Transaction", fields=["name"], ignore_permissions=False
            ).run(pluck=True)
            self.assertNotIn(transaction.name, visible_transactions)
            with self.assertRaises(frappe.PermissionError):
                frappe.get_doc("Bond Transaction", transaction.name).check_permission("read")

    def test_assignment_delete_revokes_share_list_and_direct_access(self):
        share = add_docshare("Bond Portfolio", self.assigned.name, self.investor.name)
        self.assignment.delete(ignore_permissions=True)
        self.assertFalse(frappe.db.exists("DocShare", share.name))
        with self.as_user(self.investor.name):
            self.assertNotIn(self.assigned.name, self.visible_portfolios())
            with self.assertRaises(frappe.PermissionError):
                read_doc("Bond Portfolio", self.assigned.name)

    def test_bulk_clear_endpoint_revokes_share_and_remains_safe_to_rerun(self):
        share = add_docshare("Bond Portfolio", self.assigned.name, self.investor.name)
        self.assertEqual(self.clear_portfolio_assignments(), 1)
        self.assertEqual(self.clear_portfolio_assignments(), 0)
        self.assertFalse(frappe.db.exists("DocShare", share.name))
        self.assertFalse(frappe.db.exists("User Permission", self.assignment.name))
        with self.as_user(self.investor.name):
            self.assertNotIn(self.assigned.name, self.visible_portfolios())
            with self.assertRaises(frappe.PermissionError):
                read_doc("Bond Portfolio", self.assigned.name)

    def test_bulk_clear_endpoint_keeps_core_system_manager_permission_boundary(self):
        share = add_docshare("Bond Portfolio", self.assigned.name, self.investor.name)
        with self.as_user(self.investor.name):
            with self.assertRaises(frappe.PermissionError):
                self.clear_portfolio_assignments()
        self.assertTrue(frappe.db.exists("DocShare", share.name))
        self.assertTrue(frappe.db.exists("User Permission", self.assignment.name))

    def test_assignment_update_revokes_prior_portfolio_share(self):
        share = add_docshare("Bond Portfolio", self.assigned.name, self.investor.name)
        self.assignment.for_value = self.other.name
        self.assignment.save(ignore_permissions=True)
        self.assertFalse(frappe.db.exists("DocShare", share.name))
        with self.as_user(self.investor.name):
            self.assertNotIn(self.assigned.name, self.visible_portfolios())
            self.assertIn(self.other.name, self.visible_portfolios())

    def test_assignment_user_change_revokes_previous_recipient_and_refreshes_permission_cache(self):
        next_investor = self.make_user([INVESTOR_ROLE])
        share = add_docshare("Bond Portfolio", self.assigned.name, self.investor.name)
        self.assertTrue(get_user_permissions(self.investor.name).get("Bond Portfolio"))
        self.assertFalse(get_user_permissions(next_investor.name).get("Bond Portfolio"))
        self.assignment.user = next_investor.name
        self.assignment.save(ignore_permissions=True)
        self.assertFalse(frappe.db.exists("DocShare", share.name))
        self.assertFalse(get_user_permissions(self.investor.name).get("Bond Portfolio"))
        self.assertTrue(get_user_permissions(next_investor.name).get("Bond Portfolio"))
        with self.as_user(self.investor.name):
            self.assertNotIn(self.assigned.name, self.visible_portfolios())
            with self.assertRaises(frappe.PermissionError):
                read_doc("Bond Portfolio", self.assigned.name)
        with self.as_user(next_investor.name):
            self.assertIn(self.assigned.name, self.visible_portfolios())
            self.assertEqual(read_doc("Bond Portfolio", self.assigned.name).name, self.assigned.name)

    def test_assignment_restricted_to_one_doctype_revokes_investor_portfolio_share(self):
        share = add_docshare("Bond Portfolio", self.assigned.name, self.investor.name)
        self.assignment.apply_to_all_doctypes = 0
        self.assignment.applicable_for = "Bond Portfolio"
        self.assignment.save(ignore_permissions=True)
        self.assertFalse(frappe.db.exists("DocShare", share.name))
        with self.as_user(self.investor.name):
            self.assertNotIn(self.assigned.name, self.visible_portfolios())
            with self.assertRaises(frappe.PermissionError):
                read_doc("Bond Portfolio", self.assigned.name)

    def test_statement_portfolio_change_revokes_prior_share(self):
        statement = make_statement(self.assigned)
        share = add_docshare("Bond Statement", statement.name, self.investor.name)
        # The factory skips PDF parsing; real administrative reassignment still
        # reaches the normal save hooks and must revoke the old recipient.
        statement.portfolio_name = self.other.name
        statement.save()
        self.assertFalse(frappe.db.exists("DocShare", share.name))
        with self.as_user(self.investor.name):
            visible = frappe.qb.get_query("Bond Statement", fields=["name"], ignore_permissions=False).run(
                pluck=True
            )
            self.assertNotIn(statement.name, visible)
            with self.assertRaises(frappe.PermissionError):
                read_doc("Bond Statement", statement.name)

    def test_transaction_portfolio_change_revokes_prior_share(self):
        transaction = make_transaction(make_bond(), self.assigned)
        share = add_docshare("Bond Transaction", transaction.name, self.investor.name)
        transaction.portfolio_name = self.other.name
        transaction.save()
        self.assertFalse(frappe.db.exists("DocShare", share.name))
        with self.as_user(self.investor.name):
            visible = frappe.qb.get_query("Bond Transaction", fields=["name"], ignore_permissions=False).run(
                pluck=True
            )
            self.assertNotIn(transaction.name, visible)
            with self.assertRaises(frappe.PermissionError):
                read_doc("Bond Transaction", transaction.name)

    def test_direct_document_read_still_rejects_a_conflicting_legacy_share(self):
        self.legacy_share(self.other, self.investor.name)
        with self.as_user(self.investor.name):
            with self.assertRaises(frappe.PermissionError):
                client_get("Bond Portfolio", self.other.name)
            with self.assertRaises(frappe.PermissionError):
                read_doc("Bond Portfolio", self.other.name)

    def test_financial_mutations_reject_shares_even_with_an_additional_manager_role(self):
        self.investor.append("roles", {"role": BOND_MANAGER_ROLE})
        self.investor.save(ignore_permissions=True)
        bond = make_bond()
        documents = (
            self.assigned,
            make_transaction(bond, self.assigned),
            make_statement(self.assigned),
            bond,
            make_market_date(bond),
            make_exchange_rate(),
        )
        self.assertEqual({doc.doctype for doc in documents}, set(FINANCIAL_DOCTYPES))
        for document in documents:
            with self.subTest(doctype=document.doctype):
                share = self.legacy_share(document, self.investor.name, write=1)
                with self.as_user(self.investor.name):
                    self.assertFalse(document.has_permission("write"))
                    with self.assertRaises(frappe.PermissionError):
                        document.save(ignore_permissions=True)
                    with self.assertRaises(frappe.PermissionError):
                        document.delete(ignore_permissions=True)
                    new_document = frappe.new_doc(document.doctype)
                    with self.assertRaises(frappe.PermissionError):
                        new_document.insert(ignore_permissions=True)
                frappe.delete_doc("DocShare", share.name, ignore_permissions=True)

    def test_stale_role_cache_cannot_restore_manager_access_for_an_investor(self):
        self.investor.append("roles", {"role": BOND_MANAGER_ROLE})
        self.investor.save(ignore_permissions=True)
        self.legacy_share(self.assigned, self.investor.name, write=1)
        try:
            # A role cache refilled before a concurrent role save commits can
            # retain the prior manager roles after the investor role is saved.
            frappe.cache.hset("roles", self.investor.name, [BOND_MANAGER_ROLE, "All"])
            with self.as_user(self.investor.name):
                self.assertNotIn(self.other.name, self.visible_portfolios())
                with self.assertRaises(frappe.PermissionError):
                    read_doc("Bond Portfolio", self.other.name)
                with self.assertRaises(frappe.PermissionError):
                    self.assigned.save(ignore_permissions=True)
        finally:
            frappe.clear_cache(user=self.investor.name)

    def test_standard_client_update_cannot_use_a_legacy_write_share(self):
        self.legacy_share(self.assigned, self.investor.name, write=1)
        with self.as_user(self.investor.name):
            with self.assertRaises(frappe.PermissionError):
                set_value("Bond Portfolio", self.assigned.name, "account_no", "changed")
        self.assigned.reload()
        self.assertNotEqual(self.assigned.account_no, "changed")

    def test_fresh_install_bootstrap_runs_the_same_rerunnable_cleanup(self):
        path = "bond_management.patches.enforce_investor_share_boundary.execute"
        self.assertIn(path, hooks.after_install)
        share = self.legacy_share(self.other, self.investor.name)
        frappe.get_attr(path)()
        frappe.get_attr(path)()
        self.assertFalse(frappe.db.exists("DocShare", share.name))

    def clear_portfolio_assignments(self):
        original = "frappe.core.doctype.user_permission.user_permission.clear_user_permissions"
        path = frappe.override_whitelisted_method(original)
        self.assertEqual(path, "bond_management.bond_management.utils.investor_shares.clear_user_permissions")
        return frappe.get_attr(path)(user=self.investor.name, for_doctype="Bond Portfolio")

    def visible_portfolios(self):
        return frappe.qb.get_query("Bond Portfolio", fields=["name"], ignore_permissions=False).run(
            pluck=True
        )

    def legacy_share(self, document, user=None, **permissions):
        # db_insert deliberately bypasses hooks to represent pre-upgrade rows.
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

    def make_user(self, roles):
        return frappe.get_doc(
            {
                "doctype": "User",
                "email": f"{unique_name('share-user').lower()}@example.com",
                "first_name": "Share Test",
                "send_welcome_email": 0,
                "roles": [{"role": role} for role in roles],
            }
        ).insert(ignore_permissions=True)

    @contextmanager
    def as_user(self, user):
        previous = frappe.session.user
        try:
            frappe.set_user(user)
            yield
        finally:
            frappe.set_user(previous)
