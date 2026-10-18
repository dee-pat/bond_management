"""Two-connection regressions for committed attachments outside a mover's snapshot."""

from unittest.mock import Mock, patch

import frappe
from frappe.share import add_docshare
from frappe.tests import IntegrationTestCase

from bond_management.bond_management.tests.factories import (
    allow_user,
    make_bond,
    make_portfolio,
    make_private_file,
    make_transaction,
    make_user,
)
from bond_management.bond_management.utils.investor_permissions import INVESTOR_ROLE
from bond_management.bond_management.utils.investor_shares import retry_file_share_cleanup


class TestInvestorAttachmentConcurrency(IntegrationTestCase):
    def test_portfolio_move_discovers_attachment_committed_after_snapshot(self):
        self.assert_portfolio_move_after_snapshot(strict_snapshot=False)

    def test_strict_snapshot_conflict_requires_retry_before_portfolio_move(self):
        self.assert_portfolio_move_after_snapshot(strict_snapshot=True)

    def assert_portfolio_move_after_snapshot(self, *, strict_snapshot):
        owned = []

        def own(doc):
            owned.append((doc.doctype, doc.name))
            return doc

        # Initialize both framework connections before starting the mover's snapshot.
        with self.secondary_connection():
            pass
        with self.primary_connection():
            isolation, snapshot_isolation = frappe.db.sql(
                "SELECT @@transaction_isolation, @@innodb_snapshot_isolation"
            )[0]
        try:
            with self.primary_connection():
                assigned = own(make_portfolio())
                other = own(make_portfolio())
                investor = own(make_user([INVESTOR_ROLE]))
                own(allow_user(investor.name, "Bond Portfolio", assigned.name))
                bond = own(make_bond())
                transaction = own(make_transaction(bond, assigned))
                # The harness owns these transaction boundaries, not app services.
                frappe.db.commit()  # nosemgrep: frappe-kit-no-manual-transaction-boundary, frappe-manual-commit
                frappe.db.sql("SET SESSION TRANSACTION ISOLATION LEVEL REPEATABLE READ")
                frappe.db.sql("SET SESSION innodb_snapshot_isolation = %s", (int(strict_snapshot),))
                mover_id = frappe.db.sql("SELECT CONNECTION_ID()")[0][0]
                transaction.reload()
                self.assertFalse(frappe.db.exists("File", {"attached_to_name": transaction.name}))

            with self.secondary_connection():
                self.assertNotEqual(mover_id, frappe.db.sql("SELECT CONNECTION_ID()")[0][0])
                attachment = own(make_private_file("Bond Transaction", transaction.name))
                share = own(add_docshare("File", attachment.name, investor.name))
                self.assertTrue(share.read)
                frappe.db.commit()  # nosemgrep: frappe-kit-no-manual-transaction-boundary, frappe-manual-commit

            with self.primary_connection():
                # Prove the snapshot predates the attachment, without mocking any reads.
                self.assertFalse(frappe.db.exists("File", attachment.name))
                transaction.portfolio_name = other.name
                if strict_snapshot:
                    with self.assertRaises(frappe.QueryDeadlockError) as conflict:
                        transaction.save()
                    self.assertEqual(conflict.exception.__cause__.args[0], 1020)
                    # Match Frappe's request conflict recovery, without swallowing it in services.
                    frappe.db.rollback()  # nosemgrep: frappe-kit-no-manual-transaction-boundary, frappe-manual-commit
                    transaction.reload()
                    self.assertEqual(transaction.portfolio_name, assigned.name)
                    transaction.portfolio_name = other.name
                # Keep real enqueue/after_commit behavior; substitute only the external queue.
                queue = Mock(count=0)
                with patch("frappe.utils.background_jobs.get_queue", return_value=queue):
                    transaction.save()
                    queue.enqueue_call.assert_not_called()
                    frappe.db.commit()  # nosemgrep: frappe-kit-no-manual-transaction-boundary, frappe-manual-commit
                self.assertEqual(queue.enqueue_call.call_count, 0 if strict_snapshot else 1)

            with self.secondary_connection():
                for call in queue.enqueue_call.call_args_list:
                    job = call.kwargs["kwargs"]
                    self.assertIs(job["method"], retry_file_share_cleanup)
                    job["method"](**job["kwargs"])
                frappe.db.commit()  # nosemgrep: frappe-kit-no-manual-transaction-boundary, frappe-manual-commit
                self.assertEqual(
                    frappe.db.get_value("Bond Transaction", transaction.name, "portfolio_name"), other.name
                )
                self.assertFalse(frappe.db.exists("DocShare", share.name))
                with self.set_user(investor.name):
                    visible = frappe.qb.get_query("File", fields=["name"], ignore_permissions=False).run(
                        pluck=True
                    )
                self.assertNotIn(attachment.name, visible)
        finally:
            # Roll back failed requests before deleting only this test's committed fixtures.
            self._rollback_connections()
            with self.primary_connection():
                frappe.db.sql("SET SESSION innodb_snapshot_isolation = %s", (snapshot_isolation,))
                frappe.db.sql("SET SESSION transaction_isolation = %s", (isolation,))
                for doctype, name in reversed(owned):
                    if frappe.db.exists(doctype, name):
                        frappe.delete_doc(doctype, name, ignore_permissions=True)
                frappe.db.commit()  # nosemgrep: frappe-kit-no-manual-transaction-boundary, frappe-manual-commit
            frappe.local.db = self._primary_connection
