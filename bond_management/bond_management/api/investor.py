"""Read-only API contracts for the investor SPA."""

from contextlib import AbstractContextManager, nullcontext

import frappe
from frappe import _

# Keep established dotted API paths while report adapters live in a focused module.
from bond_management.bond_management.api.investor_reports import (
    get_bond_yield_comparison,
    get_interest_difference_by_portfolio,
    get_portfolio_performance,
    get_portfolio_performance_cashflows,
    get_yield_comparison_defaults,
)
from bond_management.bond_management.utils.investor_access import is_readable
from bond_management.bond_management.utils.investor_access import (
    require_readable_portfolio as _require_readable_portfolio,
)
from bond_management.bond_management.utils.investor_permissions import (
    get_allowed_portfolios,
    include_shared_exchange_rates_in_safe_projection,
)
from bond_management.bond_management.utils.investor_ui import (
    get_investor_user_context,
    require_investor_ui_access,
    set_investor_api_data,
)
from bond_management.bond_management.utils.validation import optional_string, required_string

DEFAULT_PAGE_LENGTH = 20
MAX_PAGE_LENGTH = 50
MAX_PAGE_START = 10_000
TRANSACTION_LIST_FIELDS = (
    "name",
    "settlement_date",
    "transaction_type",
    "portfolio_name",
    "isin",
    "trade_date",
    "quantity_face_value",
    "price",
)
TRANSACTION_DETAIL_FIELDS = (
    "transaction_type",
    "portfolio_name",
    "isin",
    "bond_name",
    "account_number",
    "transaction_reference",
    "trade_date",
    "settlement_date",
    "quantity_face_value",
    "price",
    "principal",
    "commission",
    "accrued_interest_calculated",
    "accrued_interest_paid",
    "currency",
    "maturity_date",
    "coupon_frequency",
    "coupon_rate",
    "face_value_per_unit",
    "issue_date",
    "day_count_convention",
    "commission_amount",
    "settlement_amount",
    "transaction_amount",
    "attachment",
)
STATEMENT_LIST_FIELDS = (
    "name",
    "statement_date",
    "portfolio_name",
    "reconciliation_status",
)
STATEMENT_SCALAR_FIELDS = (
    "portfolio_name",
    "statement_date",
    "market_price_posting",
    "reconciliation_status",
    "attachment",
    "quantity_reconciliation_report",
)
STATEMENT_DETAIL_FIELDS = (*STATEMENT_SCALAR_FIELDS, "bond_statement_details")
STATEMENT_HOLDING_FIELDS = (
    "isin",
    "quantity",
    "principal_factor",
    "market_price",
    "currency",
)
STATEMENT_RECONCILIATION_STATUSES = {"Matched", "Mismatched"}
BOND_LIST_FIELDS = (
    "name",
    "bond_name",
    "isin",
    "currency",
    "issue_date",
)
BOND_SCALAR_FIELDS = (
    "bond_name",
    "isin",
    "issue_date",
    "first_coupon_date",
    "face_value_per_unit",
    "coupon_frequency",
    "bond_type",
    "maturity_date",
    "currency",
    "coupon_rate",
    "withholding_tax",
    "day_count_convention",
    "quantity_change",
)
BOND_DETAIL_FIELDS = (*BOND_SCALAR_FIELDS, "principal_schedule", "coupon_schedule")
BOND_PRINCIPAL_FIELDS = ("repayment_date", "principal_units", "repayment_percent")
BOND_COUPON_FIELDS = ("coupon_date", "period_start", "period_end", "coupon_factor")
MARKET_DATE_LIST_FIELDS = ("name", "date")
MARKET_DATE_SCALAR_FIELDS = ("date",)
MARKET_DATE_DETAIL_FIELDS = (*MARKET_DATE_SCALAR_FIELDS, "bond_market_prices")
MARKET_PRICE_FIELDS = (
    "isin",
    "principal_factor",
    "market_price",
    "currency",
    "future_xirr",
    "future_xirr_available",
    "weighted_avg_repayment_date",
    "weighted_avg_repayment_years",
    "maturity_date",
)
EXCHANGE_RATE_LIST_FIELDS = (
    "name",
    "rate_date",
    "from_currency",
    "to_currency",
    "rate",
    "reverse_rate",
)


# Click-to-filter columns. Frozensets keep these out of the response allowlists.
TRANSACTION_FILTER_FIELDS = frozenset({"transaction_type", "isin", "quantity_face_value", "price"})
BOND_FILTER_FIELDS = frozenset({"bond_name", "isin", "currency"})
EXCHANGE_RATE_FILTER_FIELDS = frozenset({"from_currency", "to_currency", "rate", "reverse_rate"})
# The private statement link is added only after its own read check.
EXCHANGE_RATE_SCALAR_FIELDS = (
    "rate_date",
    "from_currency",
    "to_currency",
    "source",
    "rate",
    "reverse_rate",
)
EXCHANGE_RATE_DETAIL_FIELDS = (*EXCHANGE_RATE_SCALAR_FIELDS, "statement")


@frappe.whitelist(methods=["GET"])
def get_bootstrap() -> dict:
    """Return the authenticated shell context and allowed portfolio choices."""
    require_investor_ui_access()

    allowed_portfolios = get_allowed_portfolios(frappe.session.user)
    portfolio_choices = []
    if allowed_portfolios is None or allowed_portfolios:
        portfolio_rows = frappe.qb.get_query(
            "Bond Portfolio",
            fields=["name", "portfolio_name"],
            filters={} if allowed_portfolios is None else {"name": ["in", allowed_portfolios]},
            order_by="portfolio_name asc, name asc",
            ignore_permissions=False,
        ).run(as_dict=True)
        portfolio_choices = [{"name": row.name, "label": row.portfolio_name} for row in portfolio_rows]

    return set_investor_api_data({**get_investor_user_context(), "portfolios": portfolio_choices})


@frappe.whitelist(methods=["GET"])
def get_transactions(
    portfolio: str | None = None,
    start: int | str | None = None,
    page_length: int | str | None = None,
    sort_by: str | None = None,
    sort_order: str | None = None,
    filter_field: str | None = None,
    filter_value: str | None = None,
) -> dict:
    """Return one permission-scoped page of the Desk transaction projection."""
    require_investor_ui_access()

    portfolio = optional_string(portfolio, "Portfolio")
    filters = {}
    if portfolio:
        _require_readable_portfolio(portfolio)
        filters["portfolio_name"] = portfolio

    return _paged_list(
        "Bond Transaction",
        TRANSACTION_LIST_FIELDS,
        filters=filters,
        start=start,
        page_length=page_length,
        sort_by=sort_by,
        sort_order=sort_order,
        filter_field=filter_field,
        filter_value=filter_value,
        filter_fields=TRANSACTION_FILTER_FIELDS,
        default_order="settlement_date desc, name desc",
    )


@frappe.whitelist(methods=["GET"])
def get_transaction(name: str) -> dict:
    """Return one permission-scoped transaction, including its private PDF URL."""
    require_investor_ui_access()
    name = required_string(name, "Transaction")
    transaction = _fetch_one(
        "Bond Transaction",
        TRANSACTION_DETAIL_FIELDS,
        name,
        _("You are not permitted to read this transaction."),
    )
    return set_investor_api_data({"transaction": transaction})


@frappe.whitelist(methods=["GET"])
def get_statements(
    portfolio: str | None = None,
    reconciliation_status: str | None = None,
    start: int | str | None = None,
    page_length: int | str | None = None,
    sort_by: str | None = None,
    sort_order: str | None = None,
    filter_field: str | None = None,
    filter_value: str | None = None,
) -> dict:
    """Return one permission-scoped page of the Desk statement projection."""
    require_investor_ui_access()

    portfolio = optional_string(portfolio, "Portfolio")
    reconciliation_status = optional_string(reconciliation_status, "Reconciliation status")
    if reconciliation_status and reconciliation_status not in STATEMENT_RECONCILIATION_STATUSES:
        frappe.throw(_("Reconciliation status must be Matched or Mismatched."))

    filters = {}
    if portfolio:
        _require_readable_portfolio(portfolio)
        filters["portfolio_name"] = portfolio
    if reconciliation_status:
        filters["reconciliation_status"] = reconciliation_status

    return _paged_list(
        "Bond Statement",
        STATEMENT_LIST_FIELDS,
        filters=filters,
        start=start,
        page_length=page_length,
        sort_by=sort_by,
        sort_order=sort_order,
        filter_field=filter_field,
        filter_value=filter_value,
        default_order="statement_date desc, name desc",
    )


@frappe.whitelist(methods=["GET"])
def get_statement(name: str) -> dict:
    """Return one permission-scoped statement with its PDF and report URLs."""
    require_investor_ui_access()
    name = required_string(name, "Statement")
    statement = _fetch_one(
        "Bond Statement",
        STATEMENT_SCALAR_FIELDS,
        name,
        _("You are not permitted to read this statement."),
    )
    statement["bond_statement_details"] = _checked_child_rows(
        "Bond Statement", name, "bond_statement_details", STATEMENT_HOLDING_FIELDS
    )
    return set_investor_api_data({"statement": statement})


@frappe.whitelist(methods=["GET"])
def get_bonds(
    start: int | str | None = None,
    page_length: int | str | None = None,
    sort_by: str | None = None,
    sort_order: str | None = None,
    filter_field: str | None = None,
    filter_value: str | None = None,
) -> dict:
    """Return one permission-scoped page of the Desk Bond Master projection."""
    require_investor_ui_access()
    return _paged_list(
        "Bond Master",
        BOND_LIST_FIELDS,
        start=start,
        page_length=page_length,
        sort_by=sort_by,
        sort_order=sort_order,
        filter_field=filter_field,
        filter_value=filter_value,
        filter_fields=BOND_FILTER_FIELDS,
        default_order="issue_date desc, name desc",
    )


@frappe.whitelist(methods=["GET"])
def get_bond(name: str) -> dict:
    """Return one permission-scoped Bond Master with visible schedules."""
    require_investor_ui_access()
    name = required_string(name, "Bond")
    bond = _fetch_one("Bond Master", BOND_SCALAR_FIELDS, name, _("You are not permitted to read this bond."))
    bond["principal_schedule"] = _checked_child_rows(
        "Bond Master", name, "principal_schedule", BOND_PRINCIPAL_FIELDS
    )
    bond["coupon_schedule"] = _checked_child_rows("Bond Master", name, "coupon_schedule", BOND_COUPON_FIELDS)
    return set_investor_api_data({"bond": bond})


@frappe.whitelist(methods=["GET"])
def get_market_dates(
    start: int | str | None = None,
    page_length: int | str | None = None,
    sort_by: str | None = None,
    sort_order: str | None = None,
    filter_field: str | None = None,
    filter_value: str | None = None,
) -> dict:
    """Return one permission-scoped page of Bond Market Date history."""
    require_investor_ui_access()
    return _paged_list(
        "Bond Market Date",
        MARKET_DATE_LIST_FIELDS,
        start=start,
        page_length=page_length,
        sort_by=sort_by,
        sort_order=sort_order,
        filter_field=filter_field,
        filter_value=filter_value,
        default_order="date desc, name desc",
    )


@frappe.whitelist(methods=["GET"])
def get_market_date(name: str) -> dict:
    """Return one permission-scoped market date with persisted market rows."""
    require_investor_ui_access()
    name = required_string(name, "Market date")
    market_date = _fetch_one(
        "Bond Market Date",
        MARKET_DATE_SCALAR_FIELDS,
        name,
        _("You are not permitted to read this market date."),
    )
    market_date["bond_market_prices"] = _checked_child_rows(
        "Bond Market Date", name, "bond_market_prices", MARKET_PRICE_FIELDS
    )
    for row in market_date["bond_market_prices"]:
        if not row["future_xirr_available"]:
            row["future_xirr"] = None
    return set_investor_api_data({"market_date": market_date})


@frappe.whitelist(methods=["GET"])
def get_exchange_rates(
    start: int | str | None = None,
    page_length: int | str | None = None,
    sort_by: str | None = None,
    sort_order: str | None = None,
    filter_field: str | None = None,
    filter_value: str | None = None,
) -> dict:
    """Return one permission-scoped page of Bond Exchange Rate history."""
    require_investor_ui_access()
    return _paged_list(
        "Bond Exchange Rate",
        EXCHANGE_RATE_LIST_FIELDS,
        start=start,
        page_length=page_length,
        sort_by=sort_by,
        sort_order=sort_order,
        filter_field=filter_field,
        filter_value=filter_value,
        filter_fields=EXCHANGE_RATE_FILTER_FIELDS,
        default_order="rate_date desc, name desc",
        query_context=include_shared_exchange_rates_in_safe_projection(),
    )


@frappe.whitelist(methods=["GET"])
def get_exchange_rate(name: str) -> dict:
    """Return one permission-scoped exchange rate with safe provenance."""
    require_investor_ui_access()
    name = required_string(name, "Exchange rate")

    with include_shared_exchange_rates_in_safe_projection():
        exchange_rate = _fetch_one(
            "Bond Exchange Rate",
            EXCHANGE_RATE_SCALAR_FIELDS,
            name,
            _("You are not permitted to read this exchange rate."),
        )
    # The row is authorized above. Read private provenance only to apply the
    # linked statement's read boundary before returning this fixed projection.
    statement = frappe.db.get_value("Bond Exchange Rate", name, "statement")
    exchange_rate.statement = statement if statement and is_readable("Bond Statement", statement) else None
    return set_investor_api_data({"exchange_rate": exchange_rate})


def _fetch_one(doctype: str, fields: tuple[str, ...], name: str, denied_message: str) -> dict:
    """Return one readable projection row, or deny without revealing existence."""
    rows = frappe.qb.get_query(
        doctype,
        fields=list(fields),
        filters={"name": name},
        limit=1,
        ignore_permissions=False,
    ).run(as_dict=True)
    if not rows:
        frappe.throw(denied_message, frappe.PermissionError)
    return rows[0]


def _checked_child_rows(
    parent_doctype: str, parent: str, parentfield: str, fields: tuple[str, ...]
) -> list[dict]:
    """Return child rows only when the whole document passes its read check.

    Document-level ``check_permission`` also applies User Permissions to Link
    fields inside child rows (for example a restricted Bond Master ISIN), which
    a child-table query does not.
    """
    document = frappe.get_doc(parent_doctype, parent)
    document.check_permission("read")
    return [{field: row.get(field) for field in fields} for row in document.get(parentfield)]


def _paged_list(
    doctype: str,
    fields: tuple[str, ...],
    *,
    start,
    page_length,
    sort_by: str | None,
    sort_order: str | None,
    filter_field: str | None,
    filter_value: str | None,
    default_order: str,
    filter_fields: frozenset[str] = frozenset(),
    filters: dict | None = None,
    query_context: AbstractContextManager | None = None,
) -> dict:
    """Return one permission-scoped page with validated sort, filter, and paging controls.

    Every visible list column except ``name`` is sortable, with ``name`` as the tiebreaker.
    """
    order_by, click_filters = _list_controls(
        sort_by,
        sort_order,
        filter_field,
        filter_value,
        sort_fields=frozenset(fields) - {"name"},
        filter_fields=filter_fields,
        default_order=default_order,
    )
    start_value, page_length_value = _pagination_arguments(start, page_length)
    with query_context or nullcontext():
        rows = frappe.qb.get_query(
            doctype,
            fields=list(fields),
            filters={**(filters or {}), **click_filters},
            order_by=order_by,
            offset=start_value,
            limit=page_length_value + 1,
            ignore_permissions=False,
        ).run(as_dict=True)
    return set_investor_api_data(_page_result(rows, start_value, page_length_value))


def _list_controls(
    sort_by: str | None,
    sort_order: str | None,
    filter_field: str | None,
    filter_value: str | None,
    *,
    sort_fields: frozenset[str],
    filter_fields: frozenset[str],
    default_order: str,
) -> tuple[str, dict[str, str]]:
    sort_by = optional_string(sort_by, "Sort by")
    sort_order = optional_string(sort_order, "Sort order")
    filter_field = optional_string(filter_field, "Filter field")
    filter_value = optional_string(filter_value, "Filter value")

    if sort_by is None and sort_order is not None:
        frappe.throw(_("Sort order requires Sort by."), frappe.ValidationError)
    if sort_by is not None and sort_by not in sort_fields:
        frappe.throw(_("Sort by is not supported for this list."), frappe.ValidationError)
    if sort_by is not None and sort_order not in {"asc", "desc"}:
        frappe.throw(_("Sort order must be asc or desc."), frappe.ValidationError)

    if (filter_field is None) != (filter_value is None):
        frappe.throw(
            _("Filter field and Filter value must be provided together."),
            frappe.ValidationError,
        )
    if filter_field is not None and filter_field not in filter_fields:
        frappe.throw(_("Filter field is not supported for this list."), frappe.ValidationError)

    # sort_by and sort_order are validated against fixed allowlists above.
    order_by = default_order if sort_by is None else f"{sort_by} {sort_order}, name {sort_order}"
    filters = {} if filter_field is None else {filter_field: filter_value}
    return order_by, filters


def _integer_argument(
    value,
    label: str,
    *,
    default: int,
    minimum: int,
    maximum: int | None = None,
) -> int:
    if value is None or value == "":
        return default
    if isinstance(value, bool) or not isinstance(value, (int, str)):
        frappe.throw(_("{0} must be an integer.").format(label))

    try:
        parsed = int(value)
    except ValueError:
        frappe.throw(_("{0} must be an integer.").format(label))

    if str(parsed) != str(value).strip():
        frappe.throw(_("{0} must be an integer.").format(label))
    if parsed < minimum:
        frappe.throw(_("{0} must be at least {1}.").format(label, minimum))
    if maximum is not None and parsed > maximum:
        frappe.throw(_("{0} cannot exceed {1}.").format(label, maximum))
    return parsed


def _pagination_arguments(start, page_length) -> tuple[int, int]:
    start_value = _integer_argument(start, "Start", default=0, minimum=0, maximum=MAX_PAGE_START)
    page_length_value = _integer_argument(
        page_length, "Page length", default=DEFAULT_PAGE_LENGTH, minimum=1, maximum=MAX_PAGE_LENGTH
    )
    return start_value, page_length_value


def _page_result(rows, start: int, page_length: int) -> dict:
    return {
        "data": rows[:page_length],
        "pagination": {"start": start, "page_length": page_length, "has_more": len(rows) > page_length},
    }
