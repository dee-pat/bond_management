from io import BytesIO

import frappe
from frappe.utils import escape_html, now_datetime
from pypdf import PdfWriter
from pypdf.generic import DecodedStreamObject, DictionaryObject, NameObject

from bond_management.bond_management.utils.statement_quantity_reconciliation import (
    StatementQuantityComparison,
    format_quantity,
)

REPORT_FILENAME_PREFIX = "Bond-Quantity-Reconciliation-"


def attach_quantity_reconciliation_report(statement, comparisons, *, file_name=None) -> str:
    """Create a private reconciliation PDF attached to a persisted Bond Statement."""
    if file_name:
        existing = frappe.qb.get_query(
            "File",
            fields=["file_url"],
            filters={
                "file_name": file_name,
                "attached_to_doctype": "Bond Statement",
                "attached_to_name": statement.name,
                "attached_to_field": "quantity_reconciliation_report",
            },
            limit=1,
            # The caller has already passed Bond Statement permission checks;
            # this system-generated child File lookup is only an idempotency
            # check for the report attached to that statement.
            ignore_permissions=True,
        ).run(pluck=True)
        if existing:
            return existing[0]

    generated_at = now_datetime()
    portfolio = frappe.get_doc("Bond Portfolio", statement.portfolio_name)
    portfolio.check_permission("read")
    password = portfolio.get_password("statement_pdf_password", raise_exception=False)
    if not password:
        frappe.throw(
            f"Configure Statement PDF Password on portfolio {frappe.bold(escape_html(statement.portfolio_name))} "
            "before saving its quantity reconciliation report."
        )
    content = build_quantity_reconciliation_pdf(
        statement_name=statement.name,
        portfolio_name=statement.portfolio_name,
        statement_date=str(statement.statement_date),
        generated_at=generated_at.strftime("%Y-%m-%d %H:%M:%S"),
        comparisons=tuple(comparisons),
        password=password,
    )
    file_doc = frappe.get_doc(
        {
            "doctype": "File",
            "file_name": file_name
            or (
                f"{REPORT_FILENAME_PREFIX}{statement.name}-"
                f"{generated_at.strftime('%Y%m%d-%H%M%S')}-{frappe.generate_hash(length=6)}.pdf"
            ),
            "attached_to_doctype": "Bond Statement",
            "attached_to_name": statement.name,
            "attached_to_field": "quantity_reconciliation_report",
            "content": content,
            "is_private": 1,
        }
    ).insert()
    return file_doc.file_url


def build_quantity_reconciliation_pdf(
    *,
    statement_name: str,
    portfolio_name: str,
    statement_date: str,
    generated_at: str,
    comparisons: tuple[StatementQuantityComparison, ...],
    password: str,
) -> bytes:
    """Build a compact text PDF that remains readable when the table spans pages."""
    writer = PdfWriter()
    regular_font = writer._add_object(_font("/Courier"))
    bold_font = writer._add_object(_font("/Courier-Bold"))
    mismatch_count = sum(not comparison.matches for comparison in comparisons)
    matched_count = len(comparisons) - mismatch_count
    status = "DISCREPANCIES FOUND" if mismatch_count else "MATCHED"
    first_page_lines = [
        ("Bond Quantity Reconciliation", "/FB", 15),
        ("", "/FR", 10),
        (f"Statement:  {statement_name}", "/FR", 10),
        (f"Portfolio:  {portfolio_name}", "/FR", 10),
        (f"Date:       {statement_date}", "/FR", 10),
        (f"Generated:  {generated_at}", "/FR", 10),
        (f"Status:     {status}", "/FB", 10),
        (f"Matched:    {matched_count}", "/FR", 10),
        (f"Mismatched: {mismatch_count}", "/FR", 10),
        ("", "/FR", 10),
    ]
    if comparisons:
        table_lines = [_table_header()]
        table_lines.extend(_table_row(comparison) for comparison in comparisons)
        if not mismatch_count:
            table_lines.insert(0, "No quantity discrepancies found.")
    else:
        table_lines = ["No comparable ISIN quantities found."]
    table_lines.append("")
    table_lines.append("Note: ISINs missing from Bond Master are excluded.")

    first_page_capacity = 50 - len(first_page_lines)
    page_chunks = [table_lines[:first_page_capacity]]
    remaining_lines = table_lines[first_page_capacity:]
    while remaining_lines:
        page_chunks.append(remaining_lines[:47])
        remaining_lines = remaining_lines[47:]

    for page_index, chunk in enumerate(page_chunks):
        lines = (
            list(first_page_lines)
            if page_index == 0
            else [
                ("Bond Quantity Reconciliation (continued)", "/FB", 13),
                ("", "/FR", 10),
                (_table_header(), "/FB", 9),
            ]
        )
        lines.extend(line if isinstance(line, tuple) else (line, "/FR", 9) for line in chunk)
        _add_text_page(writer, lines, regular_font, bold_font)

    writer.add_metadata({"/Title": f"Bond Quantity Reconciliation - {statement_name}"})
    writer.encrypt(password, algorithm="AES-256")
    output = BytesIO()
    writer.write(output)
    return output.getvalue()


def _font(base_font: str) -> DictionaryObject:
    return DictionaryObject(
        {
            NameObject("/Type"): NameObject("/Font"),
            NameObject("/Subtype"): NameObject("/Type1"),
            NameObject("/BaseFont"): NameObject(base_font),
        }
    )


def _add_text_page(writer, lines, regular_font, bold_font):
    page = writer.add_blank_page(width=595, height=842)
    page[NameObject("/Resources")] = DictionaryObject(
        {
            NameObject("/Font"): DictionaryObject(
                {
                    NameObject("/FR"): regular_font,
                    NameObject("/FB"): bold_font,
                }
            )
        }
    )

    commands = ["BT"]
    y = 800
    for text, font, size in lines:
        escaped = _escape_pdf_text(str(text))
        commands.append(f"{font} {size} Tf 1 0 0 1 36 {y} Tm ({escaped}) Tj")
        y -= 16 if size >= 13 else 14
    commands.append("ET")

    stream = DecodedStreamObject()
    stream.set_data("\n".join(commands).encode("latin-1", errors="replace"))
    page[NameObject("/Contents")] = writer._add_object(stream)


def _table_header() -> str:
    return f"{'ISIN':<14}{'PDF Quantity':>18}{'Calculated':>18}{'Difference':>18}{'Result':>12}"


def _table_row(comparison: StatementQuantityComparison) -> str:
    return (
        f"{comparison.isin:<14}"
        f"{format_quantity(comparison.pdf_quantity):>18}"
        f"{format_quantity(comparison.calculated_quantity):>18}"
        f"{format_quantity(comparison.difference):>18}"
        f"{'MATCHED' if comparison.matches else 'MISMATCH':>12}"
    )


def _escape_pdf_text(value: str) -> str:
    return value.replace("\\", "\\\\").replace("(", "\\(").replace(")", "\\)")
