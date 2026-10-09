export type PerformanceFieldname =
  | "isin"
  | "currency"
  | "principal_factor"
  | "nominal_value"
  | "purchases_value"
  | "proceeds_value"
  | "market_value"
  | "market_value_usd"
  | "gain_value"
  | "xirr"
  | "xirr_usd"
  | "future_xirr"
  | "expected_coupons_next_year"
  | "expected_coupons_next_year_usd";

export type CashflowCurrency = "native" | "reporting";
export type XirrType = "past" | "future";

export interface PerformanceCashflowAction {
  xirr_type: XirrType;
  cashflow_currency: CashflowCurrency;
}

export interface PerformanceColumn {
  fieldname: PerformanceFieldname;
  label: string;
  fieldtype: "Data" | "Link" | "Float" | "Currency" | "Percent";
  options: string | null;
  description: string | null;
  precision: number | null;
  cashflow_action: PerformanceCashflowAction | null;
}

export interface PerformanceRow {
  isin: string;
  currency: string | null;
  reporting_currency: string;
  principal_factor: number | null;
  nominal_value: number | null;
  purchases_value: number | null;
  proceeds_value: number | null;
  market_value: number | null;
  market_value_usd: number | null;
  gain_value: number | null;
  xirr: number | null;
  xirr_usd: number | null;
  future_xirr: number | null;
  expected_coupons_next_year: number | null;
  expected_coupons_next_year_usd: number | null;
  has_past_cashflows: boolean;
  has_future_cashflows: boolean;
}

export interface PortfolioPerformanceReport {
  filters: {
    portfolio: string;
    valuation_date: string;
  };
  columns: PerformanceColumn[];
  rows: PerformanceRow[];
  chart: null;
}

export interface PortfolioPerformanceResponse {
  report: PortfolioPerformanceReport;
}

export interface PerformanceCashflow {
  isin: string;
  transaction_type: string;
  date: string;
  currency: string;
  amount: number;
  quantity: number;
  rate: number;
}

export interface PerformanceCashflowsResponse {
  cashflows: PerformanceCashflow[];
}

export interface PerformanceCashflowSelection extends PerformanceCashflowAction {
  isin: string;
  key: string;
}

export type YieldComparisonFieldname =
  "date" | "isin" | "currency" | "market_price" | "future_xirr";

export interface YieldComparisonColumn {
  fieldname: YieldComparisonFieldname;
  label: string;
  fieldtype: "Data" | "Date" | "Link" | "Float" | "Percent";
  options: string | null;
  description: string | null;
  precision: number | null;
}

export interface YieldComparisonRow {
  date: string;
  isin: string;
  currency: string;
  market_price: number | null;
  future_xirr: number | null;
}

export interface BondYieldComparisonReport {
  filters: {
    from_date: string | null;
    to_date: string | null;
  };
  columns: YieldComparisonColumn[];
  rows: YieldComparisonRow[];
  chart: {
    x_field: "date";
    value_field: "future_xirr";
    series_field: "isin";
    gap_policy: "preserve";
  };
}

export interface BondYieldComparisonResponse {
  report: BondYieldComparisonReport;
}

export interface YieldComparisonDefaultsResponse {
  filters: {
    from_date: string | null;
    to_date: string;
  };
}

export type InterestDifferenceFieldname =
  | "transaction_reference"
  | "settlement_date"
  | "currency"
  | "isin"
  | "transaction_type"
  | "accrued_interest_calculated"
  | "accrued_interest_paid"
  | "interest_difference"
  | "interest_difference_days";

export interface InterestDifferenceColumn {
  fieldname: InterestDifferenceFieldname;
  label: string;
  fieldtype: "Data" | "Date" | "Link" | "Currency" | "Float";
  options: string | null;
  description: string | null;
  precision: number | null;
}

export type InterestDifferenceRow = Record<
  InterestDifferenceFieldname,
  string | number | null
>;

export interface InterestDifferenceReport {
  filters: {
    portfolio: string;
    from_date: string | null;
    to_date: string | null;
  };
  columns: InterestDifferenceColumn[];
  rows: InterestDifferenceRow[];
  chart: null;
}

export interface InterestDifferenceResponse {
  report: InterestDifferenceReport;
}
