# Copyright (c) 2026, Deepak Patel and contributors
# For license information, please see license.txt

import frappe
from frappe import _
from frappe.model.document import Document
from frappe.utils import escape_html, getdate

from bond_management.bond_management.utils.accrual import (
    calculate_principal_factor_from_bond,
    calculate_quantity_factor_from_bond,
)
from bond_management.bond_management.utils.financial import to_decimal
from bond_management.bond_management.utils.performance import load_portfolio_performance_context
from bond_management.bond_management.utils.portfolio import (
    get_ledger_position_from_transactions,
)
from bond_management.bond_management.utils.statement_attachment import (
    standardize_statement_attachment,
)
from bond_management.bond_management.utils.statement_exchange_rates import (
    delete_statement_exchange_rates,
    sync_statement_exchange_rates,
)
from bond_management.bond_management.utils.statement_market_prices import (
    sync_statement_market_prices,
)
from bond_management.bond_management.utils.statement_pdf import (
    get_statement_attachment_details,
)
from bond_management.bond_management.utils.statement_quantity_reconciliation import (
    format_quantity,
    reconcile_statement_quantities,
)
from bond_management.bond_management.utils.statement_quantity_report import (
    attach_quantity_reconciliation_report,
)


class BondStatement(Document):
    def before_validate(self):
        if self.flags.ignore_statement_pdf:
            return

        attachment_changed = self.is_new() or self.has_value_changed("attachment")
        if attachment_changed:
            self._set_details_from_attachment()
            return

        previous = self.get_doc_before_save()
        if previous and (
            previous.portfolio_name != self.portfolio_name
            or getdate(previous.statement_date) != getdate(self.statement_date)
            or previous.market_price_posting != self.market_price_posting
            or previous.quantity_reconciliation_report != self.quantity_reconciliation_report
        ):
            frappe.throw(
                _(
                    "Portfolio Name, Statement Date, Market Price Posting, and Quantity "
                    "Reconciliation Report are managed from the attached PDF. Attach the correct "
                    "PDF instead of editing these fields."
                )
            )

        details = get_statement_attachment_details(self.attachment, self.portfolio_name)
        if details.portfolio_name != self.portfolio_name or getdate(details.statement_date) != getdate(
            self.statement_date
        ):
            frappe.throw(
                _(
                    "The attached PDF no longer matches this Bond Statement's portfolio and date. "
                    "Attach the correct PDF before saving."
                )
            )
        self.flags.statement_attachment_details = details

    def validate(self):
        self.populate_holdings()
        self._apply_attachment_market_prices()
        self._reconcile_attachment_quantities()

    def before_save(self):
        details = self.flags.statement_attachment_details
        if not details:
            return

        self.attachment = standardize_statement_attachment(
            self,
            details.portfolio_account_no,
            details.statement_date,
        )
        self._validate_unique_attachment()
        market_date = sync_statement_market_prices(
            details.statement_date,
            details.market_prices,
        )
        self.market_price_posting = market_date.name if market_date else None

    def _validate_unique_attachment(self):
        existing = frappe.qb.get_query(
            "Bond Statement",
            fields=["name"],
            filters=[
                ["attachment", "=", self.attachment],
                ["name", "!=", self.name],
            ],
            limit=1,
            # Attachment uniqueness is a system-wide integrity rule. A statement
            # hidden by portfolio permissions must still prevent a duplicate.
            ignore_permissions=True,
        ).run(pluck=True)
        if existing:
            frappe.throw(
                f"This PDF attachment is already used by Bond Statement {frappe.bold(escape_html(existing[0]))}."
            )

    def on_update(self):
        details = self.flags.statement_attachment_details
        if not details:
            return

        sync_statement_exchange_rates(self, details.exchange_rates)
        report_url = attach_quantity_reconciliation_report(
            self,
            self.flags.quantity_reconciliation_comparisons or (),
            file_name=self.flags.quantity_reconciliation_report_file_name,
        )
        self.db_set("quantity_reconciliation_report", report_url, update_modified=False)
        if not self.flags.suppress_quantity_reconciliation_message:
            self._report_quantity_mismatches()

    def on_trash(self):
        delete_statement_exchange_rates(self.name)

    @frappe.whitelist(methods=["POST"])
    def read_statement_pdf(self):
        """Preview the portfolio and date extracted from the current attachment."""
        self.check_permission("create" if self.is_new() else "write")
        details = get_statement_attachment_details(self.attachment, self.portfolio_name)
        return {
            "portfolio_name": details.portfolio_name,
            "statement_date": details.statement_date,
            "account_no": details.account_no,
            "exchange_rates": [
                {
                    "from_currency": row.from_currency,
                    "to_currency": row.to_currency,
                    "rate": row.rate,
                }
                for row in details.exchange_rates
            ],
        }

    def _set_details_from_attachment(self):
        details = get_statement_attachment_details(self.attachment, self.portfolio_name)
        self.flags.statement_attachment_details = details
        self.portfolio_name = details.portfolio_name
        self.statement_date = details.statement_date

    def _apply_attachment_market_prices(self):
        details = self.flags.statement_attachment_details
        if not details:
            return

        prices_by_isin = {
            market_price.isin: market_price.market_price for market_price in details.market_prices
        }
        missing_isins = [row.isin for row in self.bond_statement_details if row.isin not in prices_by_isin]
        if missing_isins:
            frappe.throw(
                "Could not find fixed-income market prices in the attached PDF for: "
                f"{', '.join(missing_isins)}"
            )

        for row in self.bond_statement_details:
            row.market_price = prices_by_isin[row.isin]

    def _reconcile_attachment_quantities(self):
        details = self.flags.statement_attachment_details
        if not details:
            self.flags.quantity_reconciliation_comparisons = ()
            self.flags.quantity_reconciliation_mismatches = ()
            self.reconciliation_status = None
            return

        comparisons = reconcile_statement_quantities(
            details.market_prices,
            self.bond_statement_details,
            calculated_quantities=self.flags.matured_calculated_quantities,
        )
        self.flags.quantity_reconciliation_comparisons = comparisons
        self.flags.quantity_reconciliation_mismatches = tuple(
            comparison for comparison in comparisons if not comparison.matches
        )
        self.reconciliation_status = (
            "Mismatched" if self.flags.quantity_reconciliation_mismatches else "Matched"
        )

    def _report_quantity_mismatches(self):
        mismatches = self.flags.quantity_reconciliation_mismatches or ()
        if not mismatches:
            return

        rows = [["ISIN", "PDF Quantity", "Calculated Quantity", "Difference"]]
        rows.extend(
            [
                mismatch.isin,
                format_quantity(mismatch.pdf_quantity),
                format_quantity(mismatch.calculated_quantity),
                format_quantity(mismatch.difference),
            ]
            for mismatch in mismatches
        )
        frappe.msgprint(
            rows,
            title=f"Bond Quantity Mismatch - {self.portfolio_name} - {self.statement_date}",
            as_table=True,
            indicator="orange",
            wide=True,
        )

    def populate_holdings(self):
        # Clear generated rows first so cleared inputs cannot retain old holdings.
        self.set("bond_statement_details", [])

        if not self.portfolio_name or not self.statement_date:
            return

        context = load_portfolio_performance_context(self.portfolio_name, self.statement_date)
        self.flags.matured_calculated_quantities = {}
        for isin in context["isins"]:
            bond = context["bonds"][isin]
            quantity = get_ledger_position_from_transactions(
                context["transactions"][isin], self.statement_date
            )
            is_matured = getdate(bond.maturity_date) <= getdate(self.statement_date)
            if is_matured:
                quantity = to_decimal(0)
                self.flags.matured_calculated_quantities[isin] = quantity
            if not quantity:
                continue

            market_price = context["market_prices"].get(isin)
            quantity *= calculate_quantity_factor_from_bond(bond, self.statement_date)
            principal_factor = calculate_principal_factor_from_bond(bond, self.statement_date)

            self.append(
                "bond_statement_details",
                {
                    "isin": isin,
                    "quantity": quantity,
                    "currency": bond.currency,
                    "market_price": market_price,
                    "principal_factor": principal_factor,
                },
            )
