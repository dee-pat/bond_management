"""Opt-in CLI phases for a real, disposable install/migrate lifecycle.

Use bench execute for each phase, with actual bench migrate commands between
phases. This helper never invokes patch functions directly or creates a site.
"""

import json
import tempfile
from pathlib import Path

import frappe
from frappe.modules.patch_handler import get_patches_from_app

from bond_management.bond_management.tests.migration_lifecycle_assertions import (
    assert_business_data,
    assert_indexes,
    assert_permissions,
)
from bond_management.bond_management.tests.migration_lifecycle_fixtures import (
    KENYA_ISIN,
    USD_ISIN,
    prepare_legacy_rows,
)

OPT_IN = "bond_migration_lifecycle_test"


def fresh():
    """Assert after_install invariants before the disposable site's first migrate."""
    state_path = _guard()
    if state_path.exists():
        raise RuntimeError("Lifecycle evidence already exists; use a new disposable bench.")
    assert_indexes()
    assert_permissions()
    patches = _patch_logs()
    assert len(patches) == len(get_patches_from_app("bond_management"))
    assert not frappe.db.count("Bond Master"), "fresh() requires an empty fresh installation"
    _write_state(state_path, {"phase": "fresh", "fresh_patch_logs": patches})
    return {"phase": "fresh", "registered_patches": len(patches), "indexes": "verified"}


def prepare():
    """Seed legacy data and requeue only this app's registered Patch Logs."""
    state_path = _guard()
    state = _read_state(state_path)
    assert state["phase"] == "fresh", "Run fresh() immediately after install-app first"
    state.update(phase="prepared", fixtures=prepare_legacy_rows())
    _remove_app_patch_logs()
    _write_state(state_path, state)
    return {"phase": "prepared", "next": "bench --site test_site migrate"}


def verify():
    """Assert migrated business data, then compare each rerun with its first result."""
    state_path = _guard()
    state = _read_state(state_path)
    assert state["phase"] in {"prepared", "verified", "requeued"}
    assert_indexes()
    assert_permissions()
    patch_logs = _patch_logs()
    assert_business_data(state["fixtures"])
    snapshot = _snapshot(state["fixtures"])
    if "snapshot" in state:
        assert snapshot == state["snapshot"], "Migration rerun changed financial or attachment data"
    if state["phase"] == "verified":
        assert patch_logs == state["patch_logs"], "Normal migrate reran already-complete patches"
    state.update(phase="verified", snapshot=snapshot, patch_logs=patch_logs)
    _write_state(state_path, state)
    return {"phase": "verified", "registered_patches": len(patch_logs), "snapshot": str(state_path)}


def requeue():
    """Force a second registered sequence; the caller runs the real bench migrate."""
    state_path = _guard()
    state = _read_state(state_path)
    assert state["phase"] == "verified", "Verify the first migrate before forcing a rerun"
    _remove_app_patch_logs()
    state["phase"] = "requeued"
    _write_state(state_path, state)
    return {"phase": "requeued", "next": "bench --site test_site migrate"}


def validate_environment(*, bench_path, site_path, site, user, config):
    """Resolve both bench and active site paths before permitting legacy mutation."""
    bench = Path(bench_path).resolve()
    temporary_roots = {Path(tempfile.gettempdir()).resolve(), Path("/tmp").resolve()}
    if not any(bench.is_relative_to(root) and bench != root for root in temporary_roots):
        raise RuntimeError("Lifecycle helper requires a disposable bench under a temporary directory")
    if Path(site_path).resolve() != bench / "sites" / "test_site" or site != "test_site":
        raise RuntimeError("Lifecycle helper requires the disposable bench's test_site")
    if user != "Administrator":
        raise RuntimeError("Lifecycle helper requires Administrator")
    if not _true(config.get("allow_tests")) or not _true(config.get(OPT_IN)):
        raise RuntimeError(f"Lifecycle helper requires allow_tests and explicit {OPT_IN}=true")
    return bench


def _guard():
    bench = validate_environment(
        bench_path=Path(frappe.local.sites_path).resolve().parent,
        site_path=frappe.get_site_path(),
        site=frappe.local.site,
        user=frappe.session.user,
        config=frappe.conf,
    )
    # Evidence belongs beside the disposable bench, outside the checkout/site config.
    return bench.parent / f"{bench.name}-bond-migration-lifecycle.json"


def _true(value):
    if isinstance(value, str):
        try:
            value = json.loads(value)
        except ValueError:
            return False
    return value is True or (type(value) is int and value == 1)


def _patch_logs():
    patches = get_patches_from_app("bond_management")
    rows = _rows("Patch Log", ["name", "patch", "creation"], {"patch": ["in", patches]})
    assert sorted(row["patch"] for row in rows) == sorted(patches), "Registered Patch Logs incomplete"
    return json.loads(frappe.as_json(rows))


def _remove_app_patch_logs():
    patches = get_patches_from_app("bond_management")
    assert patches and all(patch.startswith("bond_management.") for patch in patches)
    frappe.db.delete("Patch Log", {"patch": ["in", patches]})
    assert not frappe.db.count("Patch Log", {"patch": ["in", patches]})


def _snapshot(fixtures):
    documents = [("Bond Master", USD_ISIN), ("Bond Master", KENYA_ISIN)]
    documents.extend(
        (doctype, fixtures[key])
        for doctype, key in (
            ("Bond Transaction", "transaction"),
            ("Bond Statement", "statement"),
            ("Bond Market Date", "market_date"),
            ("Bond Exchange Rate", "exchange_rate"),
        )
    )
    snapshot = {
        doctype + ":" + name: _business_fields(frappe.get_doc(doctype, name).as_dict())
        for doctype, name in documents
    }
    snapshot["sources"] = _rows(
        "Bond Exchange Rate Source",
        ["exchange_rate", "statement", "rate", "reverse_rate"],
        {"exchange_rate": fixtures["exchange_rate"]},
    )
    snapshot["files"] = _rows(
        "File",
        [
            "file_url",
            "file_name",
            "is_private",
            "attached_to_doctype",
            "attached_to_name",
            "attached_to_field",
        ],
        {"attached_to_name": ["in", [fixtures["statement"], fixtures["transaction"]]]},
    )
    return json.loads(frappe.as_json(snapshot))


def _business_fields(value):
    if isinstance(value, dict):
        return {
            key: _business_fields(item)
            for key, item in value.items()
            if key
            not in {
                "name",
                "creation",
                "modified",
                "modified_by",
                "owner",
                "_liked_by",
                "_comments",
                "_assign",
                "_user_tags",
            }
        }
    if isinstance(value, list):
        return [_business_fields(item) for item in value]
    return value


def _rows(doctype, fields, filters):
    # Every entry point enforces Administrator and a disposable bench first.
    return frappe.qb.get_query(
        doctype, fields=fields, filters=filters, order_by="name asc", ignore_permissions=True
    ).run(as_dict=True)


def _read_state(path):
    return json.loads(path.read_text())


def _write_state(path, state):
    path.write_text(frappe.as_json(state))
