# Copyright (c) 2026, Deepak Patel and contributors
# For license information, please see license.txt

from collections import defaultdict
from collections.abc import Iterable
from datetime import date
from decimal import ROUND_HALF_EVEN, Decimal

import frappe
from frappe import _
from frappe.model.document import Document
from frappe.utils import escape_html, getdate

from bond_management.bond_management.utils.accrual import get_accrued_interest_from_bond
from bond_management.bond_management.utils.financial import (
    PERCENT_PRECISION,
    DecimalInput,
    quantize_money,
    to_decimal,
)
from bond_management.bond_management.utils.transaction_attachment import (
    standardize_transaction_attachment,
)
from bond_management.bond_management.utils.transaction_pdf import (
    TransactionAttachmentDetails,
    TransactionAttachmentRow,
    get_transaction_attachment_details,
    transaction_attachment_row_values,
)
from bond_management.bond_management.utils.validation import optional_string, required_string

BOND_SNAPSHOT_FIELDS = (
    "bond_name",
    "currency",
    "coupon_frequency",
    "maturity_date",
    "coupon_rate",
    "face_value_per_unit",
    "issue_date",
    "day_count_convention",
)
PDF_MANAGED_FIELDS = (
    ("transaction_reference", "Transaction Reference", "text"),
    ("transaction_type", "Transaction Type", "text"),
    ("isin", "ISIN", "text"),
    ("portfolio_name", "Portfolio Name", "text"),
    ("trade_date", "Trade Date", "date"),
    ("settlement_date", "Settlement Date", "date"),
    ("quantity_face_value", "Quantity / Face Value", "quantity"),
    ("price", "Price", "price"),
    ("accrued_interest_paid", "Accrued Interest Paid", "money"),
    ("commission", "Commission %", "percent"),
)
PDF_POPULATION_CHECK_FIELDS = (
    "isin",
    "portfolio_name",
    "trade_date",
    "settlement_date",
    "quantity_face_value",
    "price",
)
CALCULATED_AMOUNT_FIELDS = (
    "principal",
    "commission_amount",
    "settlement_amount",
    "transaction_amount",
    "accrued_interest_calculated",
)
PDF_PRICE_PRECISION = Decimal("0.000001")
PDF_MONEY_PRECISION = Decimal("0.01")


@frappe.whitelist(methods=["POST"])
def read_transaction_pdf(name: str | None, attachment: str) -> dict:
    """Preview transaction PDF rows without submitting a document snapshot."""
    name = optional_string(name, "Bond Transaction")
    attachment = required_string(attachment, "Attachment")
    if name and frappe.db.exists("Bond Transaction", name):
        frappe.get_doc("Bond Transaction", name).check_permission("write")
    else:
        frappe.has_permission("Bond Transaction", "create", throw=True)

    details = get_transaction_attachment_details(attachment)
    return {
        "portfolio_name": details.portfolio_name,
        "account_no": details.account_no,
        "transactions": [serialize_transaction_attachment_row(row) for row in details.transactions],
    }


def serialize_transaction_attachment_row(row: TransactionAttachmentRow) -> dict:
    """Serialize a parsed transaction row for the form preview."""
    values = transaction_attachment_row_values(row)
    values["trade_date"] = row.trade_date.isoformat()
    values["settlement_date"] = row.settlement_date.isoformat()
    return values


def calculate_transaction_principal_value(
    face_value_per_unit: DecimalInput, quantity_face_value: DecimalInput, price: DecimalInput
) -> Decimal:
    """Return the unrounded consideration implied by a price quoted per 100."""
    return (
        to_decimal(face_value_per_unit) * to_decimal(quantity_face_value) * to_decimal(price) / Decimal("100")
    )


def _calculate_amount_values(
    bond: Document,
    settlement_date: date | str | None,
    quantity_face_value: DecimalInput,
    price: DecimalInput,
    accrued_interest_paid: DecimalInput,
    commission: DecimalInput,
) -> dict[str, Decimal]:
    """Derive stored amounts with one rounding path shared by the controller and preview RPC."""
    original_principal = to_decimal(bond.face_value_per_unit) * to_decimal(quantity_face_value)
    principal = calculate_transaction_principal_value(
        bond.face_value_per_unit,
        quantity_face_value,
        price,
    )
    commission_amount = original_principal * to_decimal(commission) / Decimal("100")
    # The bank transaction price is commission-inclusive, so commission_amount is
    # informational and must not be added to settlement or XIRR cash flows again.
    commission_amount = quantize_money(commission_amount)
    settlement_amount = quantize_money(principal + to_decimal(accrued_interest_paid))
    transaction_amount = quantize_money(settlement_amount - commission_amount)
    accrued_interest_calculated = get_accrued_interest_from_bond(
        bond,
        settlement_date=settlement_date,
        quantity_face_value=quantity_face_value,
    )
    return {
        "principal": quantize_money(principal),
        "commission_amount": commission_amount,
        "settlement_amount": settlement_amount,
        "transaction_amount": transaction_amount,
        "accrued_interest_calculated": quantize_money(accrued_interest_calculated),
    }


@frappe.whitelist(methods=["POST"])
def get_calculated_amounts(
    isin: str | None = None,
    settlement_date: str | None = None,
    quantity_face_value: DecimalInput = None,
    price: DecimalInput = None,
    accrued_interest_paid: DecimalInput = None,
    commission: DecimalInput = None,
    transaction_name: str | None = None,
) -> dict[str, Decimal]:
    """Return value-only calculations so stale RPCs cannot sync an older Document."""
    isin = optional_string(isin, "ISIN")
    settlement_date = optional_string(settlement_date, "Settlement Date")
    transaction_name = optional_string(transaction_name, "Transaction name")
    if transaction_name and frappe.db.exists("Bond Transaction", transaction_name):
        frappe.has_permission("Bond Transaction", "write", doc=transaction_name, throw=True)
    else:
        frappe.has_permission("Bond Transaction", "create", throw=True)

    if not isin:
        return dict.fromkeys(CALCULATED_AMOUNT_FIELDS, Decimal("0"))

    bond = frappe.get_doc("Bond Master", isin)
    bond.check_permission("read")
    return _calculate_amount_values(
        bond,
        settlement_date,
        quantity_face_value,
        price,
        accrued_interest_paid,
        commission,
    )


def _throw_pdf_mismatches(heading: str, mismatches: list[str], hint: str) -> None:
    if mismatches:
        frappe.throw(heading + "<br>".join(f"- {escape_html(mismatch)}" for mismatch in mismatches) + hint)


class BondTransaction(Document):
    def before_naming(self) -> None:
        """Fill a blank form from the selected PDF row so the reference-based name comes from the PDF."""
        row = self._get_selected_attachment_row()
        if row and not any(self.get(fieldname) for fieldname in PDF_POPULATION_CHECK_FIELDS):
            self._apply_attachment_row(row)
        elif row:
            self._validate_attachment_row(row)

    def before_validate(self) -> None:
        """Reject edits to PDF-managed fields before any derived value is recalculated."""
        row = self._get_selected_attachment_row()
        if row:
            self._validate_attachment_row(row)

    def validate(self) -> None:
        """Recompute every server-authoritative value and reject a save that breaks the ledger."""
        self.validate_required_inputs()
        bond = self.set_authoritative_bond_snapshot()
        self.validate_financial_terms()
        self.validate_transaction_dates()
        calculated_amounts = self.calculate_amounts(bond=bond)
        self.validate_pdf_amounts(calculated_amounts)
        self.validate_portfolio_ledger()

    def _has_pdf_attachment(self) -> bool:
        return bool(self.attachment) and self.attachment.lower().endswith(".pdf")

    def before_save(self) -> None:
        """Rename the private PDF only after its portfolio and transaction are identified."""
        if not self._has_pdf_attachment():
            return

        details = self._get_transaction_attachment_details()
        portfolio = frappe.get_doc("Bond Portfolio", details.portfolio_name)
        portfolio.check_permission("read")
        self.attachment = standardize_transaction_attachment(
            self,
            portfolio.account_no,
            self.settlement_date,
        )

    @frappe.whitelist(methods=["POST"])
    def create_selected_pdf_transactions(self, transaction_selections: str | list | None) -> list[str]:  # noqa: C901 -- whitelisted input checks, permission checks and atomic creation share one request
        """Atomically create one document per selected row from a multi-transaction PDF."""
        frappe.has_permission("Bond Transaction", "create", throw=True)
        if self.name and frappe.db.exists("Bond Transaction", self.name):
            frappe.throw(_("Multiple PDF transactions can only be created from a new form."))
        if transaction_selections is not None and not isinstance(transaction_selections, (str, list)):
            frappe.throw(_("Selected transaction references must be sent as a JSON list."))

        selections = frappe.parse_json(transaction_selections)
        if not isinstance(selections, list):
            frappe.throw(_("Select one or more transaction references to create."))
        normalized_selections = []
        for selection in selections:
            if isinstance(selection, str):
                reference = selection.strip().upper()
                portfolio_name = None
            elif isinstance(selection, dict):
                raw_reference = selection.get("transaction_reference")
                raw_portfolio_name = selection.get("portfolio_name")
                if raw_reference is not None and not isinstance(raw_reference, str):
                    frappe.throw(_("Each transaction reference must be text."))
                if raw_portfolio_name is not None and not isinstance(raw_portfolio_name, str):
                    frappe.throw(_("Each portfolio name must be text."))
                reference = (raw_reference or "").strip().upper()
                portfolio_name = (raw_portfolio_name or "").strip() or None
            else:
                frappe.throw(_("Each selected transaction must include a reference and portfolio."))
            if reference:
                normalized_selections.append((reference, portfolio_name))

        selections_by_reference = dict(normalized_selections)
        references = list(selections_by_reference)
        if not references:
            frappe.throw(_("Select one or more transaction references to create."))

        details = self._get_transaction_attachment_details()
        rows_by_reference = {row.transaction_reference: row for row in details.transactions}
        unknown = sorted(set(references) - set(rows_by_reference))
        if unknown:
            frappe.throw(
                _("The selected references are not present in the attached PDF: {0}.").format(
                    ", ".join(unknown)
                )
            )

        existing = frappe.qb.get_query(
            "Bond Transaction",
            fields=["name"],
            filters={"name": ["in", references]},
            ignore_permissions=False,
        ).run(pluck=True)
        if existing:
            frappe.throw(
                _("Bond Transactions already exist for: {0}. No transactions were created.").format(
                    ", ".join(sorted(existing))
                )
            )

        selected_rows = [
            (
                rows_by_reference[reference],
                selections_by_reference[reference] or rows_by_reference[reference].portfolio_name,
            )
            for reference in references
        ]
        portfolio_names = {portfolio_name for _, portfolio_name in selected_rows}
        accessible_portfolios = set(
            frappe.qb.get_query(
                "Bond Portfolio",
                fields=["name"],
                filters={"name": ["in", portfolio_names]},
                ignore_permissions=False,
            ).run(pluck=True)
        )
        inaccessible = sorted(portfolio_names - accessible_portfolios)
        if inaccessible:
            frappe.throw(_("No accessible Bond Portfolio exists for: {0}.").format(", ".join(inaccessible)))
        self._lock_portfolios(portfolio_names)
        selected_rows.sort(
            key=lambda selected: (
                selected[0].transaction_type == "Sale",
                selected[0].settlement_date,
                selected[0].transaction_reference,
            )
        )
        created = []
        attachment = self.attachment
        for row, portfolio_name in selected_rows:
            portfolio_override = portfolio_name != row.portfolio_name
            transaction = frappe.get_doc(
                {
                    "doctype": "Bond Transaction",
                    "attachment": attachment,
                    "attachment_portfolio_override": portfolio_override,
                    **transaction_attachment_row_values(row, portfolio_name),
                }
            )
            transaction.flags.transaction_attachment_details = details
            transaction.flags.allow_attachment_portfolio_override = portfolio_override
            transaction.insert()
            attachment = transaction.attachment
            created.append(transaction.name)
        return created

    def _get_selected_attachment_row(self) -> TransactionAttachmentRow | None:
        if not self.attachment:
            return None
        if not self._has_pdf_attachment():
            previous = self.get_doc_before_save()
            if previous and previous.attachment == self.attachment:
                return None
            frappe.throw(
                _(
                    "Automatic Bond Transaction entry requires a PDF attachment. "
                    "Remove the attachment to use manual entry."
                )
            )

        details = self._get_transaction_attachment_details()
        if not self.transaction_reference:
            if len(details.transactions) > 1:
                references = ", ".join(row.transaction_reference for row in details.transactions)
                frappe.throw(
                    _(
                        "This PDF contains multiple transactions. Select one or more references before saving: {0}."
                    ).format(references)
                )
            return details.transactions[0]

        reference = str(self.transaction_reference).strip().upper()
        matching = [row for row in details.transactions if row.transaction_reference == reference]
        if not matching:
            frappe.throw(
                _("Transaction Reference {0} is not present in the attached PDF.").format(
                    frappe.bold(escape_html(reference))
                )
            )
        return matching[0]

    def _get_transaction_attachment_details(self) -> TransactionAttachmentDetails:
        """Parse the attachment once per save; batch creation shares one parse across documents."""
        details = self.flags.transaction_attachment_details
        if not details:
            details = get_transaction_attachment_details(self.attachment)
            self.flags.transaction_attachment_details = details
        return details

    def _apply_attachment_row(self, row: TransactionAttachmentRow) -> None:
        for fieldname, value in transaction_attachment_row_values(row).items():
            self.set(fieldname, value)

    def _validate_attachment_row(self, row: TransactionAttachmentRow) -> None:
        """Keep PDF-managed fields equal to the PDF; only batch selection may override the portfolio."""
        mismatches = []
        expected_portfolio = row.portfolio_name
        if self.attachment_portfolio_override:
            previous = self.get_doc_before_save()
            override_is_authorized = self.flags.allow_attachment_portfolio_override
            override_is_unchanged = (
                previous
                and previous.attachment_portfolio_override
                and previous.portfolio_name == self.portfolio_name
            )
            if not (override_is_authorized or override_is_unchanged):
                frappe.throw(
                    _(
                        "PDF portfolio overrides can only be set while selecting transactions "
                        "from a multi-transaction attachment."
                    )
                )
            expected_portfolio = self.portfolio_name
        expected_values = transaction_attachment_row_values(row, expected_portfolio)
        for fieldname, label, value_type in PDF_MANAGED_FIELDS:
            actual = self.get(fieldname)
            expected = expected_values[fieldname]
            if not self._attachment_values_match(actual, expected, value_type):
                mismatches.append(f"{label} (form: {actual or 'blank'}, PDF: {expected})")
        _throw_pdf_mismatches(
            _("The Bond Transaction fields no longer match the attached PDF:<br>"),
            mismatches,
            _("<br>Re-read the PDF, or remove the attachment to use manual entry."),
        )

    @staticmethod
    def _attachment_values_match(
        actual: DecimalInput | date, expected: DecimalInput | date, value_type: str
    ) -> bool:
        """Compare form and PDF values at the precision the PDF prints for that value type."""
        if value_type == "text":
            return str(actual or "").strip().upper() == str(expected or "").strip().upper()
        if value_type == "date":
            return bool(actual) and getdate(actual) == getdate(expected)

        actual_decimal = to_decimal(actual)
        expected_decimal = to_decimal(expected)
        if value_type == "quantity":
            return actual_decimal == expected_decimal
        precision = {
            "price": PDF_PRICE_PRECISION,
            "money": PDF_MONEY_PRECISION,
            "percent": PERCENT_PRECISION,
        }[value_type]
        return actual_decimal.quantize(
            precision,
            rounding=ROUND_HALF_EVEN,
        ) == expected_decimal.quantize(precision, rounding=ROUND_HALF_EVEN)

    def validate_required_inputs(self) -> None:
        """Fail early with a field label before any lookup depends on a missing value."""
        for fieldname, label in (
            ("isin", "ISIN"),
            ("portfolio_name", "Portfolio Name"),
            ("trade_date", "Trade Date"),
            ("settlement_date", "Settlement Date"),
        ):
            if not self.get(fieldname):
                frappe.throw(_("{0} is required").format(label))
        if self.transaction_type not in {"Purchase", "Sale"}:
            frappe.throw(_("Transaction Type must be Purchase or Sale"))

    def on_trash(self) -> None:
        """A purchase cannot be deleted when later transactions depend on it."""
        self._lock_portfolios({self.portfolio_name})
        self._validate_ledger_group(
            self.isin,
            self.portfolio_name,
            exclude_name=self.name,
        )

    def set_authoritative_bond_snapshot(self) -> Document:
        """Overwrite client-sent bond terms with Bond Master values and return the bond."""
        bond = frappe.get_doc("Bond Master", self.isin)
        bond.check_permission("read")
        for fieldname in BOND_SNAPSHOT_FIELDS:
            self.set(fieldname, bond.get(fieldname))
        return bond

    def validate_financial_terms(self) -> None:
        """Reject non-positive quantity, face value and price, and negative commission."""
        if to_decimal(self.quantity_face_value) <= 0:
            frappe.throw(_("Quantity / Face Value must be greater than zero"))
        if to_decimal(self.face_value_per_unit) <= 0:
            frappe.throw(_("Face Value Per Unit must be greater than zero"))
        if to_decimal(self.price) <= 0:
            frappe.throw(_("Price must be greater than zero"))
        if to_decimal(self.commission) < 0:
            frappe.throw(_("Commission must be zero or greater"))

    def validate_transaction_dates(self) -> None:
        """Keep trade on or before settlement, and both within the bond's issue-to-maturity life."""
        trade_date = getdate(self.trade_date)
        settlement_date = getdate(self.settlement_date)
        issue_date = getdate(self.issue_date)
        maturity_date = getdate(self.maturity_date)

        if trade_date < issue_date:
            frappe.throw(_("Trade Date must be on or after Issue Date"))
        if trade_date > maturity_date:
            frappe.throw(_("Trade Date must be on or before Maturity Date"))
        if settlement_date < issue_date:
            frappe.throw(_("Settlement Date must be on or after Issue Date"))
        if settlement_date > maturity_date:
            frappe.throw(_("Settlement Date must be on or before Maturity Date"))
        if trade_date > settlement_date:
            frappe.throw(_("Trade Date must be on or before Settlement Date"))

    def calculate_amounts(self, bond: Document | None = None) -> dict[str, Decimal]:
        """Store server-calculated amounts so client-sent totals are never trusted."""
        if bond is None:
            bond = frappe.get_doc("Bond Master", self.isin)
        values = _calculate_amount_values(
            bond,
            self.settlement_date,
            self.quantity_face_value,
            self.price,
            self.accrued_interest_paid,
            self.commission,
        )
        for fieldname, value in values.items():
            self.set(fieldname, value)
        return values

    def validate_pdf_amounts(self, calculated_amounts: dict[str, Decimal]) -> None:
        """Catch a wrong Bond Master face value by comparing calculated amounts with the PDF."""
        if not self._has_pdf_attachment():
            return

        row = self._get_selected_attachment_row()
        mismatches = []
        for fieldname, label in (
            ("principal", "Principal"),
            ("settlement_amount", "Settlement Amount"),
        ):
            expected = getattr(row, fieldname)
            if expected is None:
                continue
            actual = calculated_amounts[fieldname]
            if not self._attachment_values_match(actual, expected, "money"):
                mismatches.append(f"{label} (calculated: {actual}, PDF: {expected})")

        _throw_pdf_mismatches(
            _("The calculated Bond Transaction amounts no longer match the attached PDF:<br>"),
            mismatches,
            _("<br>Correct the Bond Master Face Value Per Unit or re-read the PDF."),
        )

    def validate_portfolio_ledger(self) -> None:
        """Keep the old and new ISIN-portfolio ledgers non-negative when either changes."""
        previous = self.get_doc_before_save()
        groups = {(self.isin, self.portfolio_name)}
        if previous:
            groups.add((previous.isin, previous.portfolio_name))

        self._lock_portfolios({portfolio for _isin, portfolio in groups})
        for isin, portfolio_name in sorted(groups):
            replacement = self if (isin, portfolio_name) == (self.isin, self.portfolio_name) else None
            self._validate_ledger_group(
                isin,
                portfolio_name,
                exclude_name=self.name,
                replacement=replacement,
            )

    def _lock_portfolios(self, portfolio_names: Iterable[str | None]) -> None:
        # A real portfolio row exists before its transactions, so this also locks an
        # empty ledger and serializes concurrent sales against the same portfolio.
        for portfolio_name in sorted(name for name in portfolio_names if name):
            frappe.has_permission("Bond Portfolio", "read", doc=portfolio_name, throw=True)
            # This controller is the integrity boundary. Permission-filtering would hide
            # other owners' rows and could allow the complete ledger to go negative.
            frappe.qb.get_query(
                "Bond Portfolio",
                filters={"name": portfolio_name},
                fields=["name"],
                for_update=True,
                ignore_permissions=True,
            ).run()

    def _validate_ledger_group(
        self,
        isin: str,
        portfolio_name: str,
        exclude_name: str | None = None,
        replacement: BondTransaction | None = None,
    ) -> None:
        """Reject any settlement date on which the end-of-day position would go negative."""
        rows = frappe.qb.get_query(
            "Bond Transaction",
            filters={"isin": isin, "portfolio_name": portfolio_name},
            fields=[
                "name",
                "transaction_type",
                "quantity_face_value",
                "settlement_date",
            ],
            for_update=True,
            # The framework already checked the current document and linked portfolio;
            # the invariant itself must lock and inspect every transaction in the group.
            ignore_permissions=True,
        ).run(as_dict=True)

        ledger_rows = [row for row in rows if row.name != exclude_name]
        if replacement:
            ledger_rows.append(replacement)

        daily_movements = defaultdict(Decimal)
        for row in ledger_rows:
            quantity = to_decimal(row.get("quantity_face_value"))
            if quantity <= 0:
                frappe.throw(
                    _("Transaction {0} must have a positive quantity").format(row.get("name") or "(unsaved)")
                )
            direction = 1 if row.get("transaction_type") == "Purchase" else -1
            daily_movements[getdate(row.get("settlement_date"))] += direction * quantity

        position = Decimal("0")
        for settlement_date in sorted(daily_movements):
            position += daily_movements[settlement_date]
            if position < 0:
                frappe.throw(
                    _(
                        "Transactions would make the position negative on {0}. Purchases settling that day are included."
                    ).format(settlement_date)
                )
