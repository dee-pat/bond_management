from dataclasses import dataclass
from decimal import Decimal

import frappe

from bond_management.bond_management.utils.financial import to_decimal
from bond_management.bond_management.utils.statement_pdf import ParsedMarketPrice


@dataclass(frozen=True)
class StatementQuantityMismatch:
    isin: str
    pdf_quantity: Decimal | None
    calculated_quantity: Decimal
    difference: Decimal


def reconcile_statement_quantities(
    parsed_rows: tuple[ParsedMarketPrice, ...],
    statement_rows,
) -> tuple[StatementQuantityMismatch, ...]:
    """Compare normalized PDF units with calculated statement ledger quantities."""
    parsed_isins = [row.isin for row in parsed_rows]
    bonds = (
        frappe.qb.get_query(
            "Bond Master",
            fields=["name", "face_value_per_unit"],
            filters={"name": ["in", parsed_isins]},
            ignore_permissions=False,
        ).run(as_dict=True)
        if parsed_isins
        else []
    )
    face_value_by_isin = {
        bond.name: to_decimal(bond.face_value_per_unit, "Face Value Per Unit")
        for bond in bonds
    }

    pdf_quantities = {}
    for row in parsed_rows:
        face_value_per_unit = face_value_by_isin.get(row.isin)
        if face_value_per_unit is None:
            continue
        if face_value_per_unit <= 0:
            frappe.throw(f"Face Value Per Unit for ISIN {frappe.bold(row.isin)} must be greater than zero")

        pdf_quantities[row.isin] = (
            row.reported_quantity / face_value_per_unit
            if row.quantity_is_face_value
            else row.reported_quantity
        )

    calculated_quantities = {
        row.isin: to_decimal(row.quantity, "Calculated Quantity") for row in statement_rows
    }
    mismatches = []
    for isin in sorted(set(pdf_quantities) | set(calculated_quantities)):
        pdf_quantity = pdf_quantities.get(isin)
        calculated_quantity = calculated_quantities.get(isin, Decimal("0"))
        if pdf_quantity is None or pdf_quantity != calculated_quantity:
            mismatches.append(
                StatementQuantityMismatch(
                    isin=isin,
                    pdf_quantity=pdf_quantity,
                    calculated_quantity=calculated_quantity,
                    difference=(
                        pdf_quantity - calculated_quantity
                        if pdf_quantity is not None
                        else -calculated_quantity
                    ),
                )
            )

    return tuple(mismatches)


def format_quantity(value: Decimal | None) -> str:
    if value is None:
        return "Not present"
    formatted = f"{value:,f}"
    return formatted.rstrip("0").rstrip(".") if "." in formatted else formatted
