"""Opt-in, disposable-bench verification of real share authorization races.

Run seed() and run() in separate `bench --site bond-management-test.localhost execute` calls so
the framework commits fixtures before the independent request connections.
Require BOND_SHARE_RACE_BENCH, BOND_SHARE_RACE_TOKEN (12 lowercase hex digits),
BOND_SHARE_LOCK_SOCKET and BOND_SHARE_LOCK_USER in the private environment.
BOND_SHARE_LOCK_PASSWORD is optional. The observer needs PROCESS privileges;
it reads information_schema and InnoDB lock diagnostics only. Fixtures remain for inspection.
"""

import os
import re
import tempfile
from contextvars import Context
from pathlib import Path
from threading import Event, Thread
from time import monotonic

import frappe
import pymysql
from frappe.core.doctype.user_permission.user_permission import get_user_permissions
from frappe.share import add_docshare

from bond_management.bond_management.utils.investor_permissions import (
    BOND_MANAGER_ROLE,
    INVESTOR_ROLE,
    _get_allowed_portfolios,
    is_investor_user,
)


def seed():
    """Create owned fixtures; bench execute owns the successful commit."""
    _guard()
    names = _names()
    for doctype, name in (
        ("Bond Portfolio", names["portfolio"]),
        *(("User", names[key]) for key in ("investor", "manager")),
    ):
        if frappe.db.exists(doctype, name):
            raise AssertionError("Use a new race token: fixture names already exist")
    frappe.get_doc(
        doctype="Bond Portfolio", portfolio_name=names["portfolio"], account_no=names["portfolio"]
    ).insert()
    for key, role in (("investor", INVESTOR_ROLE), ("manager", BOND_MANAGER_ROLE)):
        frappe.get_doc(
            doctype="User",
            email=names[key],
            first_name="Share race",
            send_welcome_email=0,
            roles=[{"role": role}],
        ).insert()
    frappe.get_doc(
        doctype="User Permission",
        user=names["investor"],
        allow="Bond Portfolio",
        for_value=names["portfolio"],
        apply_to_all_doctypes=1,
    ).insert()
    return names


def run():
    """Simulate two ordinary request transactions per race, without core mocks."""
    _guard()
    names = _names()
    _assert_seeded(names)
    sites_path = str(Path(frappe.local.sites_path).resolve())
    with pymysql.connect(
        unix_socket=_required("BOND_SHARE_LOCK_SOCKET"),
        user=_required("BOND_SHARE_LOCK_USER"),
        password=os.environ.get("BOND_SHARE_LOCK_PASSWORD", ""),
        autocommit=True,
        connect_timeout=5,
        read_timeout=5,
    ) as observer:
        results = [Race(kind, names, sites_path).run(observer) for kind in ("assignment", "role")]
    return {"races": results, "fixtures": names}


class Race:
    def __init__(self, kind, names, sites_path):
        self.kind, self.names, self.sites_path = kind, names, sites_path
        self.user = names["investor" if kind == "assignment" else "manager"]
        self.warmed, self.changed, self.release = Event(), Event(), Event()
        self.errors, self.connections = [], {}
        self.denied = False
        self.conflict = False
        self.lock_table = f"`{frappe.conf.db_name}`.`tabUser`"

    def run(self, observer):
        workers = [
            Thread(target=self.request, args=(name,), daemon=True, context=Context())
            for name in ("grant", "writer")
        ]
        for worker in workers:
            worker.start()
        try:
            self.wait(self.changed, "authorization change")
            observation = self.observe_wait(observer)
        finally:
            self.release.set()
            for worker in workers:
                worker.join(timeout=20)
        if any(worker.is_alive() for worker in workers):
            raise AssertionError("Race workers did not terminate")
        if self.errors:
            raise AssertionError(f"{self.kind} race worker failed") from self.errors[0]
        if self.conflict:
            # Frappe rolls conflicts back; simulate a caller retry in a fresh transaction.
            frappe.db.rollback()  # nosemgrep: bond-management-no-manual-transaction-boundary
            try:
                add_docshare("Bond Portfolio", self.names["portfolio"], self.user)
            except frappe.PermissionError:
                self.denied = True
            finally:
                frappe.db.rollback()  # nosemgrep: bond-management-no-manual-transaction-boundary
        if not self.denied:
            raise AssertionError("Grant succeeded after authorization changed")
        # The CLI connection may retain an old snapshot; inspect current state.
        share = frappe.qb.get_query(
            "DocShare",
            fields=["name"],
            filters={
                "share_doctype": "Bond Portfolio",
                "share_name": self.names["portfolio"],
                "user": self.user,
            },
            ignore_permissions=True,
            for_update=True,
        ).run(pluck=True)
        # This disposable request harness owns its outer transaction.
        frappe.db.rollback()  # nosemgrep: bond-management-no-manual-transaction-boundary
        if share:
            raise AssertionError("Conflicting share survived the race")
        return {
            "kind": self.kind,
            "user_lock_wait_observed": True,
            "observation": observation,
            "conflict_then_retry": self.conflict,
            "denied": True,
            "shares": 0,
        }

    def request(self, name):
        try:
            frappe.init("bond-management-test.localhost", sites_path=self.sites_path, force=True)
            frappe.connect()
            _guard()
            frappe.db.sql("SET SESSION TRANSACTION ISOLATION LEVEL REPEATABLE READ")
            frappe.db.sql("SET SESSION innodb_lock_wait_timeout = 15")
            self.connections[name] = frappe.db.sql("SELECT CONNECTION_ID()")[0][0]
            frappe.db.begin()
            if name == "grant":
                self.grant()
            else:
                self.write()
            # These workers are the outer request harness, never business code.
            if name == "grant" and (self.denied or self.conflict):
                frappe.db.rollback()  # nosemgrep: bond-management-no-manual-transaction-boundary
            else:
                frappe.db.commit()  # nosemgrep: bond-management-no-manual-transaction-boundary
        except BaseException as error:
            self.errors.append(error)
            if getattr(frappe.local, "db", None):
                frappe.db.rollback()  # nosemgrep: bond-management-no-manual-transaction-boundary
            self.changed.set()
        finally:
            frappe.destroy()

    def grant(self):
        self.warm_old_authorization()
        self.warmed.set()
        self.wait(self.changed, "writer mutation")
        # Refill caches while the writer is uncommitted, using the old snapshot.
        self.warm_old_authorization()
        try:
            add_docshare("Bond Portfolio", self.names["portfolio"], self.user)
        except frappe.PermissionError:
            self.denied = True
        except frappe.QueryDeadlockError:
            self.conflict = True

    def write(self):
        self.wait(self.warmed, "old repeatable-read snapshot")
        if self.kind == "assignment":
            assignment = frappe.db.get_value(
                "User Permission",
                {
                    "user": self.user,
                    "allow": "Bond Portfolio",
                    "for_value": self.names["portfolio"],
                },
            )
            if not assignment:
                raise AssertionError("Missing assignment fixture")
            frappe.delete_doc("User Permission", assignment)
        else:
            user = frappe.get_doc("User", self.user)
            user.append("roles", {"role": INVESTOR_ROLE})
            user.save()
        self.changed.set()
        self.wait(self.release, "observed User lock wait")

    def warm_old_authorization(self):
        portfolios = _get_allowed_portfolios(self.user)
        roles = frappe.get_roles(self.user)
        permissions = get_user_permissions(self.user)
        if self.kind == "assignment":
            cached = [permission.doc for permission in permissions.get("Bond Portfolio", [])]
            if portfolios != [self.names["portfolio"]] or cached != portfolios or INVESTOR_ROLE not in roles:
                raise AssertionError("Grant did not retain its old assignment snapshot")
        elif portfolios is not None or is_investor_user(self.user) or INVESTOR_ROLE in roles:
            raise AssertionError("Grant did not retain its old non-investor snapshot")

    def observe_wait(self, observer):
        deadline = monotonic() + 10
        while monotonic() < deadline:
            if self.errors:
                raise AssertionError("Worker failed before lock observation") from self.errors[0]
            if "grant" in self.connections and "writer" in self.connections:
                with observer.cursor() as cursor:
                    cursor.execute(
                        """SELECT 1 FROM information_schema.INNODB_LOCK_WAITS w
                        JOIN information_schema.INNODB_TRX r ON r.trx_id=w.requesting_trx_id
                        JOIN information_schema.INNODB_TRX b ON b.trx_id=w.blocking_trx_id
                        JOIN information_schema.INNODB_LOCKS l ON l.lock_id=w.requested_lock_id
                        WHERE r.trx_mysql_thread_id=%s AND b.trx_mysql_thread_id=%s
                        AND l.lock_table=%s AND l.lock_index='PRIMARY'""",
                        (self.connections["grant"], self.connections["writer"], self.lock_table),
                    )
                    if cursor.fetchone():
                        return "lock_views"
                if self.engine_has_user_wait(observer):
                    return "innodb_status"
            # Poll database evidence; elapsed time never proves a wait.
            self.release.wait(0.05)
        raise AssertionError("Did not observe the grant waiting on the writer's User lock")

    def engine_has_user_wait(self, observer):
        # MariaDB may omit optimizer-time record waits from INNODB_LOCK_WAITS.
        # InnoDB's transaction block still identifies the pending primary lock.
        with observer.cursor() as cursor:
            cursor.execute("SHOW ENGINE INNODB STATUS")
            status = cursor.fetchone()[2]
        for block in re.split(r"(?=---TRANSACTION)", status):
            if f"MariaDB thread id {self.connections['grant']}," not in block:
                continue
            return (
                "LOCK WAIT" in block
                and "index PRIMARY" in block
                and self.lock_table.casefold() in block.casefold()
                and f"'{self.user}'" in block
                and not self.release.is_set()
            )
        return False

    @staticmethod
    def wait(event, description):
        if not event.wait(15):
            raise AssertionError(f"Timed out waiting for {description}")


def _guard():
    expected = Path(_required("BOND_SHARE_RACE_BENCH")).resolve()
    actual = Path(frappe.local.sites_path).resolve().parent
    temporary_roots = (Path(tempfile.gettempdir()).resolve(), Path("/tmp").resolve())
    if expected != actual or not any(actual.is_relative_to(root) for root in temporary_roots):
        raise AssertionError("Run only in the explicitly opted-in disposable temporary bench")
    if (
        frappe.local.site != "bond-management-test.localhost"
        or frappe.session.user != "Administrator"
        or not frappe.conf.allow_tests
    ):
        raise AssertionError(
            "Requires Administrator on opted-in bond-management-test.localhost with allow_tests"
        )
    _names()


def _names():
    token = _required("BOND_SHARE_RACE_TOKEN")
    if not re.fullmatch(r"[a-f0-9]{12}", token):
        raise AssertionError("BOND_SHARE_RACE_TOKEN must contain 12 lowercase hex digits")
    return {
        "portfolio": f"SHARE-RACE-{token}",
        "investor": f"share-race-{token}-investor@example.com",
        "manager": f"share-race-{token}-manager@example.com",
    }


def _assert_seeded(names):
    portfolio = frappe.get_doc("Bond Portfolio", names["portfolio"])
    if portfolio.account_no != names["portfolio"]:
        raise AssertionError("Unowned portfolio fixture")
    for key in ("investor", "manager"):
        if frappe.get_doc("User", names[key]).first_name != "Share race":
            raise AssertionError("Unowned user fixture")
    if _get_allowed_portfolios(names["investor"]) != [names["portfolio"]] or is_investor_user(
        names["manager"]
    ):
        raise AssertionError("Seed fixtures in a separate invocation with a new token")


def _required(name):
    value = os.environ.get(name)
    if not value:
        raise AssertionError(f"Private environment variable {name} is required")
    return value
