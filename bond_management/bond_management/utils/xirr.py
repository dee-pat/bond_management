from collections import defaultdict
from decimal import Decimal

import frappe
from frappe.utils import getdate
from pyxirr import InvalidPaymentsError, xirr

from bond_management.bond_management.utils.accrual import (
    calculate_principal_factor_from_bond,
    calculate_quantity_factor_from_bond,
    is_quantity_change_bond,
    unit_accrued_interest_from_bond,
)
from bond_management.bond_management.utils.financial import quantize_money, to_decimal
from bond_management.bond_management.utils.portfolio import (
    get_coupon_position_from_transactions,
    get_ledger_position_from_transactions,
    get_position,
    get_position_for_coupon_payment,
    get_position_for_payment,
)

DEFAULT_XIRR_GUESS = 0.1
PERCENT = Decimal("100")


def round_cashflow_amount(amount):
    """Round a cash-flow amount for the JSON/clipboard serialization boundary."""
    return float(quantize_money(amount))


def round_cashflow_amounts(cash_flows):
    """Apply the cash-flow amount convention without changing other metadata."""
    return [{**cash_flow, "amount": quantize_money(cash_flow["amount"])} for cash_flow in cash_flows]


def apply_withholding_tax(amount, bond_doc):
    """Return a coupon or accrued-interest amount after bond-level tax."""
    withholding_tax = to_decimal(bond_doc.get("withholding_tax"))
    return to_decimal(amount) * (PERCENT - withholding_tax) / PERCENT


def calculate_future_xirr(
    isin,
    date,
    market_price,
    *,
    bond_doc=None,
    historical_guess=None,
):
    future_cash_flows = create_future_cash_flows(isin, date, market_price, bond_doc=bond_doc)
    consolidated_cash_flows = consolidate_cashflows(future_cash_flows)
    guess = historical_guess if historical_guess is not None else get_last_xirr_guess(isin, date)
    if guess is None:
        guess = DEFAULT_XIRR_GUESS
    guess = max(min(guess, 1.0), -0.5)
    return calculate_xirr(consolidated_cash_flows, guess)


def calculate_xirr(cash_flows, guess=DEFAULT_XIRR_GUESS):
    """Return an XIRR value, or ``None`` when cash flows have no valid solution."""
    if len(cash_flows) < 2:
        return None

    try:
        return xirr(_to_pyxirr_cashflows(cash_flows), guess=guess)
    except (ArithmeticError, InvalidPaymentsError, ValueError):
        if guess == DEFAULT_XIRR_GUESS:
            return None

    try:
        return xirr(
            _to_pyxirr_cashflows(cash_flows),
            guess=DEFAULT_XIRR_GUESS,
        )
    except (ArithmeticError, InvalidPaymentsError, ValueError):
        return None


def _to_pyxirr_cashflows(cash_flows):
    """Adapt Decimal cash flows to pyxirr's float-only input contract."""
    return {date: float(amount) for date, amount in cash_flows.items()}


def get_last_xirr_guess(isin, date):
    return get_last_xirr_guesses({isin}, date).get(isin)


def get_last_xirr_guesses(isins, date):
    isins = sorted(set(isins or ()))
    if not isins or not date:
        return {}

    results = frappe.qb.get_query(
        "Bond Market Date",
        fields=["bond_market_prices.isin", "bond_market_prices.future_xirr"],
        filters={"date": ["<=", date], "bond_market_prices.isin": ["in", isins]},
        order_by="date desc, name desc",
        ignore_permissions=False,
    ).run(as_dict=True)

    guesses = {}
    for result in results:
        isin = result.get("isin")
        if isin in guesses or result.get("future_xirr") is None:
            continue
        guesses[isin] = float(to_decimal(result["future_xirr"]) / to_decimal(100))

    return guesses


def consolidate_cashflows(cash_flows):
    consolidated_cash_flows = defaultdict(Decimal)

    for cash_flow in cash_flows:
        if not cash_flow.get("date") or cash_flow.get("amount") is None:
            continue

        cash_flow_date = getdate(cash_flow["date"])
        amount = to_decimal(cash_flow["amount"])

        consolidated_cash_flows[cash_flow_date] += amount

    return dict(consolidated_cash_flows)


def create_future_cash_flows(isin, date, market_price, quantity=1, bond_doc=None):
    # Fetch the bond document
    bond_doc = bond_doc or frappe.get_doc("Bond Master", isin)
    market_price = to_decimal(market_price)
    quantity = to_decimal(quantity)

    # Initialize future cash flows list
    future_cash_flows = []

    # Calculate accrued interest up to the settlement date
    settlement_date = getdate(date)
    quantity_factor = calculate_quantity_factor_from_bond(bond_doc, settlement_date)
    accrued_interest = apply_withholding_tax(
        unit_accrued_interest_from_bond(bond_doc, settlement_date) * quantity_factor,
        bond_doc,
    )

    # Standard bonds use the bank quote per 100 of original face value. KES
    # quantity-change bonds instead reduce the quantity represented by that
    # quote after a repayment.
    future_cash_flows.append(
        {
            "bond": isin,
            "type": "market_price",
            "date": settlement_date,
            "amount": (
                -to_decimal(bond_doc.get("face_value_per_unit"))
                * market_price
                / to_decimal(100)
                * quantity_factor
            ),
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
    maturity_date = getdate(bond_doc.get("maturity_date"))

    # Iterate through the coupon schedule to add future coupon payments
    for coupon_period in coupon_schedule:
        coupon_date = getdate(coupon_period.get("coupon_date"))
        coupon_factor = coupon_period.get("coupon_factor")
        if coupon_date and coupon_factor is not None and coupon_date > settlement_date:
            # On a repayment date this is the pre-payment factor. That day's
            # coupon is paid before the factor affects subsequent coupons.
            coupon_position_factor = (
                calculate_quantity_factor_from_bond(bond_doc, coupon_date, include_repayment_on_date=False)
                if is_quantity_change_bond(bond_doc)
                else calculate_principal_factor_from_bond(
                    bond_doc, coupon_date, include_repayment_on_date=False
                )
            )
            coupon_factor = to_decimal(coupon_factor) / to_decimal(100)
            coupon_payment = apply_withholding_tax(
                coupon_factor * to_decimal(bond_doc.get("face_value_per_unit")) * coupon_position_factor,
                bond_doc,
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
        if repayment_date and repayment_date > settlement_date:
            if is_quantity_change_bond(bond_doc):
                quantity_before = calculate_quantity_factor_from_bond(
                    bond_doc, repayment_date, include_repayment_on_date=False
                )
                quantity_after = calculate_quantity_factor_from_bond(bond_doc, repayment_date)
                repayment_factor = quantity_before - quantity_after
            else:
                repayment_factor = to_decimal(principal_period.get("repayment_percent")) / to_decimal(100)
            principal_payment = to_decimal(bond_doc.get("face_value_per_unit")) * repayment_factor
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
    future_cash_flows = [
        {**cash_flow, "amount": cash_flow["amount"] * quantity, "quantity": quantity}
        for cash_flow in future_cash_flows
        if to_decimal(cash_flow.get("amount")) != 0
    ]
    future_cash_flows = round_cashflow_amounts(future_cash_flows)
    return sorted(future_cash_flows, key=lambda x: x["date"])


def create_past_cash_flows(isin, date, market_price, portfolio, bond_doc=None, transactions=None):
    # Fetch the bond document
    bond_doc = bond_doc or frappe.get_doc("Bond Master", isin)
    market_price = to_decimal(market_price)

    # Initialize past cash flows list
    past_cash_flows = []

    # Calculate accrued interest up to the settlement date
    settlement_date = getdate(date)
    if transactions is None:
        position = get_position(isin, statement_date=date, portfolio_name=portfolio)
    else:
        position = get_ledger_position_from_transactions(transactions, settlement_date)
        if getdate(bond_doc.get("maturity_date")) <= settlement_date:
            position = to_decimal(0)
    accrued_interest = apply_withholding_tax(
        unit_accrued_interest_from_bond(bond_doc, settlement_date),
        bond_doc,
    )

    quantity_factor = calculate_quantity_factor_from_bond(bond_doc, settlement_date)
    # Standard bonds quote per 100 of original face value. KES quantity-change
    # bonds reduce the represented quantity after a repayment.
    past_cash_flows.append(
        {
            "bond": isin,
            "type": "market_price",
            "date": settlement_date,
            "amount": to_decimal(bond_doc.get("face_value_per_unit"))
            * market_price
            / to_decimal(100)
            * quantity_factor
            * position,
            "quantity": position,
        }
    )
    past_cash_flows.append(
        {
            "bond": isin,
            "type": "accrued_interest",
            "date": settlement_date,
            "amount": accrued_interest * quantity_factor * position,
            "quantity": position,
        }
    )

    # Get the coupon schedule and principal schedule from the bond document
    coupon_schedule = bond_doc.get("coupon_schedule")
    principal_schedule = bond_doc.get("principal_schedule")
    maturity_date = getdate(bond_doc.get("maturity_date"))

    # Iterate through the coupon schedule to add past coupon payments
    for coupon_period in coupon_schedule:
        coupon_date = getdate(coupon_period.get("coupon_date"))
        if not coupon_date:
            continue
        coupon_factor = coupon_period.get("coupon_factor")
        if coupon_factor is None:
            continue
        if coupon_date <= settlement_date:
            coupon_position_factor = (
                calculate_quantity_factor_from_bond(bond_doc, coupon_date, include_repayment_on_date=False)
                if is_quantity_change_bond(bond_doc)
                else calculate_principal_factor_from_bond(
                    bond_doc, coupon_date, include_repayment_on_date=False
                )
            )
            coupon_rate = (
                to_decimal(coupon_factor)
                / to_decimal(100)
                * to_decimal(bond_doc.get("face_value_per_unit"))
                * coupon_position_factor
            )
            position = (
                get_position_for_coupon_payment(isin, coupon_date, coupon_rate, portfolio)
                if transactions is None
                else get_coupon_position_from_transactions(transactions, coupon_date, coupon_rate)
            )

            if position > 0:
                past_cash_flows.append(
                    {
                        "bond": isin,
                        "type": "coupon",
                        "date": coupon_date,
                        "amount": apply_withholding_tax(coupon_rate * position, bond_doc),
                        "quantity": position,
                    }
                )

    # Iterate through the principal schedule to add past principal repayments
    for principal_period in principal_schedule:
        repayment_date = getdate(principal_period.get("repayment_date"))
        if not repayment_date:
            continue
        if repayment_date <= settlement_date:
            # Equality belongs to past performance. Same-day settlements occur
            # immediately before payment and participate in the entitlement.
            position = (
                get_position_for_payment(isin, repayment_date, portfolio)
                if transactions is None
                else get_ledger_position_from_transactions(transactions, repayment_date)
            )
            if is_quantity_change_bond(bond_doc):
                quantity_before = calculate_quantity_factor_from_bond(
                    bond_doc, repayment_date, include_repayment_on_date=False
                )
                quantity_after = calculate_quantity_factor_from_bond(bond_doc, repayment_date)
                repayment_factor = quantity_before - quantity_after
            else:
                repayment_factor = to_decimal(principal_period.get("repayment_percent")) / to_decimal(100)
            principal_amount = to_decimal(bond_doc.get("face_value_per_unit")) * repayment_factor * position
            if repayment_date == maturity_date:
                past_cash_flows.append(
                    {
                        "bond": isin,
                        "type": "sale",
                        "date": repayment_date,
                        "amount": principal_amount,
                        "quantity": position,
                    }
                )
            else:
                past_cash_flows.append(
                    {
                        "bond": isin,
                        "type": "amortisation",
                        "date": repayment_date,
                        "amount": principal_amount,
                        "quantity": position,
                    }
                )

    rows = transactions
    if rows is None:
        rows = frappe.qb.get_query(
            "Bond Transaction",
            filters={
                "isin": isin,
                "portfolio_name": portfolio,
                "settlement_date": ["<=", date],
            },
            fields=[
                "transaction_type",
                "settlement_amount",
                "settlement_date",
                "quantity_face_value",
            ],
            ignore_permissions=False,
        ).run(as_dict=True)

    # settlement_amount already contains the commission-inclusive bank price;
    # adding commission_amount here would double-count it in XIRR.
    for row in rows:
        if row["transaction_type"] == "Purchase":
            past_cash_flows.append(
                {
                    "bond": isin,
                    "type": "purchase",
                    "date": row["settlement_date"],
                    "amount": -to_decimal(row["settlement_amount"]),
                    "quantity": row["quantity_face_value"],
                }
            )
        elif row["transaction_type"] == "Sale":
            past_cash_flows.append(
                {
                    "bond": isin,
                    "type": "sale",
                    "date": row["settlement_date"],
                    "amount": to_decimal(row["settlement_amount"]),
                    "quantity": row["quantity_face_value"],
                }
            )
    past_cash_flows = [d for d in past_cash_flows if to_decimal(d.get("amount")) != 0]
    past_cash_flows = round_cashflow_amounts(past_cash_flows)
    return sorted(past_cash_flows, key=lambda x: x["date"])


def calculate_past_xirr(isin, date, market_price, portfolio):
    # Create past cash flows
    past_cash_flows = create_past_cash_flows(isin, date, market_price, portfolio)

    # Consolidate cash flows
    consolidated_cash_flows = consolidate_cashflows(past_cash_flows)

    return calculate_xirr(consolidated_cash_flows)
