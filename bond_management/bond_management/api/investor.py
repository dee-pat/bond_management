"""Read-only API contracts for the investor SPA."""

import frappe
from frappe import _
from frappe.utils import get_fullname

# Keep established dotted API paths while report adapters live in a focused module.
from bond_management.bond_management.api.investor_reports import (
    get_bond_yield_comparison,
    get_portfolio_performance,
    get_portfolio_performance_cashflows,
    get_yield_comparison_defaults,
)
from bond_management.bond_management.utils.investor_permissions import (
    BOND_MANAGER_ROLE,
    INVESTOR_ROLE,
    _get_allowed_portfolios,
)
from bond_management.bond_management.utils.investor_ui import require_investor_ui_access
from bond_management.bond_management.utils.validation import optional_string, required_string

DEFAULT_PAGE_LENGTH = 20
MAX_PAGE_LENGTH = 50
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
STATEMENT_DETAIL_FIELDS = (
    "portfolio_name",
    "statement_date",
    "market_price_posting",
    "reconciliation_status",
    "attachment",
    "quantity_reconciliation_report",
    "bond_statement_details",
)
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
MARKET_DATE_DETAIL_FIELDS = ("date", "bond_market_prices")
MARKET_PRICE_FIELDS = (
    "isin",
    "principal_factor",
    "market_price",
    "currency",
    "future_xirr",
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


def _build_sort_options(fields: tuple[str, ...]) -> dict[str, dict[str, str]]:
    return {
        field: {
            "asc": f"{field} asc, name asc",
            "desc": f"{field} desc, name desc",
        }
        for field in fields
    }


TRANSACTION_SORT_OPTIONS = _build_sort_options(
    (
        "settlement_date",
        "transaction_type",
        "portfolio_name",
        "isin",
        "trade_date",
        "quantity_face_value",
        "price",
    )
)
STATEMENT_SORT_OPTIONS = _build_sort_options(("statement_date", "portfolio_name", "reconciliation_status"))
BOND_SORT_OPTIONS = _build_sort_options(("bond_name", "isin", "currency", "issue_date"))
MARKET_DATE_SORT_OPTIONS = _build_sort_options(("date",))
EXCHANGE_RATE_SORT_OPTIONS = _build_sort_options(
    ("rate_date", "from_currency", "to_currency", "rate", "reverse_rate")
)

TRANSACTION_FILTER_FIELDS = {
    "transaction_type": "transaction_type",
    "isin": "isin",
    "quantity_face_value": "quantity_face_value",
    "price": "price",
}
STATEMENT_FILTER_FIELDS = {}
BOND_FILTER_FIELDS = {
    "bond_name": "bond_name",
    "isin": "isin",
    "currency": "currency",
}
MARKET_DATE_FILTER_FIELDS = {}
EXCHANGE_RATE_FILTER_FIELDS = {
    "from_currency": "from_currency",
    "to_currency": "to_currency",
    "rate": "rate",
    "reverse_rate": "reverse_rate",
}
EXCHANGE_RATE_DETAIL_FIELDS = (
    "rate_date",
    "from_currency",
    "to_currency",
    "source",
    "rate",
    "reverse_rate",
    "statement",
)


@frappe.whitelist(methods=["GET"])
def get_bootstrap() -> dict:
    """Return the authenticated shell context and allowed portfolio choices."""
    require_investor_ui_access()

    user = frappe.session.user
    roles = set(frappe.get_roles(user))
    allowed_portfolios = _get_allowed_portfolios(user)
    filters = {}

    if allowed_portfolios is not None:
        if not allowed_portfolios:
            portfolio_choices = []
        else:
            filters["name"] = ["in", allowed_portfolios]

    if allowed_portfolios is None or allowed_portfolios:
        portfolio_rows = frappe.qb.get_query(
            "Bond Portfolio",
            fields=["name", "portfolio_name"],
            filters=filters,
            order_by="portfolio_name asc, name asc",
            ignore_permissions=False,
        ).run(as_dict=True)
        portfolio_choices = [{"name": row.name, "label": row.portfolio_name} for row in portfolio_rows]

    return {
        "feature_enabled": True,
        "user": {
            "name": user,
            "full_name": get_fullname(user),
        },
        "is_investor": INVESTOR_ROLE in roles,
        "is_support": user == "Administrator" or BOND_MANAGER_ROLE in roles,
        "portfolios": portfolio_choices,
    }


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
    order_by, click_filters = _list_controls(
        sort_by,
        sort_order,
        filter_field,
        filter_value,
        sort_options=TRANSACTION_SORT_OPTIONS,
        filter_fields=TRANSACTION_FILTER_FIELDS,
        default_order="settlement_date desc, name desc",
    )
    start_value = _integer_argument(start, "Start", default=0, minimum=0)
    page_length_value = _integer_argument(
        page_length,
        "Page length",
        default=DEFAULT_PAGE_LENGTH,
        minimum=1,
        maximum=MAX_PAGE_LENGTH,
    )
    filters = {}
    if portfolio:
        _require_readable_portfolio(portfolio)
        filters["portfolio_name"] = portfolio
    filters.update(click_filters)

    rows = frappe.qb.get_query(
        "Bond Transaction",
        fields=list(TRANSACTION_LIST_FIELDS),
        filters=filters,
        order_by=order_by,
        offset=start_value,
        limit=page_length_value + 1,
        ignore_permissions=False,
    ).run(as_dict=True)
    has_more = len(rows) > page_length_value

    return {
        "data": rows[:page_length_value],
        "pagination": {
            "start": start_value,
            "page_length": page_length_value,
            "has_more": has_more,
        },
    }


@frappe.whitelist(methods=["GET"])
def get_transaction(name: str) -> dict:
    """Return one permission-scoped transaction, including its private PDF URL."""
    require_investor_ui_access()
    name = required_string(name, "Transaction")

    rows = frappe.qb.get_query(
        "Bond Transaction",
        fields=list(TRANSACTION_DETAIL_FIELDS),
        filters={"name": name},
        limit=1,
        ignore_permissions=False,
    ).run(as_dict=True)
    if not rows:
        frappe.throw(_("You are not permitted to read this transaction."), frappe.PermissionError)

    return {"transaction": rows[0]}


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
    order_by, click_filters = _list_controls(
        sort_by,
        sort_order,
        filter_field,
        filter_value,
        sort_options=STATEMENT_SORT_OPTIONS,
        filter_fields=STATEMENT_FILTER_FIELDS,
        default_order="statement_date desc, name desc",
    )
    if reconciliation_status and reconciliation_status not in STATEMENT_RECONCILIATION_STATUSES:
        frappe.throw(_("Reconciliation status must be Matched or Mismatched."))

    start_value = _integer_argument(start, "Start", default=0, minimum=0)
    page_length_value = _integer_argument(
        page_length,
        "Page length",
        default=DEFAULT_PAGE_LENGTH,
        minimum=1,
        maximum=MAX_PAGE_LENGTH,
    )
    filters = {}
    if portfolio:
        _require_readable_portfolio(portfolio)
        filters["portfolio_name"] = portfolio
    if reconciliation_status:
        filters["reconciliation_status"] = reconciliation_status
    filters.update(click_filters)

    rows = frappe.qb.get_query(
        "Bond Statement",
        fields=list(STATEMENT_LIST_FIELDS),
        filters=filters,
        order_by=order_by,
        offset=start_value,
        limit=page_length_value + 1,
        ignore_permissions=False,
    ).run(as_dict=True)
    has_more = len(rows) > page_length_value

    return {
        "data": rows[:page_length_value],
        "pagination": {
            "start": start_value,
            "page_length": page_length_value,
            "has_more": has_more,
        },
    }


@frappe.whitelist(methods=["GET"])
def get_statement(name: str) -> dict:
    """Return one permission-scoped statement with its PDF and report URLs."""
    require_investor_ui_access()
    name = required_string(name, "Statement")

    rows = frappe.qb.get_query(
        "Bond Statement",
        fields=list(STATEMENT_DETAIL_FIELDS[:-1]),
        filters={"name": name},
        limit=1,
        ignore_permissions=False,
    ).run(as_dict=True)
    if not rows:
        frappe.throw(_("You are not permitted to read this statement."), frappe.PermissionError)

    statement = rows[0]
    document = frappe.get_doc("Bond Statement", name)
    statement["bond_statement_details"] = [
        {field: row.get(field) for field in STATEMENT_HOLDING_FIELDS}
        for row in document.bond_statement_details
    ]
    return {"statement": statement}


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
    order_by, filters = _list_controls(
        sort_by,
        sort_order,
        filter_field,
        filter_value,
        sort_options=BOND_SORT_OPTIONS,
        filter_fields=BOND_FILTER_FIELDS,
        default_order="issue_date desc, name desc",
    )

    start_value = _integer_argument(start, "Start", default=0, minimum=0)
    page_length_value = _integer_argument(
        page_length,
        "Page length",
        default=DEFAULT_PAGE_LENGTH,
        minimum=1,
        maximum=MAX_PAGE_LENGTH,
    )
    rows = frappe.qb.get_query(
        "Bond Master",
        fields=list(BOND_LIST_FIELDS),
        filters=filters,
        order_by=order_by,
        offset=start_value,
        limit=page_length_value + 1,
        ignore_permissions=False,
    ).run(as_dict=True)
    has_more = len(rows) > page_length_value

    return {
        "data": rows[:page_length_value],
        "pagination": {
            "start": start_value,
            "page_length": page_length_value,
            "has_more": has_more,
        },
    }


@frappe.whitelist(methods=["GET"])
def get_bond(name: str) -> dict:
    """Return one permission-scoped Bond Master with visible schedules."""
    require_investor_ui_access()
    name = required_string(name, "Bond")

    rows = frappe.qb.get_query(
        "Bond Master",
        fields=list(BOND_SCALAR_FIELDS),
        filters={"name": name},
        limit=1,
        ignore_permissions=False,
    ).run(as_dict=True)
    if not rows:
        frappe.throw(_("You are not permitted to read this bond."), frappe.PermissionError)

    bond = rows[0]
    document = frappe.get_doc("Bond Master", name)
    bond["principal_schedule"] = [
        {field: row.get(field) for field in BOND_PRINCIPAL_FIELDS} for row in document.principal_schedule
    ]
    bond["coupon_schedule"] = [
        {field: row.get(field) for field in BOND_COUPON_FIELDS} for row in document.coupon_schedule
    ]
    return {"bond": bond}


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
    order_by, filters = _list_controls(
        sort_by,
        sort_order,
        filter_field,
        filter_value,
        sort_options=MARKET_DATE_SORT_OPTIONS,
        filter_fields=MARKET_DATE_FILTER_FIELDS,
        default_order="date desc, name desc",
    )

    start_value = _integer_argument(start, "Start", default=0, minimum=0)
    page_length_value = _integer_argument(
        page_length,
        "Page length",
        default=DEFAULT_PAGE_LENGTH,
        minimum=1,
        maximum=MAX_PAGE_LENGTH,
    )
    rows = frappe.qb.get_query(
        "Bond Market Date",
        fields=list(MARKET_DATE_LIST_FIELDS),
        filters=filters,
        order_by=order_by,
        offset=start_value,
        limit=page_length_value + 1,
        ignore_permissions=False,
    ).run(as_dict=True)
    has_more = len(rows) > page_length_value

    return {
        "data": rows[:page_length_value],
        "pagination": {
            "start": start_value,
            "page_length": page_length_value,
            "has_more": has_more,
        },
    }


@frappe.whitelist(methods=["GET"])
def get_market_date(name: str) -> dict:
    """Return one permission-scoped market date with persisted market rows."""
    require_investor_ui_access()
    name = required_string(name, "Market date")

    rows = frappe.qb.get_query(
        "Bond Market Date",
        fields=list(MARKET_DATE_DETAIL_FIELDS[:-1]),
        filters={"name": name},
        limit=1,
        ignore_permissions=False,
    ).run(as_dict=True)
    if not rows:
        frappe.throw(_("You are not permitted to read this market date."), frappe.PermissionError)

    market_date = rows[0]
    document = frappe.get_doc("Bond Market Date", name)
    market_date["bond_market_prices"] = [
        {field: row.get(field) for field in MARKET_PRICE_FIELDS} for row in document.bond_market_prices
    ]
    return {"market_date": market_date}


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
    order_by, filters = _list_controls(
        sort_by,
        sort_order,
        filter_field,
        filter_value,
        sort_options=EXCHANGE_RATE_SORT_OPTIONS,
        filter_fields=EXCHANGE_RATE_FILTER_FIELDS,
        default_order="rate_date desc, name desc",
    )

    start_value = _integer_argument(start, "Start", default=0, minimum=0)
    page_length_value = _integer_argument(
        page_length,
        "Page length",
        default=DEFAULT_PAGE_LENGTH,
        minimum=1,
        maximum=MAX_PAGE_LENGTH,
    )
    rows = frappe.qb.get_query(
        "Bond Exchange Rate",
        fields=list(EXCHANGE_RATE_LIST_FIELDS),
        filters=filters,
        order_by=order_by,
        offset=start_value,
        limit=page_length_value + 1,
        ignore_permissions=False,
    ).run(as_dict=True)
    has_more = len(rows) > page_length_value

    return {
        "data": rows[:page_length_value],
        "pagination": {
            "start": start_value,
            "page_length": page_length_value,
            "has_more": has_more,
        },
    }


@frappe.whitelist(methods=["GET"])
def get_exchange_rate(name: str) -> dict:
    """Return one permission-scoped exchange rate with safe provenance."""
    require_investor_ui_access()
    name = required_string(name, "Exchange rate")

    rows = frappe.qb.get_query(
        "Bond Exchange Rate",
        fields=list(EXCHANGE_RATE_DETAIL_FIELDS),
        filters={"name": name},
        limit=1,
        ignore_permissions=False,
    ).run(as_dict=True)
    if not rows:
        frappe.throw(_("You are not permitted to read this exchange rate."), frappe.PermissionError)

    exchange_rate = rows[0]
    exchange_rate.statement = _visible_statement_reference(exchange_rate.statement)
    return {"exchange_rate": exchange_rate}


def _visible_statement_reference(statement: str | None) -> str | None:
    if not statement:
        return None

    readable = frappe.qb.get_query(
        "Bond Statement",
        fields=["name"],
        filters={"name": statement},
        limit=1,
        ignore_permissions=False,
    ).run(pluck=True)
    return statement if readable else None


def _require_readable_portfolio(portfolio: str) -> None:
    readable = frappe.qb.get_query(
        "Bond Portfolio",
        fields=["name"],
        filters={"name": portfolio},
        limit=1,
        ignore_permissions=False,
    ).run(pluck=True)
    if not readable:
        frappe.throw(_("You are not permitted to read this portfolio."), frappe.PermissionError)


def _list_controls(
    sort_by: str | None,
    sort_order: str | None,
    filter_field: str | None,
    filter_value: str | None,
    *,
    sort_options: dict[str, dict[str, str]],
    filter_fields: dict[str, str],
    default_order: str,
) -> tuple[str, dict[str, str]]:
    sort_by = optional_string(sort_by, "Sort by")
    sort_order = optional_string(sort_order, "Sort order")
    filter_field = optional_string(filter_field, "Filter field")
    filter_value = optional_string(filter_value, "Filter value")

    if sort_by is None and sort_order is not None:
        frappe.throw(_("Sort order requires Sort by."), frappe.ValidationError)
    if sort_by is not None and sort_by not in sort_options:
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

    order_by = default_order if sort_by is None else sort_options[sort_by][sort_order]
    filters = {} if filter_field is None else {filter_fields[filter_field]: filter_value}
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
