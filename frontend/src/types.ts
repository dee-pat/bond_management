export interface InvestorUser {
  name: string;
  full_name: string;
}

export interface InvestorBootContext {
  feature_enabled: boolean;
  user: InvestorUser;
  is_investor: boolean;
  is_support: boolean;
}

export interface PortfolioChoice {
  name: string;
  label: string;
}

export interface InvestorBootstrap extends InvestorBootContext {
  portfolios: PortfolioChoice[];
}

export interface TransactionListRow {
  name: string;
  settlement_date: string;
  transaction_type: "Purchase" | "Sale";
  portfolio_name: string;
  isin: string;
  trade_date: string;
  quantity_face_value: number;
  price: number;
  attachment: string | null;
}

export interface TransactionPage {
  data: TransactionListRow[];
  pagination: {
    start: number;
    page_length: number;
    has_more: boolean;
  };
}

export interface TransactionDetail {
  transaction_type: "Purchase" | "Sale";
  portfolio_name: string;
  isin: string;
  bond_name: string;
  account_number: string;
  transaction_reference: string;
  trade_date: string;
  settlement_date: string;
  quantity_face_value: number;
  price: number;
  principal: number;
  commission: number;
  accrued_interest_calculated: number;
  accrued_interest_paid: number;
  currency: string;
  maturity_date: string;
  coupon_frequency: string;
  coupon_rate: number;
  face_value_per_unit: number;
  issue_date: string;
  day_count_convention: string;
  commission_amount: number;
  settlement_amount: number;
  transaction_amount: number;
  attachment: string | null;
}

export interface TransactionDetailResponse {
  transaction: TransactionDetail;
}

export type ReconciliationStatus = "Matched" | "Mismatched";

export interface StatementListRow {
  name: string;
  statement_date: string;
  portfolio_name: string;
  reconciliation_status: ReconciliationStatus | null;
}

export interface StatementPage {
  data: StatementListRow[];
  pagination: {
    start: number;
    page_length: number;
    has_more: boolean;
  };
}

export interface StatementHolding {
  isin: string;
  quantity: number;
  principal_factor: number;
  market_price: number | null;
  currency: string;
}

export interface StatementDetail {
  portfolio_name: string;
  statement_date: string;
  market_price_posting: string | null;
  reconciliation_status: ReconciliationStatus | null;
  attachment: string | null;
  quantity_reconciliation_report: string | null;
  bond_statement_details: StatementHolding[];
}

export interface StatementDetailResponse {
  statement: StatementDetail;
}

export interface BondListRow {
  name: string;
  bond_name: string;
  isin: string;
  currency: string;
  issue_date: string;
}

export interface BondPage {
  data: BondListRow[];
  pagination: {
    start: number;
    page_length: number;
    has_more: boolean;
  };
}

export interface BondPrincipalRow {
  repayment_date: string;
  principal_units: number;
  repayment_percent: number;
}

export interface BondCouponRow {
  coupon_date: string;
  period_start: string;
  period_end: string;
  coupon_factor: number;
}

export interface BondDetail {
  bond_name: string;
  isin: string;
  issue_date: string;
  first_coupon_date: string;
  face_value_per_unit: number;
  coupon_frequency: string;
  bond_type: string;
  maturity_date: string;
  currency: string;
  coupon_rate: number;
  withholding_tax: number;
  day_count_convention: string;
  quantity_change: 0 | 1;
  principal_schedule: BondPrincipalRow[];
  coupon_schedule: BondCouponRow[];
}

export interface BondDetailResponse {
  bond: BondDetail;
}

export interface MarketDateListRow {
  name: string;
  date: string;
}

export interface MarketDatePage {
  data: MarketDateListRow[];
  pagination: {
    start: number;
    page_length: number;
    has_more: boolean;
  };
}

export interface MarketPriceRow {
  isin: string;
  principal_factor: number;
  market_price: number;
  currency: string;
  future_xirr: number | null;
  weighted_avg_repayment_date: string | null;
  weighted_avg_repayment_years: number | null;
  maturity_date: string;
}

export interface MarketDateDetail {
  date: string;
  bond_market_prices: MarketPriceRow[];
}

export interface MarketDateDetailResponse {
  market_date: MarketDateDetail;
}

export interface ExchangeRateListRow {
  name: string;
  rate_date: string;
  from_currency: string;
  to_currency: string;
  rate: number;
  reverse_rate: number;
}

export interface ExchangeRatePage {
  data: ExchangeRateListRow[];
  pagination: {
    start: number;
    page_length: number;
    has_more: boolean;
  };
}

export type ExchangeRateSource = "Manual" | "Statement PDF";

export interface ExchangeRateDetail {
  rate_date: string;
  from_currency: string;
  to_currency: string;
  source: ExchangeRateSource;
  rate: number;
  reverse_rate: number;
  statement: string | null;
}

export interface ExchangeRateDetailResponse {
  exchange_rate: ExchangeRateDetail;
}

declare global {
  interface Window {
    bond_investor?: InvestorBootContext;
    csrf_token?: string;
  }
}
