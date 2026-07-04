import frappe
from frappe.utils import getdate
from bond_management.bond_management.utils.accrual import get_accrued_interest
from pyxirr import xirr
from collections import defaultdict


def calculate_future_xirr(isin, date, market_price):
    """
    Calculate the future XIRR for a bond based on its future cash flows.

    :param isin: The ISIN of the bond.
    :param date: The date from which to calculate future cash flows.
    :param market_price: The current market price of the bond.
    :return: The calculated future XIRR as a float.
    """

    # Create future cash flows
    future_cash_flows = create_future_cash_flows(isin, date, market_price)

    # Consolidate cash flows
    consolidated_cash_flows = consolidate_cashflows(future_cash_flows)

    # Extract cash flow amounts and dates
    xirr_value = xirr(consolidated_cash_flows)
    # xirr_value = 0.07

    return xirr_value

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
    """
    Create future cash flows for a bond based on its coupon schedule and market price.

    :param isin: The ISIN of the bond.
    :param date: The date from which to calculate future cash flows.
    :param market_price: The current market price of the bond.
    :return: A list of tuples containing (cash_flow, date) for each future cash flow.
    """

    # Fetch the bond document
    bond_doc = frappe.get_doc("Bond Master", isin)

    # Initialize future cash flows list
    future_cash_flows = []

    # Calculate accrued interest up to the settlement date
    settlement_date = getdate(date)
    accrued_interest = get_accrued_interest(
        isin=isin,
        settlement_date=settlement_date,
        quantity_face_value=1
    )
    # correct the accrued interest based on the principal factor
    accrued_interest = accrued_interest * calculate_principal_factor2(isin, date)
    
    # Add accrued interest as a cash flow on the settlement date
    future_cash_flows.append({"type": "market_price", "date": settlement_date, "amount": -market_price})
    future_cash_flows.append({"type": "accrued_interest", "date": settlement_date, "amount": -accrued_interest})
    
    # Get the coupon schedule and principal schedule from the bond document
    coupon_schedule = bond_doc.get("coupon_schedule")
    principal_schedule = bond_doc.get("principal_schedule")

    # Iterate through the coupon schedule to add future coupon payments
    for coupon_period in coupon_schedule:
        coupon_date = getdate(coupon_period.get("coupon_date"))
        if coupon_date > settlement_date:
            principal_factor = calculate_princlple_factor(principal_schedule, coupon_date)
            interest_factor = (bond_doc.coupon_rate / 100) / int(bond_doc.coupon_frequency) 
            coupon_payment = interest_factor * bond_doc.face_value_per_unit * principal_factor
            future_cash_flows.append({"type": "coupon", "date": coupon_date, "amount": coupon_payment})
    

    
    # Iterate through the principal schedule to add future principal repayments
    for principal_period in principal_schedule:
        repayment_date = getdate(principal_period.get("repayment_date"))
        if repayment_date > settlement_date:
            principal_payment = bond_doc.face_value_per_unit * (principal_period.get("repayment_percent") or 0.0) / 100.0
            future_cash_flows.append({"type": "principal", "date": repayment_date, "amount": principal_payment})

    print("Accrued Interest", accrued_interest)
    print("Market Price", market_price)
    print("Future Cash Flows for ISIN {}: {}".format(isin, future_cash_flows))

    return future_cash_flows
    

def calculate_princlple_factor(principal_schedule, date):
    """
    Calculate the principal factor for a bond based on its principal schedule and settlement date.

    :param principal_schedule: The principal schedule of the bond.
    :param date: The date for which to calculate the principal factor.
    :return: The principal factor as a float.
    """

    settlement_date = getdate(date)
    principal_factor = 1.0

    for period in principal_schedule:
        if settlement_date > period.get("repayment_date"):
            principal_factor = principal_factor - (period.get("repayment_percent") or 0.0) / 100.0

    return principal_factor

def calculate_principal_factor2(isin, date):

    bond_doc = frappe.get_doc("Bond Master", isin)
    principal_schedule = bond_doc.get("principal_schedule")
    principal_factor = calculate_princlple_factor(principal_schedule, date)

    return principal_factor




