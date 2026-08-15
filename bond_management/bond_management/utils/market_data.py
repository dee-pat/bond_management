import frappe

from bond_management.bond_management.utils.accrual import (
    calculate_principal_factor_from_bond,
    calculate_weighted_average_repayment,
)
from bond_management.bond_management.utils.xirr import calculate_future_xirr


def calculate_market_data(date, isin, market_price, *, historical_guess=None):
    """Calculate market-row values without depending on a DocType controller."""
    values = {
        "currency": None,
        "future_xirr": None,
        "principal_factor": None,
        "weighted_avg_repayment_date": None,
        "weighted_avg_repayment_years": None,
        "maturity_date": None,
    }
    if not isin:
        return values

    bond_doc = frappe.get_doc("Bond Master", isin)
    values["currency"] = bond_doc.get("currency")
    values["maturity_date"] = bond_doc.get("maturity_date")

    if not date:
        return values

    values["principal_factor"] = calculate_principal_factor_from_bond(bond_doc, date)
    weighted_date, weighted_years = calculate_weighted_average_repayment(
        bond_doc.get("principal_schedule"), date
    )
    values["weighted_avg_repayment_date"] = weighted_date
    values["weighted_avg_repayment_years"] = weighted_years
    if market_price is None:
        return values

    future_xirr = calculate_future_xirr(
        isin,
        date,
        market_price,
        bond_doc=bond_doc,
        historical_guess=historical_guess,
    )
    values["future_xirr"] = future_xirr * 100 if future_xirr is not None else None
    return values
