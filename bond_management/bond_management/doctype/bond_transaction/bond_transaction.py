# Copyright (c) 2026, Deepak Patel and contributors
# For license information, please see license.txt

from collections import defaultdict
from decimal import Decimal

import frappe
from frappe.model.document import Document
from frappe.utils import getdate

from bond_management.bond_management.utils.accrual import get_accrued_interest
from bond_management.bond_management.utils.financial import (
    DecimalInput,
    quantize_money,
    to_decimal,
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


def _calculate_amount_values(
    bond, settlement_date, quantity_face_value, price, accrued_interest_paid, commission
):
    principal = to_decimal(bond.face_value_per_unit) * to_decimal(quantity_face_value)
    commission_amount = principal * to_decimal(commission) / Decimal("100")
    # The bank transaction price is commission-inclusive, so commission_amount is
    # informational and must not be added to settlement or XIRR cash flows again.
    settlement_amount = (
        principal * to_decimal(price) / Decimal("100") + to_decimal(accrued_interest_paid)
    )
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
    def validate(self):
        self.validate_required_inputs()
        self.set_authoritative_bond_snapshot()
        self.validate_financial_terms()
        self.validate_transaction_dates()
        self.calculate_amounts()
        self.validate_portfolio_ledger()

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
