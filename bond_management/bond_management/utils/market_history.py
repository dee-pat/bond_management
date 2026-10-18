"""Permission-aware lookups over persisted Bond Market Date history."""

from collections.abc import Callable, Iterable
from typing import Any

import frappe
from frappe.utils.data import DateTimeLikeObject
from pypika import Table
from pypika.analytics import RowNumber
from pypika.enums import Order
from pypika.terms import Criterion

_RANK = "market_rank"


def latest_market_rows(
    isins: Iterable[str],
    on_or_before: DateTimeLikeObject,
    fields: Iterable[str],
    *,
    filters: dict[str, Any] | None = None,
    where: Callable[[Table], Criterion] | None = None,
) -> list[frappe._dict]:
    """Return the latest market-price row per ISIN dated on or before ``on_or_before``.

    ``fields`` are Bond Market Prices columns returned with ``isin``. Ties on
    date resolve to the latest Bond Market Date name, as everywhere else.
    Rows are limited to Bond Market Dates the session user can read.
    """
    market_date = frappe.qb.DocType("Bond Market Date")
    market_price = frappe.qb.DocType("Bond Market Prices")
    rank = (
        RowNumber()
        .over(market_price.isin)
        .orderby(market_date.date, order=Order.desc)
        .orderby(market_date.name, order=Order.desc)
        .as_(_RANK)
    )
    columns = ("isin", *fields)
    ranked_query = frappe.qb.get_query(
        "Bond Market Date",
        fields=[*(f"bond_market_prices.{column} as {column}" for column in columns), rank],
        filters={
            "date": ["<=", on_or_before],
            "bond_market_prices.isin": ["in", list(isins)],
            **(filters or {}),
        },
        ignore_permissions=False,
    )
    if where is not None:
        ranked_query = ranked_query.where(where(market_price))
    ranked = ranked_query.as_("ranked_market")
    return (
        frappe.qb.from_(ranked).select(*(ranked[column] for column in columns)).where(ranked[_RANK] == 1)
    ).run(as_dict=True)
