from collections import defaultdict

import frappe
from frappe.utils import get_datetime

from bond_management.patches.add_bond_query_indexes import ensure_bond_query_indexes


def execute():
    """Keep the earliest statement for each attachment and remove later duplicates."""
    rows = frappe.qb.get_query(
        "Bond Statement",
        fields=["name", "attachment", "creation"],
        order_by="creation asc, name asc",
        ignore_permissions=True,
    ).run(as_dict=True)

    for statement_name in get_redundant_statement_names(rows):
        frappe.delete_doc(
            "Bond Statement",
            statement_name,
            ignore_permissions=True,
        )

    ensure_bond_query_indexes()


def get_redundant_statement_names(rows) -> list[str]:
    """Return every duplicate except the earliest statement for each attachment."""
    rows_by_attachment = defaultdict(list)
    for row in rows:
        if row.attachment:
            rows_by_attachment[row.attachment].append(row)

    redundant = []
    for attachment_rows in rows_by_attachment.values():
        attachment_rows.sort(key=lambda row: (get_datetime(row.creation), row.name))
        redundant.extend(row.name for row in attachment_rows[1:])
    return redundant
