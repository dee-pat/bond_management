"""Investor response contracts owned by tests, independent of production projections.

Endpoint tests compare actual responses with these fields, so a production
allowlist change must be mirrored here deliberately.
"""

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
BOND_LIST_FIELDS = (
    "name",
    "bond_name",
    "isin",
    "currency",
    "issue_date",
)
BOND_DETAIL_FIELDS = (
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
    "principal_schedule",
    "coupon_schedule",
)
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
EXCHANGE_RATE_DETAIL_FIELDS = (
    "rate_date",
    "from_currency",
    "to_currency",
    "source",
    "rate",
    "reverse_rate",
    "statement",
)
INTEREST_DIFFERENCE_FIELDS = (
    "transaction_reference",
    "settlement_date",
    "currency",
    "isin",
    "transaction_type",
    "accrued_interest_calculated",
    "accrued_interest_paid",
    "interest_difference",
    "interest_difference_days",
)
INTEREST_DIFFERENCE_ROW_FIELDS = (
    "transaction_reference",
    "settlement_date",
    "currency",
    "isin",
    "transaction_type",
    "accrued_interest_calculated",
    "accrued_interest_paid",
    "interest_difference",
    "interest_difference_days",
    "is_total_row",
)
PORTFOLIO_PERFORMANCE_COLUMN_FIELDS = (
    "isin",
    "currency",
    "principal_factor",
    "nominal_value",
    "purchases_value",
    "proceeds_value",
    "market_value",
    "market_value_usd",
    "gain_value",
    "xirr",
    "xirr_usd",
    "future_xirr",
    "expected_coupons_next_year",
    "expected_coupons_next_year_usd",
)
PORTFOLIO_PERFORMANCE_ROW_FIELDS = (
    "isin",
    "currency",
    "reporting_currency",
    "principal_factor",
    "nominal_value",
    "purchases_value",
    "proceeds_value",
    "market_value",
    "market_value_usd",
    "gain_value",
    "xirr",
    "xirr_usd",
    "future_xirr",
    "expected_coupons_next_year",
    "expected_coupons_next_year_usd",
    "has_past_cashflows",
    "has_future_cashflows",
)
PORTFOLIO_CASHFLOW_FIELDS = (
    "isin",
    "transaction_type",
    "date",
    "currency",
    "amount",
    "quantity",
    "rate",
)
BOND_YIELD_COMPARISON_FIELDS = (
    "date",
    "isin",
    "currency",
    "market_price",
    "future_xirr",
)
YIELD_COMPARISON_CHART = {
    "x_field": "date",
    "value_field": "future_xirr",
    "series_field": "isin",
    "gap_policy": "preserve",
}
