import filecmp
import shutil
from pathlib import Path

import frappe


def standardize_private_pdf_attachment(
    document,
    expected_filename: str,
    *,
    fieldname: str = "attachment",
) -> str:
    """Give a local private PDF its canonical name and attach it to the document."""
    expected_url = f"/private/files/{expected_filename}"
    current_url = document.get(fieldname)
    if not current_url:
        frappe.throw("Attach a PDF before standardizing its filename.")

    files = frappe.qb.get_query(
        "File",
        fields=[
            "name",
            "attached_to_doctype",
            "attached_to_name",
            "attached_to_field",
        ],
        filters={"file_url": current_url},
        order_by="creation desc",
        ignore_permissions=False,
    ).run(as_dict=True)
    if not files:
        frappe.throw("The attached PDF was not found or you do not have permission to rename it.")

    selected = next(
        (
            row
            for row in files
            if row.attached_to_doctype == document.doctype
            and row.attached_to_name == document.name
            and row.attached_to_field == fieldname
        ),
        None,
    )
    source_row = selected or files[0]
    source_is_attached_elsewhere = bool(
        not selected
        and source_row.attached_to_doctype
        and (
            source_row.attached_to_doctype != document.doctype
            or source_row.attached_to_name != document.name
            or source_row.attached_to_field != fieldname
        )
    )
    file_doc = frappe.get_doc("File", source_row.name)
    file_doc.check_permission("read" if source_is_attached_elsewhere else "write")
    if not file_doc.is_private or file_doc.is_remote_file:
        frappe.throw("The PDF must be a local private file before it can be renamed.")

    private_files_path = Path(frappe.get_site_path("private", "files")).resolve()
    source_path = Path(file_doc.get_full_path()).resolve()
    target_path = (private_files_path / expected_filename).resolve()
    if not source_path.is_relative_to(private_files_path) or not source_path.is_file():
        frappe.throw("The attached private PDF could not be found.")
    if not target_path.is_relative_to(private_files_path):
        frappe.throw("The standardized filename is outside the private files directory.")

    source_is_shared = len(files) > 1 or source_is_attached_elsewhere
    if source_path != target_path:
        _place_standardized_file(
            source_path,
            target_path,
            source_is_shared=source_is_shared,
        )

    if source_is_attached_elsewhere:
        attachment = frappe.copy_doc(file_doc)
        attachment.update(
            {
                "file_name": expected_filename,
                "file_url": expected_url,
                "attached_to_doctype": document.doctype,
                "attached_to_name": document.name,
                "attached_to_field": fieldname,
                "folder": None,
            }
        )
        attachment.flags.copy_from_existing_file = True
        attachment.insert()
    else:
        file_doc.file_name = expected_filename
        file_doc.file_url = expected_url
        file_doc.attached_to_doctype = document.doctype
        file_doc.attached_to_name = document.name
        file_doc.attached_to_field = fieldname
        file_doc.save()

    document.set(fieldname, expected_url)
    return expected_url


def _place_standardized_file(source_path: Path, target_path: Path, *, source_is_shared: bool):
    if target_path.exists():
        if not filecmp.cmp(source_path, target_path, shallow=False):
            frappe.throw(
                f"Cannot rename the PDF because {target_path.name} already exists "
                "with different content."
            )
        if not source_is_shared:
            frappe.db.after_commit.add(lambda: source_path.unlink(missing_ok=True))
        return

    if source_is_shared:
        shutil.copy2(source_path, target_path)
        frappe.db.after_rollback.add(lambda: target_path.unlink(missing_ok=True))
        return

    source_path.rename(target_path)

    def restore_source_path():
        if target_path.exists() and not source_path.exists():
            target_path.rename(source_path)

    frappe.db.after_rollback.add(restore_source_path)
