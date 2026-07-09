import frappe
from frappe.utils import getdate, add_days
from bond_management.bond_management.utils.accrual import (
    unit_accrued_interest,
    calculate_principal_factor,
)
from pyxirr import xirr
from collections import defaultdict


def calculate_future_xirr(isin, date, market_price):
    # Create future cash flows
    future_cash_flows = create_future_cash_flows(isin, date, market_price)

    # Consolidate cash flows
    consolidated_cash_flows = consolidate_cashflows(future_cash_flows)

    # ---------- SMART GUESS ----------
    guess = get_last_xirr_guess(isin, date)

    if guess is None:
        guess = 0.1

    # Optional: clamp guess to reasonable range
    guess = max(min(guess, 1.0), -0.5)

    # ---------- XIRR ----------
    try:
        xirr_value = xirr(consolidated_cash_flows, guess=guess)
    except Exception:
        try:
            xirr_value = xirr(consolidated_cash_flows, guess=0.1)
        except Exception:
            xirr_value = None

    return xirr_value


def get_last_xirr_guess(isin, date):

    BMP = frappe.qb.DocType("Bond Market Prices")
    BMD = frappe.qb.DocType("Bond Market Date")

    query = (
        frappe.qb.from_(BMP)
        .join(BMD)
        .on(BMP.parent == BMD.name)
        .select(BMP.future_xirr)
        .where((BMP.isin == isin) & (BMP.future_xirr.isnotnull()) & (BMD.date <= date))
        .orderby(BMD.date, order=frappe.qb.desc)
        .limit(1)
    )

    result = query.run(as_dict=True)

    guess = result[0].future_xirr / 100 if result else None

    return guess


def consolidate_cashflows(cash_flows):
    consolidated_cash_flows = defaultdict(float)

    for f in cash_flows:
        if not f.get("date") or f.get("amount") is None:
            continue

        date = getdate(f["date"])
        amount = float(f["amount"] or 0.0)

        consolidated_cash_flows[date] += amount

    return dict(consolidated_cash_flows)


def create_future_cash_flows(isin, date, market_price):
    # Fetch the bond document
    bond_doc = frappe.get_doc("Bond Master", isin)

    # Initialize future cash flows list
    future_cash_flows = []

    # Calculate accrued interest up to the settlement date
    settlement_date = getdate(date)
    accrued_interest = unit_accrued_interest(
        isin=isin, settlement_date=settlement_date,
    )

    # Add accrued interest as a cash flow on the settlement date
    future_cash_flows.append(
        {
            "bond": isin,
            "type": "market_price",
            "date": settlement_date,
            "amount": -market_price,
        }
    )
    future_cash_flows.append(
        {
            "bond": isin,
            "type": "accrued_interest",
            "date": settlement_date,
            "amount": -accrued_interest,
        }
    )

    # Get the coupon schedule and principal schedule from the bond document
    coupon_schedule = bond_doc.get("coupon_schedule")
    principal_schedule = bond_doc.get("principal_schedule")
    maturity_date = bond_doc.get("maturity_date")

    # Iterate through the coupon schedule to add future coupon payments
    for coupon_period in coupon_schedule:
        coupon_date = getdate(coupon_period.get("coupon_date"))
        if coupon_date > settlement_date:
            principal_factor = calculate_principal_factor(isin, coupon_date)
            interest_factor = (bond_doc.coupon_rate / 100) / int(
                bond_doc.coupon_frequency
            )
            coupon_payment = (
                interest_factor * bond_doc.face_value_per_unit * principal_factor
            )
            future_cash_flows.append(
                {
                    "bond": isin,
                    "type": "coupon",
                    "date": coupon_date,
                    "amount": coupon_payment,
                }
            )

    # Iterate through the principal schedule to add future principal repayments
    for principal_period in principal_schedule:
        repayment_date = getdate(principal_period.get("repayment_date"))
        if repayment_date > settlement_date:
            principal_payment = (
                bond_doc.face_value_per_unit
                * (principal_period.get("repayment_percent") or 0.0)
                / 100.0
            )
            if repayment_date == maturity_date:
                future_cash_flows.append(
                    {
                        "bond": isin,
                        "type": "sale",
                        "date": repayment_date,
                        "amount": principal_payment,
                    }
                )
            else:
                future_cash_flows.append(
                    {
                        "bond": isin,
                        "type": "amortisation",
                        "date": repayment_date,
                        "amount": principal_payment,
                    }
            )
    future_cash_flows = [d for d in future_cash_flows if d.get('amount') != 0.0]
    return sorted(future_cash_flows, key=lambda x: x['date'])


def create_past_cash_flows(isin, date, market_price, portfolio):
    # Fetch the bond document
    bond_doc = frappe.get_doc("Bond Master", isin)

    # Initialize past cash flows list
    past_cash_flows = []

    # Calculate accrued interest up to the settlement date
    settlement_date = getdate(date)
    position = get_position(isin, statement_date=date, portfolio_name=portfolio)
    accrued_interest = unit_accrued_interest(
        isin=isin, settlement_date=settlement_date,
    )

    # Add accrued interest as a cash flow on the settlement date
    past_cash_flows.append(
        {
            "bond": isin,
            "type": "market_price",
            "date": settlement_date,
            "amount": market_price * position,
        }
    )
    past_cash_flows.append(
        {
            "bond": isin,
            "type": "accrued_interest",
            "date": settlement_date,
            "amount": accrued_interest * position,
        }
    )

    # Get the coupon schedule and principal schedule from the bond document
    coupon_schedule = bond_doc.get("coupon_schedule")
    principal_schedule = bond_doc.get("principal_schedule")
    maturity_date = bond_doc.get("maturity_date")

    # Iterate through the coupon schedule to add past coupon payments
    for coupon_period in coupon_schedule:
        coupon_date = getdate(coupon_period.get("coupon_date"))
        position = get_position(
            isin, statement_date=coupon_date, portfolio_name=portfolio
        )
        if coupon_date <= settlement_date:
            principal_factor = calculate_principal_factor(isin, coupon_date)
            interest_factor = (bond_doc.coupon_rate / 100) / int(
                bond_doc.coupon_frequency
            )
            coupon_rate = (
                interest_factor
                * bond_doc.face_value_per_unit
                * principal_factor
            )
            if coupon_date == maturity_date:
                position = get_position(
                        isin, statement_date=add_days(coupon_date, days=-1), portfolio_name=portfolio
                    )
                print("\n New Coupon Date:", add_days(coupon_date, days=-1),"\n")
                past_cash_flows.append(
                    {
                        "bond": isin,
                        "type": "coupon",
                        "date": coupon_date,
                        "amount": coupon_rate * position,
                    }
                )
            elif position > 0:
                past_cash_flows.append(
                    {
                        "bond": isin,
                        "type": "coupon",
                        "date": coupon_date,
                        "amount": coupon_rate * position,
                    }
            )

    # Iterate through the principal schedule to add past principal repayments
    for principal_period in principal_schedule:
        repayment_date = getdate(principal_period.get("repayment_date"))
        position = get_position(
            isin, statement_date=repayment_date, portfolio_name=portfolio
        )
        if repayment_date <= settlement_date:
            principal_amount = (
                bond_doc.face_value_per_unit
                * (principal_period.get("repayment_percent") or 0.0)
                / 100.0 * position
            )
            if repayment_date == maturity_date:
                past_cash_flows.append(
                    {
                        "bond": isin,
                        "type": "sale",
                        "date": repayment_date,
                        "amount": principal_amount,
                    }
                )
            else:
                past_cash_flows.append(
                    {
                        "bond": isin,
                        "type": "amortisation",
                        "date": repayment_date,
                        "amount": principal_amount,
                    }
            )

    rows = frappe.get_all(
        "Bond Transaction",
        filters={
            "isin": isin,
            "portfolio_name": portfolio,
            "settlement_date": ["<=", date],
            # "docstatus": 1
        },
        fields=["transaction_type", "settlement_amount", "settlement_date"],
    )

    for r in rows:
        if r.transaction_type == "Purchase":
            past_cash_flows.append(
                {
                    "bond": isin,
                    "type": "purchase",
                    "date": r.settlement_date,
                    "amount": -r.settlement_amount,
                }
            )
        elif r.transaction_type == "Sale":
            past_cash_flows.append(
                {
                    "bond": isin,
                    "type": "sale",
                    "date": r.settlement_date,
                    "amount": r.settlement_amount,
                }
            )
    past_cash_flows = [d for d in past_cash_flows if d.get('amount') != 0.0]
    return sorted(past_cash_flows, key=lambda x: x['date'])


def get_position(isin, statement_date, portfolio_name):
    rows = frappe.get_all(
        "Bond Transaction",
        filters={
            "isin": isin,
            "portfolio_name": portfolio_name,
            "settlement_date": ["<=", statement_date],
            # "docstatus": 1
        },
        fields=["transaction_type", "quantity_face_value", "maturity_date"],
    )

    position = 0

    for r in rows:
        if r.maturity_date and getdate(r.maturity_date) <= getdate(statement_date):
            return 0  # Bond has matured, no further transactions affect position
        if r.transaction_type == "Purchase":
            position = position + r.quantity_face_value
        elif r.transaction_type == "Sale":
            position = position - r.quantity_face_value

    return position


def calculate_past_xirr(isin, date, market_price, portfolio):
    # Create past cash flows
    past_cash_flows = create_past_cash_flows(isin, date, market_price, portfolio)

    # Consolidate cash flows
    consolidated_cash_flows = consolidate_cashflows(past_cash_flows)

    # ---------- SMART GUESS ----------
    #guess = get_last_xirr_guess(isin, date) # chnage this for future 

    #if guess is None:
    #    guess = 0.1

    # Optional: clamp guess to reasonable range
    #guess = max(min(guess, 1.0), -0.5)

    guess = 0.1

    # ---------- XIRR ----------
    try:
        xirr_value = xirr(consolidated_cash_flows, guess=guess)
    except Exception:
        try:
            xirr_value = xirr(consolidated_cash_flows, guess=0.1)
        except Exception:
            xirr_value = None

    return xirr_value