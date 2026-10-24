"""Persisted business and bootstrap assertions for the migration lifecycle."""

from decimal import Decimal

import frappe

from bond_management.bond_management.tests.migration_lifecycle_fixtures import USD_ISIN
from bond_management.patches import add_bond_query_indexes as indexes
from bond_management.patches.add_bond_investor_read_only_access import READ_ONLY_DOCTYPES
from bond_management.patches.add_bond_management_manager_access import BOND_DOCTYPES


def assert_indexes():
    expected = {
        "Bond Transaction": {
            indexes.LEDGER_INDEX: (["portfolio_name", "isin", "settlement_date"], 1),
            indexes.REPORT_INDEX: (["portfolio_name", "settlement_date", "isin"], 1),
        },
        "Bond Market Date": {indexes.MARKET_DATE_UNIQUE: (["date"], 0)},
        "Bond Statement": {indexes.STATEMENT_ATTACHMENT_UNIQUE: (["attachment"], 0)},
        "Bond Exchange Rate": {
            indexes.EXCHANGE_RATE_UNIQUE: (["rate_date", "from_currency", "to_currency"], 0)
        },
        "Bond Exchange Rate Source": {
            indexes.EXCHANGE_RATE_SOURCE_EXCHANGE_RATE_INDEX: (["exchange_rate"], 1),
            indexes.EXCHANGE_RATE_SOURCE_STATEMENT_INDEX: (["statement"], 1),
        },
    }
    for doctype, table_indexes in expected.items():
        # information_schema is outside the DocType query abstraction.
        rows = frappe.db.sql(
            """SELECT INDEX_NAME AS Key_name, COLUMN_NAME AS Column_name,
            SEQ_IN_INDEX AS Seq_in_index, NON_UNIQUE AS Non_unique
            FROM information_schema.STATISTICS
            WHERE TABLE_SCHEMA = %s AND TABLE_NAME = %s""",
            (frappe.conf.db_name, "tab" + doctype),
            as_dict=True,
        )
        for name, (columns, non_unique) in table_indexes.items():
            matching = sorted((row for row in rows if row.Key_name == name), key=lambda row: row.Seq_in_index)
            assert [row.Column_name for row in matching] == columns, (doctype, name, matching)
            assert all(row.Non_unique == non_unique for row in matching), (doctype, name)


def assert_permissions():
    for doctype in READ_ONLY_DOCTYPES:
        row = frappe.db.get_value(
            "DocPerm",
            {"parent": doctype, "role": "Bond Investor Read Only", "permlevel": 0},
            ["read", "write", "create", "delete"],
        )
        assert row == (1, 0, 0, 0), (doctype, row)
    for doctype in BOND_DOCTYPES:
        row = frappe.db.get_value(
            "DocPerm",
            {"parent": doctype, "role": "Bond Management Manager", "permlevel": 0},
            ["read", "write", "create", "delete"],
        )
        assert row == (1, 1, 1, 1), (doctype, row)
    for report in (
        "Portfolio Performance",
        "Bond Yield Comparison",
        "Interest Difference by Portfolio",
    ):
        roles = {
            row["role"] for row in _rows("Has Role", ["role"], {"parent": report, "parenttype": "Report"})
        }
        assert {"Bond Investor Read Only", "Bond Management Manager"} <= roles, (report, roles)


def assert_business_data(fixtures):
    _assert_share_cleanup(fixtures["shares"])
    transaction = frappe.get_doc("Bond Transaction", fixtures["transaction"])
    for field, expected in {
        "quantity_face_value": "10",
        "face_value_per_unit": "100",
        "price": "105",
        "principal": "1050",
        "accrued_interest_paid": "1",
        "commission_amount": "20",
        "settlement_amount": "1051",
        "transaction_amount": "1031",
    }.items():
        assert Decimal(str(transaction.get(field))) == Decimal(expected), (field, transaction.get(field))
    assert transaction.isin == USD_ISIN
    rate = frappe.get_doc("Bond Exchange Rate", fixtures["exchange_rate"])
    assert Decimal(str(rate.rate)) == Decimal("0.008") and Decimal(str(rate.reverse_rate)) == Decimal("125")
    assert rate.manual_fallback == 0 and rate.statement == fixtures["statement"]
    sources = _rows(
        "Bond Exchange Rate Source", ["statement", "rate", "reverse_rate"], {"exchange_rate": rate.name}
    )
    assert len(sources) == 1 and sources[0]["statement"] == fixtures["statement"]
    assert Decimal(str(sources[0]["rate"])) == Decimal("0.008")
    assert Decimal(str(sources[0]["reverse_rate"])) == Decimal("125")
    manual = frappe.get_doc("Bond Exchange Rate", fixtures["manual_exchange_rate"])
    assert manual.manual_fallback == 1 and not manual.statement


def _assert_share_cleanup(shares):
    remaining = _rows("DocShare", ["name"], {"name": ["in", shares["removed"]]})
    assert not remaining, ("Financial shares survived migration", remaining)
    for expected in shares["kept"]:
        actual = frappe.db.get_value("DocShare", expected["name"], list(expected), as_dict=True)
        assert actual == expected, ("Unrelated share changed", expected, actual)
    for expected in shares["files"]:
        file = frappe.get_doc("File", expected["name"])
        for field, value in expected.items():
            actual = file.get_content() if field == "content" else file.get(field)
            assert actual == value, ("File changed during share cleanup", file.name, field)


def _rows(doctype, fields, filters):
    # Every entry point enforces Administrator and an opted-in temporary site first.
    return frappe.qb.get_query(
        doctype, fields=fields, filters=filters, order_by="name asc", ignore_permissions=True
    ).run(as_dict=True)
