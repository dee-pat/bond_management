# Copyright (c) 2026, Deepak Patel and contributors
# For license information, please see license.txt

from collections import defaultdict
from decimal import ROUND_HALF_EVEN, Decimal

import frappe
from frappe.model.document import Document
from frappe.utils import escape_html, getdate

from bond_management.bond_management.utils.accrual import get_accrued_interest
from bond_management.bond_management.utils.financial import (
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
)

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
PDF_PRICE_PRECISION = Decimal("0.000001")
PDF_MONEY_PRECISION = Decimal("0.01")
PDF_PERCENT_PRECISION = Decimal("0.000000001")


def _calculate_amount_values(
    bond, settlement_date, quantity_face_value, price, accrued_interest_paid, commission
):
    principal = to_decimal(bond.face_value_per_unit) * to_decimal(quantity_face_value)
    commission_amount = principal * to_decimal(commission) / Decimal("100")
    # The bank transaction price is commission-inclusive, so commission_amount is
    # informational and must not be added to settlement or XIRR cash flows again.
    settlement_amount = principal * to_decimal(price) / Decimal("100") + to_decimal(accrued_interest_paid)
    accrued_interest_calculated = get_accrued_interest(
        isin=bond.name,
        settlement_date=settlement_date,
        quantity_face_value=quantity_face_value,
    )
    return {
        "principal": quantize_money(principal),
        "commission_amount": quantize_money(commission_amount),
        "settlement_amount": quantize_money(settlement_amount),
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
    if transaction_name and frappe.db.exists("Bond Transaction", transaction_name):
        frappe.has_permission("Bond Transaction", "write", doc=transaction_name, throw=True)
    else:
        frappe.has_permission("Bond Transaction", "create", throw=True)

    if not isin:
        return {
            "principal": Decimal("0"),
            "commission_amount": Decimal("0"),
            "settlement_amount": Decimal("0"),
            "accrued_interest_calculated": Decimal("0"),
        }

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


class BondTransaction(Document):
    def before_naming(self):
        row = self._get_selected_attachment_row()
        if row and not any(self.get(fieldname) for fieldname in PDF_POPULATION_CHECK_FIELDS):
            self._apply_attachment_row(row)
        elif row:
            self._validate_attachment_row(row)

    def before_validate(self):
        row = self._get_selected_attachment_row()
        if row:
            self._validate_attachment_row(row)

    def validate(self):
        self.validate_required_inputs()
        self.set_authoritative_bond_snapshot()
        self.validate_financial_terms()
        self.validate_transaction_dates()
        self.calculate_amounts()
        self.validate_portfolio_ledger()

    def before_save(self):
        if not self.attachment or not self.attachment.lower().endswith(".pdf"):
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
    def read_transaction_pdf(self):
        """Return every transaction found so the client can populate or offer a selection."""
        permission_type = (
            "write" if self.name and frappe.db.exists("Bond Transaction", self.name) else "create"
        )
        self.check_permission(permission_type)
        details = self._get_transaction_attachment_details()
        return {
            "portfolio_name": details.portfolio_name,
            "account_no": details.account_no,
            "transactions": [self._serialize_attachment_row(row) for row in details.transactions],
        }

    @frappe.whitelist(methods=["POST"])
    def create_selected_pdf_transactions(self, transaction_selections):
        """Atomically create one document per selected row from a multi-transaction PDF."""
        frappe.has_permission("Bond Transaction", "create", throw=True)
        if self.name and frappe.db.exists("Bond Transaction", self.name):
            frappe.throw("Multiple PDF transactions can only be created from a new form.")

        selections = frappe.parse_json(transaction_selections)
        if not isinstance(selections, list):
            frappe.throw("Select one or more transaction references to create.")
        normalized_selections = []
        for selection in selections:
            if isinstance(selection, str):
                reference = selection.strip().upper()
                portfolio_name = None
            elif isinstance(selection, dict):
                reference = str(selection.get("transaction_reference") or "").strip().upper()
                portfolio_name = str(selection.get("portfolio_name") or "").strip()
            else:
                frappe.throw("Each selected transaction must include a reference and portfolio.")
            if reference:
                normalized_selections.append((reference, portfolio_name))

        selections_by_reference = dict(normalized_selections)
        references = list(selections_by_reference)
        if not references:
            frappe.throw("Select one or more transaction references to create.")

        details = self._get_transaction_attachment_details()
        rows_by_reference = {row.transaction_reference: row for row in details.transactions}
        unknown = sorted(set(references) - set(rows_by_reference))
        if unknown:
            frappe.throw(
                f"The selected references are not present in the attached PDF: {', '.join(unknown)}."
            )

        existing = frappe.qb.get_query(
            "Bond Transaction",
            fields=["name"],
            filters={"name": ["in", references]},
            ignore_permissions=False,
        ).run(pluck=True)
        if existing:
            frappe.throw(
                "Bond Transactions already exist for: "
                f"{', '.join(sorted(existing))}. No transactions were created."
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
            frappe.throw("No accessible Bond Portfolio exists for: " + ", ".join(inaccessible) + ".")
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
                    **self._attachment_row_values(row, portfolio_name),
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
        if not self.attachment.lower().endswith(".pdf"):
            previous = self.get_doc_before_save()
            if previous and previous.attachment == self.attachment:
                return None
            frappe.throw(
                "Automatic Bond Transaction entry requires a PDF attachment. "
                "Remove the attachment to use manual entry."
            )

        details = self._get_transaction_attachment_details()
        if not self.transaction_reference:
            if len(details.transactions) > 1:
                references = ", ".join(row.transaction_reference for row in details.transactions)
                frappe.throw(
                    "This PDF contains multiple transactions. Select one or more references "
                    f"before saving: {references}."
                )
            return details.transactions[0]

        reference = str(self.transaction_reference).strip().upper()
        matching = [row for row in details.transactions if row.transaction_reference == reference]
        if not matching:
            frappe.throw(
                f"Transaction Reference {frappe.bold(reference)} is not present in the attached PDF."
            )
        return matching[0]

    def _get_transaction_attachment_details(self) -> TransactionAttachmentDetails:
        details = self.flags.transaction_attachment_details
        if not details:
            details = get_transaction_attachment_details(self.attachment)
            self.flags.transaction_attachment_details = details
        return details

    def _apply_attachment_row(self, row: TransactionAttachmentRow):
        for fieldname, value in self._attachment_row_values(row).items():
            self.set(fieldname, value)

    def _validate_attachment_row(self, row: TransactionAttachmentRow):
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
                    "PDF portfolio overrides can only be set while selecting transactions "
                    "from a multi-transaction attachment."
                )
            expected_portfolio = self.portfolio_name
        expected_values = self._attachment_row_values(row, expected_portfolio)
        for fieldname, label, value_type in PDF_MANAGED_FIELDS:
            actual = self.get(fieldname)
            expected = expected_values[fieldname]
            if not self._attachment_values_match(actual, expected, value_type):
                mismatches.append(f"{label} (form: {actual or 'blank'}, PDF: {expected})")
        if mismatches:
            frappe.throw(
                "The Bond Transaction fields no longer match the attached PDF:<br>"
                + "<br>".join(f"- {escape_html(mismatch)}" for mismatch in mismatches)
                + "<br>Re-read the PDF, or remove the attachment to use manual entry."
            )

    @staticmethod
    def _attachment_row_values(row: TransactionAttachmentRow, portfolio_name: str | None = None) -> dict:
        return {
            "transaction_reference": row.transaction_reference,
            "transaction_type": row.transaction_type,
            "isin": row.isin,
            "portfolio_name": portfolio_name or row.portfolio_name,
            "trade_date": row.trade_date,
            "settlement_date": row.settlement_date,
            "quantity_face_value": row.quantity_face_value,
            "price": row.price,
            "accrued_interest_paid": row.accrued_interest_paid,
            "commission": row.commission,
        }

    @classmethod
    def _serialize_attachment_row(cls, row: TransactionAttachmentRow) -> dict:
        values = cls._attachment_row_values(row)
        values["trade_date"] = row.trade_date.isoformat()
        values["settlement_date"] = row.settlement_date.isoformat()
        return values

    @staticmethod
    def _attachment_values_match(actual, expected, value_type: str) -> bool:
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
            "percent": PDF_PERCENT_PRECISION,
        }[value_type]
        return actual_decimal.quantize(
            precision,
            rounding=ROUND_HALF_EVEN,
        ) == expected_decimal.quantize(precision, rounding=ROUND_HALF_EVEN)

    def validate_required_inputs(self):
        for fieldname, label in (
            ("isin", "ISIN"),
            ("portfolio_name", "Portfolio Name"),
            ("trade_date", "Trade Date"),
            ("settlement_date", "Settlement Date"),
        ):
            if not self.get(fieldname):
                frappe.throw(f"{label} is required")
        if self.transaction_type not in {"Purchase", "Sale"}:
            frappe.throw("Transaction Type must be Purchase or Sale")

    def on_trash(self):
        """A purchase cannot be deleted when later transactions depend on it."""
        self._lock_portfolios({self.portfolio_name})
        self._validate_ledger_group(
            self.isin,
            self.portfolio_name,
            exclude_name=self.name,
        )

    def set_authoritative_bond_snapshot(self):
        bond = frappe.get_doc("Bond Master", self.isin)
        bond.check_permission("read")
        for fieldname in BOND_SNAPSHOT_FIELDS:
            self.set(fieldname, bond.get(fieldname))

    def validate_financial_terms(self):
        if to_decimal(self.quantity_face_value) <= 0:
            frappe.throw("Quantity / Face Value must be greater than zero")
        if to_decimal(self.face_value_per_unit) <= 0:
            frappe.throw("Face Value Per Unit must be greater than zero")
        if to_decimal(self.price) <= 0:
            frappe.throw("Price must be greater than zero")
        if to_decimal(self.commission) < 0:
            frappe.throw("Commission must be zero or greater")

    def validate_transaction_dates(self):
        trade_date = getdate(self.trade_date)
        settlement_date = getdate(self.settlement_date)
        issue_date = getdate(self.issue_date)
        maturity_date = getdate(self.maturity_date)

        if trade_date < issue_date:
            frappe.throw("Trade Date must be on or after Issue Date")
        if trade_date > maturity_date:
            frappe.throw("Trade Date must be on or before Maturity Date")
        if settlement_date < issue_date:
            frappe.throw("Settlement Date must be on or after Issue Date")
        if settlement_date > maturity_date:
            frappe.throw("Settlement Date must be on or before Maturity Date")
        if trade_date > settlement_date:
            frappe.throw("Trade Date must be on or before Settlement Date")

    def calculate_amounts(self):
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

    def validate_portfolio_ledger(self):
        previous = self.get_doc_before_save()
        groups = {(self.isin, self.portfolio_name)}
        if previous:
            groups.add((previous.isin, previous.portfolio_name))

        self._lock_portfolios({portfolio for _isin, portfolio in groups})
        for isin, portfolio_name in sorted(groups):
            replacement = (
                self
                if (isin, portfolio_name)
                == (
                    self.isin,
                    self.portfolio_name,
                )
                else None
            )
            self._validate_ledger_group(
                isin,
                portfolio_name,
                exclude_name=self.name,
                replacement=replacement,
            )

    def _lock_portfolios(self, portfolio_names):
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

    def _validate_ledger_group(self, isin, portfolio_name, exclude_name=None, replacement=None):
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
                frappe.throw(f"Transaction {row.get('name') or '(unsaved)'} must have a positive quantity")
            direction = 1 if row.get("transaction_type") == "Purchase" else -1
            daily_movements[getdate(row.get("settlement_date"))] += direction * quantity

        position = Decimal("0")
        for settlement_date in sorted(daily_movements):
            position += daily_movements[settlement_date]
            if position < 0:
                frappe.throw(
                    "Transactions would make the position negative on "
                    f"{settlement_date}. Purchases settling that day are included."
                )
