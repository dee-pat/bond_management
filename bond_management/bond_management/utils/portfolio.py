import frappe
from frappe.utils import getdate

from bond_management.bond_management.utils.financial import to_decimal


def get_position(
    isin,
    statement_date,
    portfolio_name,
    exclude_name=None,
):
    """Return the end-of-day position, after maturity redemption on that date."""
    statement_date = getdate(statement_date)
    position = _get_ledger_position(isin, statement_date, portfolio_name, exclude_name=exclude_name)

    maturity_dates = frappe.qb.get_query(
        "Bond Master",
        filters={"name": isin},
        fields=["maturity_date"],
        ignore_permissions=False,
    ).run(pluck=True)
    if maturity_dates and getdate(maturity_dates[0]) <= statement_date:
        return 0

    return position


def get_position_for_payment(isin, payment_date, portfolio_name):
    """Return the position immediately before a coupon or principal payment.

    Settlement is ordered before cash payments within the day, so transactions
    settling exactly on ``payment_date`` participate in that day's entitlement.
    Unlike :func:`get_position`, maturity redemption is not applied here.
    """
    return _get_ledger_position(isin, payment_date, portfolio_name)


def get_position_for_coupon_payment(isin, coupon_date, coupon_per_unit, portfolio_name):
    """Return the position entitled to a coupon on ``coupon_date``.

    Holdings acquired before the coupon date receive the coupon and holdings
    sold on that date retain it. A purchase settling on the coupon date is
    entitled only where the recorded accrued-interest payment covers that
    purchase's full scheduled coupon. This reflects the bank settlement rather
    than assuming that all same-day settlements occur before the payment.
    """
    coupon_date = getdate(coupon_date)
    coupon_per_unit = to_decimal(coupon_per_unit)
    rows = frappe.qb.get_query(
        "Bond Transaction",
        filters={
            "isin": isin,
            "portfolio_name": portfolio_name,
            "settlement_date": ["<=", coupon_date],
        },
        fields=[
            "transaction_type",
            "quantity_face_value",
            "settlement_date",
            "accrued_interest_paid",
        ],
        ignore_permissions=False,
    ).run(as_dict=True)

    return get_coupon_position_from_transactions(rows, coupon_date, coupon_per_unit)


def get_coupon_position_from_transactions(rows, coupon_date, coupon_per_unit):
    """Calculate coupon entitlement from already-fetched ledger rows."""
    coupon_date = getdate(coupon_date)
    coupon_per_unit = to_decimal(coupon_per_unit)
    position = to_decimal(0)
    for row in rows:
        quantity = to_decimal(row.get("quantity_face_value"))
        settlement_date = getdate(row.get("settlement_date"))

        if settlement_date < coupon_date:
            position += quantity if row.get("transaction_type") == "Purchase" else -quantity
        elif settlement_date == coupon_date and row.get("transaction_type") == "Purchase":
            full_coupon = coupon_per_unit * quantity
            if to_decimal(row.get("accrued_interest_paid")) >= full_coupon:
                position += quantity

    return position


def _get_ledger_position(isin, statement_date, portfolio_name, exclude_name=None):
    statement_date = getdate(statement_date)
    rows = frappe.qb.get_query(
        "Bond Transaction",
        filters={
            "isin": isin,
            "portfolio_name": portfolio_name,
            "settlement_date": ["<=", statement_date],
        },
        fields=["name", "transaction_type", "quantity_face_value", "settlement_date"],
        ignore_permissions=False,
    ).run(as_dict=True)

    return get_ledger_position_from_transactions(rows, statement_date, exclude_name=exclude_name)


def get_ledger_position_from_transactions(rows, statement_date, exclude_name=None):
    """Calculate an end-of-day ledger position without additional database reads."""
    statement_date = getdate(statement_date)
    position = to_decimal(0)
    for row in rows:
        if row.get("name") == exclude_name or getdate(row.get("settlement_date")) > statement_date:
            continue
        if row.get("transaction_type") == "Purchase":
            position += to_decimal(row.get("quantity_face_value"))
        elif row.get("transaction_type") == "Sale":
            position -= to_decimal(row.get("quantity_face_value"))

    return position


def get_portfolio_bonds(portfolio_name):
    return frappe.qb.get_query(
        "Bond Transaction",
        filters={"portfolio_name": portfolio_name},
        distinct=True,
        fields=["isin"],
        ignore_permissions=False,
    ).run(pluck=True)


def fetch_holdings(portfolio_name, statement_date):
    holdings = []
    for isin in get_portfolio_bonds(portfolio_name):
        quantity = get_position(isin, statement_date, portfolio_name)
        if not quantity:
            continue

        bond = frappe.get_doc("Bond Master", isin)
        holdings.append({"isin": bond.name, "quantity": quantity, "currency": bond.currency})

    return holdings
