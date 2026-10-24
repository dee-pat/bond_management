"""Opt-in CLI phases for a real, temporary-site install/migrate lifecycle.

Use bench execute for each phase, with actual bench migrate commands between
phases. This helper never invokes patch functions directly or creates a site.
"""

import json
from pathlib import Path

import frappe
from frappe.modules.patch_handler import get_patches_from_app

from bond_management.bond_management.tests.migration_lifecycle_assertions import (
    assert_business_data,
    assert_indexes,
    assert_permissions,
)
from bond_management.bond_management.tests.migration_lifecycle_fixtures import (
    USD_ISIN,
    prepare_legacy_rows,
)
from bond_management.bond_management.tests.temporary_site_guard import validate_temporary_site

OPT_IN = "bond_migration_lifecycle_test"
PREVIOUS_SHARE_PATCHES = tuple(
    f"bond_management.patches.{name}"
    for name in (
        "enforce_investor_share_boundary",
        "add_bond_exchange_rate_source_permission",
        "cleanup_incompatible_file_shares",
    )
)


def fresh():
    """Assert after_install invariants before the temporary site's first migrate."""
    state_path = _guard()
    if state_path.exists():
        raise RuntimeError("Lifecycle evidence already exists; use a new temporary lifecycle site.")
    assert_indexes()
    assert_permissions()
    patches = _patch_logs()
    assert len(patches) == len(get_patches_from_app("bond_management"))
    assert not frappe.db.count("Bond Master"), "fresh() requires an empty fresh installation"
    _write_state(state_path, {"phase": "fresh", "fresh_patch_logs": patches})
    return {"phase": "fresh", "registered_patches": len(patches), "indexes": "verified"}


def prepare():
    """Seed legacy data; requeue app patches except the already-complete share cleanups."""
    state_path = _guard()
    state = _read_state(state_path)
    assert state["phase"] == "fresh", "Run fresh() immediately after install-app first"
    state.update(phase="prepared", fixtures=prepare_legacy_rows())
    # Existing sites have already completed these wrappers. Replaying them
    # would hide a broken remove_financial_document_shares upgrade patch.
    _remove_app_patch_logs(keep=PREVIOUS_SHARE_PATCHES)
    _write_state(state_path, state)
    return {"phase": "prepared", "next": f"bench --site {frappe.local.site} migrate"}


def verify():
    """Assert migrated business data, then compare each rerun with its first result."""
    state_path = _guard()
    state = _read_state(state_path)
    assert state["phase"] in {"prepared", "verified", "requeued"}
    assert_indexes()
    assert_permissions()
    patch_logs = _patch_logs()
    if state["phase"] == "prepared":
        previous = [row for row in state["fresh_patch_logs"] if row["patch"] in PREVIOUS_SHARE_PATCHES]
        assert len(previous) == len(PREVIOUS_SHARE_PATCHES)
        assert [row for row in patch_logs if row["patch"] in PREVIOUS_SHARE_PATCHES] == previous, (
            "First migration reran an already-complete share cleanup patch"
        )
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
    return {"phase": "requeued", "next": f"bench --site {frappe.local.site} migrate"}


def validate_environment(*, bench_path, site_path, site, user, config):
    """Require an opted-in, uniquely named lifecycle site in the configured bench."""
    return validate_temporary_site(
        bench_path=bench_path,
        site_path=site_path,
        site=site,
        user=user,
        config=config,
        site_prefix="bond-management-lifecycle-",
        required_flags=(OPT_IN,),
    )


def _guard():
    bench = validate_environment(
        bench_path=Path(frappe.local.sites_path).resolve().parent,
        site_path=frappe.get_site_path(),
        site=frappe.local.site,
        user=frappe.session.user,
        config=frappe.conf,
    )
    # Each temporary site keeps its evidence separate beside the configured bench.
    return bench.parent / f"{frappe.local.site}-bond-migration-lifecycle.json"


def _patch_logs():
    patches = get_patches_from_app("bond_management")
    rows = _rows("Patch Log", ["name", "patch", "creation"], {"patch": ["in", patches]})
    assert sorted(row["patch"] for row in rows) == sorted(patches), "Registered Patch Logs incomplete"
    return json.loads(frappe.as_json(rows))


def _remove_app_patch_logs(*, keep=()):
    registered = get_patches_from_app("bond_management")
    assert set(keep) <= set(registered)
    patches = [patch for patch in registered if patch not in keep]
    assert patches and all(patch.startswith("bond_management.") for patch in patches)
    frappe.db.delete("Patch Log", {"patch": ["in", patches]})
    assert not frappe.db.count("Patch Log", {"patch": ["in", patches]})


def _snapshot(fixtures):
    documents = [("Bond Master", USD_ISIN)]
    documents.extend(
        (doctype, fixtures[key])
        for doctype, key in (
            ("Bond Transaction", "transaction"),
            ("Bond Statement", "statement"),
            ("Bond Exchange Rate", "exchange_rate"),
            ("Bond Exchange Rate", "manual_exchange_rate"),
        )
    )
    snapshot = {
        doctype + ":" + name: _business_fields(frappe.get_doc(doctype, name).as_dict())
        for doctype, name in documents
    }
    snapshot["sources"] = _rows(
        "Bond Exchange Rate Source",
        ["exchange_rate", "statement", "rate", "reverse_rate"],
        {"exchange_rate": ["in", [fixtures["exchange_rate"], fixtures["manual_exchange_rate"]]]},
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
    # Every entry point enforces Administrator and an opted-in temporary site first.
    return frappe.qb.get_query(
        doctype, fields=fields, filters=filters, order_by="name asc", ignore_permissions=True
    ).run(as_dict=True)


def _read_state(path):
    return json.loads(path.read_text())


def _write_state(path, state):
    path.write_text(frappe.as_json(state))
