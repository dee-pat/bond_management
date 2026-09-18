from contextlib import contextmanager
from decimal import ROUND_HALF_UP, Decimal
from hashlib import sha256

import frappe
from frappe import _
from frappe.utils import getdate

from bond_management.bond_management.utils.exchange_rate import REPORTING_CURRENCY

SOURCE_DOCTYPE = "Bond Exchange Rate Source"
RATE_PRECISION = Decimal("0.000000000001")


def build_source_key(exchange_rate_name: str, statement_name: str) -> str:
    """Return a stable, bounded identifier for one exchange-rate/statement pair."""
    value = f"{exchange_rate_name}\0{statement_name}".encode()
    return f"EXRSRC-{sha256(value).hexdigest()}"


@contextmanager
def statement_exchange_rate_sync():
    previous = frappe.flags.get("in_statement_exchange_rate_sync")
    frappe.flags.in_statement_exchange_rate_sync = True
    try:
        yield
    finally:
        frappe.flags.in_statement_exchange_rate_sync = previous


def sync_statement_exchange_rates(statement, exchange_rates) -> None:
    """Reconcile one PDF's sources against one global canonical rate per key."""
    # BondStatement has already checked the caller's permission for this save;
    # every row touched here is derived from that authorized statement change.
    desired_rates = _collect_desired_rates(exchange_rates)
    previous_sources = _get_statement_sources(statement.name)
    retained_source_names = set()
    affected_exchange_rate_names = {source.exchange_rate for source in previous_sources}

    with statement_exchange_rate_sync():
        for parsed_rate in desired_rates.values():
            exchange_rate = _get_or_create_exchange_rate(statement, parsed_rate)
            affected_exchange_rate_names.add(exchange_rate.name)
            source = _upsert_statement_source(exchange_rate, statement, parsed_rate)
            retained_source_names.add(source.name)

        for source in previous_sources:
            if source.name in retained_source_names:
                continue
            affected_exchange_rate_names.add(source.exchange_rate)
            _delete_source(source.name)

        for exchange_rate_name in sorted(affected_exchange_rate_names):
            _recompute_canonical_rate(exchange_rate_name)


def delete_statement_exchange_rates(statement_name: str) -> None:
    """Detach one statement's sources and remove only orphaned canonical rows."""
    # BondStatement.on_trash has already checked the caller's permission; the
    # provenance rows are derived data owned by that statement lifecycle.
    sources = _get_statement_sources(statement_name)
    affected_exchange_rate_names = {source.exchange_rate for source in sources}

    with statement_exchange_rate_sync():
        for source in sources:
            _delete_source(source.name)
        for exchange_rate_name in sorted(affected_exchange_rate_names):
            _recompute_canonical_rate(exchange_rate_name)


def _collect_desired_rates(exchange_rates):
    desired_rates = {}
    for parsed_rate in exchange_rates or ():
        if parsed_rate.to_currency != REPORTING_CURRENCY:
            continue
        key = (parsed_rate.from_currency, parsed_rate.to_currency)
        previous = desired_rates.get(key)
        if previous and previous.rate != parsed_rate.rate:
            frappe.throw(
                _("The statement PDF contains conflicting exchange rates for {0} / {1}.").format(*key),
                frappe.ValidationError,
            )
        desired_rates[key] = parsed_rate
    return desired_rates


def _get_statement_sources(statement_name):
    return frappe.qb.get_query(
        SOURCE_DOCTYPE,
        filters={"statement": statement_name},
        fields=["name", "exchange_rate", "statement", "rate", "reverse_rate"],
        order_by="name asc",
        for_update=True,
        ignore_permissions=True,
    ).run(as_dict=True)


def _get_or_create_exchange_rate(statement, parsed_rate):
    rate = _stored_rate(parsed_rate.rate)
    if rate <= 0:
        frappe.throw(
            _("The statement exchange rate is too small to store at 12 decimal places."),
            frappe.ValidationError,
        )
    filters = {
        "rate_date": getdate(statement.statement_date),
        "from_currency": parsed_rate.from_currency,
        "to_currency": parsed_rate.to_currency,
    }
    existing_name = frappe.qb.get_query(
        "Bond Exchange Rate",
        fields=["name"],
        filters=filters,
        limit=1,
        for_update=True,
        ignore_permissions=True,
    ).run(pluck=True)
    if not existing_name:
        try:
            return frappe.get_doc(
                {
                    "doctype": "Bond Exchange Rate",
                    **filters,
                    "rate": rate,
                    "source": "Statement PDF",
                    "statement": statement.name,
                    "manual_fallback": 0,
                }
            ).insert(ignore_permissions=True)
        except frappe.UniqueValidationError:
            # A concurrent PDF may win the global insert. Re-read its locked
            # canonical row so equal rates can still share provenance.
            existing_name = frappe.qb.get_query(
                "Bond Exchange Rate",
                fields=["name"],
                filters=filters,
                limit=1,
                for_update=True,
                ignore_permissions=True,
            ).run(pluck=True)
            if not existing_name:
                raise

    exchange_rate = frappe.get_doc("Bond Exchange Rate", existing_name[0])
    _validate_source_rate(exchange_rate, statement.name, rate)
    return exchange_rate


def _validate_source_rate(exchange_rate, statement_name, desired_rate):
    sources = frappe.qb.get_query(
        SOURCE_DOCTYPE,
        filters={"exchange_rate": exchange_rate.name},
        fields=["name", "statement", "rate"],
        order_by="name asc",
        for_update=True,
        ignore_permissions=True,
    ).run(as_dict=True)
    for source in sources:
        if source.statement != statement_name and _rates_differ(source.rate, desired_rate):
            _throw_conflict(exchange_rate, source.statement, desired_rate)

    if exchange_rate.manual_fallback and _rates_differ(exchange_rate.rate, desired_rate):
        frappe.throw(
            _(
                "The statement rate for {0} on {1} conflicts with the existing manual fallback. "
                "Correct the manual rate or the PDF before saving."
            ).format(exchange_rate.from_currency, exchange_rate.rate_date),
            frappe.ValidationError,
        )
    if not sources and not exchange_rate.manual_fallback and _rates_differ(exchange_rate.rate, desired_rate):
        _throw_conflict(exchange_rate, "the existing canonical row", desired_rate)


def _upsert_statement_source(exchange_rate, statement, parsed_rate):
    rate = _stored_rate(parsed_rate.rate)
    source_key = build_source_key(exchange_rate.name, statement.name)
    source_name = frappe.db.get_value(SOURCE_DOCTYPE, {"source_key": source_key}, "name")
    values = {
        "doctype": SOURCE_DOCTYPE,
        "source_key": source_key,
        "exchange_rate": exchange_rate.name,
        "statement": statement.name,
        "rate": rate,
        "reverse_rate": _reverse_rate(rate),
    }
    if source_name:
        source = frappe.get_doc(SOURCE_DOCTYPE, source_name)
        for fieldname, value in values.items():
            if fieldname != "doctype":
                setattr(source, fieldname, value)
        source.save(ignore_permissions=True)
        return source
    return frappe.get_doc(values).insert(ignore_permissions=True)


def _recompute_canonical_rate(exchange_rate_name):
    exchange_rate = frappe.get_doc("Bond Exchange Rate", exchange_rate_name)
    sources = frappe.qb.get_query(
        SOURCE_DOCTYPE,
        filters={"exchange_rate": exchange_rate_name},
        fields=["statement", "rate", "reverse_rate"],
        order_by="statement asc",
        for_update=True,
        ignore_permissions=True,
    ).run(as_dict=True)
    if not sources:
        if exchange_rate.manual_fallback:
            exchange_rate.source = "Manual"
            exchange_rate.statement = None
            exchange_rate.save(ignore_permissions=True)
            return
        exchange_rate.delete(ignore_permissions=True)
        return

    rate = Decimal(str(sources[0].rate))
    if any(_rates_differ(source.rate, rate) for source in sources[1:]):
        _throw_conflict(exchange_rate, sources[0].statement, sources[1].rate)
    exchange_rate.rate = rate
    exchange_rate.reverse_rate = _reverse_rate(rate)
    exchange_rate.source = "Statement PDF"
    # This link is a stable display projection only; source rows own cleanup.
    exchange_rate.statement = sources[0].statement
    exchange_rate.save(ignore_permissions=True)


def _delete_source(source_name):
    frappe.delete_doc(SOURCE_DOCTYPE, source_name, ignore_permissions=True)


def _reverse_rate(rate):
    rate = Decimal(str(rate))
    return Decimal(1) / rate


def _rates_differ(first, second):
    return _stored_rate(first) != _stored_rate(second)


def _stored_rate(rate):
    """Match the 12-place, half-up DECIMAL storage boundary of rate fields."""
    return Decimal(str(rate)).quantize(RATE_PRECISION, rounding=ROUND_HALF_UP)


def _throw_conflict(exchange_rate, statement_name, desired_rate):
    frappe.throw(
        _(
            "The exchange rate for {0} / {1} on {2} conflicts with statement {3} "
            "({4} versus {5}). Correct one source before saving."
        ).format(
            exchange_rate.from_currency,
            exchange_rate.to_currency,
            exchange_rate.rate_date,
            statement_name,
            exchange_rate.rate,
            desired_rate,
        ),
        frappe.ValidationError,
    )
