from collections.abc import Iterable
from datetime import date

import frappe

from bond_management.bond_management.utils.financial import to_decimal
from bond_management.bond_management.utils.statement_pdf import ParsedMarketPrice


def sync_statement_market_prices(
    statement_date: date | str,
    market_prices: Iterable[ParsedMarketPrice],
):
    """Upsert PDF prices into the single Bond Market Date for the statement date."""
    market_prices = tuple(market_prices)
    if not market_prices:
        return None

    market_prices = _filter_visible_bonds(market_prices)
    if not market_prices:
        return None

    existing = frappe.qb.get_query(
        "Bond Market Date",
        fields=["name"],
        filters={"date": statement_date},
        limit=1,
        for_update=True,
        ignore_permissions=False,
    ).run(pluck=True)

    if not existing:
        market_date = frappe.get_doc(
            {
                "doctype": "Bond Market Date",
                "date": statement_date,
                "bond_market_prices": [
                    {
                        "isin": price.isin,
                        "market_price": price.market_price,
                    }
                    for price in market_prices
                ],
            }
        )
        market_date.check_permission("create")
        return market_date.insert()

    market_date = frappe.get_doc("Bond Market Date", existing[0])
    market_date.check_permission("write")
    rows_by_isin = {row.isin: row for row in market_date.bond_market_prices}
    changed = False

    for price in market_prices:
        row = rows_by_isin.get(price.isin)
        if row is None:
            market_date.append(
                "bond_market_prices",
                {
                    "isin": price.isin,
                    "market_price": price.market_price,
                },
            )
            changed = True
        elif to_decimal(row.market_price) != price.market_price:
            row.market_price = price.market_price
            changed = True

    return market_date.save() if changed else market_date


def _filter_visible_bonds(
    market_prices: tuple[ParsedMarketPrice, ...],
) -> tuple[ParsedMarketPrice, ...]:
    """Ignore statement holdings that are not represented by an accessible Bond Master."""
    isins = [price.isin for price in market_prices]
    visible_isins = set(
        frappe.qb.get_query(
            "Bond Master",
            fields=["name"],
            filters={"name": ["in", isins]},
            ignore_permissions=False,
        ).run(pluck=True)
    )
    return tuple(price for price in market_prices if price.isin in visible_isins)
