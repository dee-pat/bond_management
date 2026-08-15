from io import BytesIO

import frappe
from frappe.core.doctype.file.utils import get_content_hash
from frappe.utils import escape_html, get_datetime
from pypdf import PdfWriter
from pypdf.generic import DecodedStreamObject, DictionaryObject, NameObject

from bond_management.bond_management.utils.statement_quantity_reconciliation import (
    StatementQuantityComparison,
    format_quantity,
)

REPORT_FILENAME_PREFIX = "Bond-Quantity-Reconciliation-"
REPORT_FIELD = "quantity_reconciliation_report"
REPORT_DELETE_METHOD = (
    "bond_management.bond_management.utils.statement_quantity_report."
    "delete_quantity_reconciliation_report_file"
)


def attach_quantity_reconciliation_report(statement, comparisons, *, file_name=None) -> str:
    """Create or replace the private reconciliation PDF for a statement.

    A statement owns one current report. Updating that File keeps the URL stable,
    lets File's rollback hook restore its previous bytes, and avoids leaking a
    private PDF on every unchanged save.
    """
    existing_reports = _get_report_files(statement.name)
    if file_name:
        existing = next(
            (report for report in existing_reports if report.file_name == file_name),
            None,
        )
        if existing:
            return existing.file_url

    generated_at = _stable_generated_at(statement)
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
        generated_at=generated_at,
        comparisons=tuple(comparisons),
        password=password,
    )

    content_hash = get_content_hash(content)
    matching_report = next(
        (
            report
            for report in existing_reports
            if report.content_hash == content_hash and _file_exists(report.name)
        ),
        None,
    )
    if matching_report and not file_name:
        _schedule_obsolete_report_cleanup(existing_reports, matching_report.name)
        return matching_report.file_url

    if existing_reports and not file_name:
        current_report = next(
            (report for report in existing_reports if _file_exists(report.name)),
            None,
        )
        if current_report:
            file_doc = frappe.get_doc("File", current_report.name)
            # Generated reports are a verified service-side artifact. Bypass
            # user permissions only for this owned File update.
            file_doc.save_file(
                content=content,
                ignore_existing_file_check=True,
                overwrite=True,
            )
            file_doc.save(ignore_permissions=True)
            _schedule_obsolete_report_cleanup(existing_reports, file_doc.name)
            return file_doc.file_url

    file_doc = frappe.get_doc(
        {
            "doctype": "File",
            "file_name": file_name or f"{REPORT_FILENAME_PREFIX}{statement.name}.pdf",
            "attached_to_doctype": "Bond Statement",
            "attached_to_name": statement.name,
            "attached_to_field": REPORT_FIELD,
            "content": content,
            "is_private": 1,
        }
    ).insert()
    _schedule_obsolete_report_cleanup(existing_reports, file_doc.name)
    return file_doc.file_url


def delete_quantity_reconciliation_reports(statement_name: str) -> None:
    """Remove statement-owned report Files after the parent deletion commits."""
    for report in _get_report_files(statement_name):
        _schedule_file_deletion(report.name)


def _get_report_files(statement_name: str) -> list:
    return frappe.qb.get_query(
        "File",
        fields=["name", "file_name", "file_url", "content_hash"],
        filters={
            "attached_to_doctype": "Bond Statement",
            "attached_to_name": statement_name,
            "attached_to_field": REPORT_FIELD,
        },
        order_by="creation asc, name asc",
        ignore_permissions=True,
    ).run(as_dict=True)


def _file_exists(file_name: str) -> bool:
    try:
        return frappe.get_doc("File", file_name).exists_on_disk()
    except (frappe.DoesNotExistError, OSError):
        return False


def _stable_generated_at(statement) -> str:
    if not statement.creation:
        return "unknown"
    return get_datetime(statement.creation).strftime("%Y-%m-%d %H:%M:%S")


def _schedule_obsolete_report_cleanup(reports, keep_name: str) -> None:
    for report in reports:
        if report.name != keep_name:
            _schedule_file_deletion(report.name)


def _schedule_file_deletion(file_name: str) -> None:
    # File deletion needs its own worker transaction. Running delete_doc in an
    # after_commit callback starts uncommitted database work in the web process.
    frappe.enqueue(
        REPORT_DELETE_METHOD,
        queue="short",
        enqueue_after_commit=True,
        file_name=file_name,
    )


def delete_quantity_reconciliation_report_file(file_name: str) -> None:
    """Delete an obsolete generated report in a worker-owned transaction."""
    try:
        if frappe.db.exists("File", file_name):
            # Scheduling happens only after the statement permission boundary.
            frappe.delete_doc("File", file_name, ignore_permissions=True)
    except Exception:
        frappe.logger("bond_management").exception(
            "Bond Statement report cleanup failed: file=%s",
            file_name,
        )
        raise


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
