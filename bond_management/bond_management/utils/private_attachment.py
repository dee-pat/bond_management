import filecmp
import hashlib
import os
import shutil
import tempfile
from collections.abc import Iterator
from contextlib import contextmanager
from pathlib import Path

import frappe
from filelock import FileLock, Timeout
from frappe import _


def read_private_pdf_attachment(
    attachment,
    *,
    max_bytes: int,
    missing_message: str,
    extension_message: str,
    private_message: str,
    size_message: str,
) -> tuple[bytes, str]:
    """Read a private PDF through Frappe's File storage API."""
    attachment = _required_attachment_url(attachment, missing_message)
    if not attachment.lower().endswith(".pdf"):
        frappe.throw(extension_message)

    files = _get_file_rows(attachment)
    if not files:
        frappe.throw(_("The attached PDF was not found or you do not have permission to read it."))

    file_doc = frappe.get_doc("File", files[0].name)
    file_doc.check_permission("read")
    if not file_doc.is_private:
        frappe.throw(private_message)

    if file_doc.file_size and int(file_doc.file_size) > max_bytes:
        frappe.throw(size_message)

    try:
        # Frappe's default encodings can turn binary PDF bytes into text.
        content = file_doc.get_content(encodings=())
    except (OSError, TypeError, ValueError):
        frappe.throw(_("The attached private PDF could not be read from storage."))

    if isinstance(content, str):
        content = content.encode()
    if not isinstance(content, bytes):
        frappe.throw(_("The attached private PDF could not be read from storage."))
    if len(content) > max_bytes:
        frappe.throw(size_message)

    return content, file_doc.file_name


def standardize_private_pdf_attachment(
    document,
    expected_filename: str,
    *,
    fieldname: str = "attachment",
) -> str:
    """Give a local private PDF its canonical name and attach it to the document."""
    expected_filename = _validated_filename(expected_filename)
    expected_url = f"/private/files/{expected_filename}"

    current_url = _required_attachment_url(
        document.get(fieldname),
        _("Attach a PDF before standardizing its filename."),
    )

    with _standardization_lock(expected_url):
        files = _get_file_rows(current_url, expected_url, for_update=True)
        current_files = [file_row for file_row in files if file_row.file_url == current_url]
        if not current_files:
            frappe.throw(_("The attached PDF was not found or you do not have permission to rename it."))

        selected = next(
            (
                row
                for row in current_files
                if row.attached_to_doctype == document.doctype
                and row.attached_to_name == document.name
                and row.attached_to_field == fieldname
            ),
            None,
        )
        source_row = selected or current_files[0]
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
            frappe.throw(_("The PDF must be a local private file before it can be renamed."))

        private_files_path = Path(frappe.get_site_path("private", "files")).resolve()
        source_path = Path(file_doc.get_full_path()).resolve()
        target_path = (private_files_path / expected_filename).resolve()
        if not source_path.is_relative_to(private_files_path) or not source_path.is_file():
            frappe.throw(_("The attached private PDF could not be found."))
        if not target_path.is_relative_to(private_files_path):
            frappe.throw(_("The standardized filename is outside the private files directory."))

        source_is_shared = len(current_files) > 1 or source_is_attached_elsewhere
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


def _required_attachment_url(attachment, missing_message: str) -> str:
    if attachment is None or (isinstance(attachment, str) and not attachment.strip()):
        frappe.throw(missing_message)
    if not isinstance(attachment, str):
        frappe.throw(_("The attachment URL must be a string."))
    return attachment.strip()


def _validated_filename(filename: str) -> str:
    if (
        not isinstance(filename, str)
        or not filename
        or filename in {".", ".."}
        or "/" in filename
        or "\\" in filename
    ):
        frappe.throw(_("The standardized filename is invalid."))
    return filename


def _get_file_rows(
    *file_urls: str,
    for_update: bool = False,
) -> list:
    filters = {"file_url": file_urls[0]} if len(file_urls) == 1 else {"file_url": ["in", list(file_urls)]}
    return frappe.qb.get_query(
        "File",
        fields=[
            "name",
            "file_url",
            "attached_to_doctype",
            "attached_to_name",
            "attached_to_field",
        ],
        filters=filters,
        order_by="creation desc",
        for_update=for_update,
        ignore_permissions=False,
    ).run(as_dict=True)


@contextmanager
def _standardization_lock(expected_url: str) -> Iterator[None]:
    lock_registry = getattr(frappe.local, "_bond_private_attachment_locks", None)
    if lock_registry is None:
        lock_registry = {}
        frappe.local._bond_private_attachment_locks = lock_registry

    existing_lock = lock_registry.get(expected_url)
    if existing_lock:
        existing_lock["depth"] += 1
        try:
            yield
        finally:
            existing_lock["depth"] -= 1
        return

    lock_key = hashlib.sha256(expected_url.encode()).hexdigest()
    lock_path = Path(frappe.get_site_path("locks", f"bond-private-attachment-{lock_key}.lock"))
    lock = FileLock(lock_path)
    try:
        lock_path.parent.mkdir(parents=True, exist_ok=True)
        lock.acquire(timeout=30)
    except Timeout:
        frappe.throw(_("Another request is standardizing this attachment. Try again."))
    except OSError:
        frappe.throw(_("The attachment standardization lock could not be created."))

    lock_state = {"depth": 1, "released": False}
    lock_registry[expected_url] = lock_state

    def release_lock():
        if not lock_state["released"]:
            lock_state["released"] = True
            lock_registry.pop(expected_url, None)
            lock.release()

    try:
        yield
    except BaseException:
        # Release after filesystem rollback callbacks, not before them.
        frappe.db.after_commit.add(release_lock)
        frappe.db.after_rollback.add(release_lock)
        raise
    else:
        # _place_standardized_file registers its cleanup callbacks while the
        # lock is held. Appending release here keeps cleanup serialized too.
        frappe.db.after_commit.add(release_lock)
        frappe.db.after_rollback.add(release_lock)


def _place_standardized_file(source_path: Path, target_path: Path, *, source_is_shared: bool):
    if target_path.exists():
        if not target_path.is_file():
            frappe.throw(_("Cannot standardize the PDF because the target path is not a file."))
        if not filecmp.cmp(source_path, target_path, shallow=False):
            frappe.throw(
                f"Cannot rename the PDF because {target_path.name} already exists with different content."
            )
        if not source_is_shared:
            frappe.db.after_commit.add(lambda: source_path.unlink(missing_ok=True))
        return

    if source_is_shared:
        temporary_path = None
        try:
            with tempfile.NamedTemporaryFile(
                dir=target_path.parent,
                prefix=f".{target_path.name}.",
                suffix=".tmp",
                delete=False,
            ) as temporary_file:
                temporary_path = Path(temporary_file.name)
            shutil.copy2(source_path, temporary_path)
            os.replace(temporary_path, target_path)
        except BaseException:
            if temporary_path:
                temporary_path.unlink(missing_ok=True)
            raise
        frappe.db.after_rollback.add(lambda: target_path.unlink(missing_ok=True))
        return

    source_path.replace(target_path)

    def restore_source_path():
        if target_path.exists() and not source_path.exists():
            target_path.replace(source_path)

    frappe.db.after_rollback.add(restore_source_path)
