import type { Component } from "vue";

import BondDetail from "./pages/BondDetail.vue";
import BondList from "./pages/BondList.vue";
import ExchangeRateDetail from "./pages/ExchangeRateDetail.vue";
import ExchangeRateList from "./pages/ExchangeRateList.vue";
import InterestDifference from "./pages/InterestDifference.vue";
import MarketDateDetail from "./pages/MarketDateDetail.vue";
import MarketDateList from "./pages/MarketDateList.vue";
import PortfolioPerformance from "./pages/PortfolioPerformance.vue";
import StatementDetail from "./pages/StatementDetail.vue";
import StatementList from "./pages/StatementList.vue";
import TransactionDetail from "./pages/TransactionDetail.vue";
import TransactionList from "./pages/TransactionList.vue";
import YieldComparison from "./pages/YieldComparison.vue";

interface InvestorPage {
  component: Component;
  path?: string;
  title?: string;
  parent?: string;
  needsBootstrap?: boolean;
}

export const PAGE_BY_ROUTE: Partial<Record<string, InvestorPage>> = {
  transactions: { component: TransactionList, needsBootstrap: true },
  "transaction-detail": {
    path: "/transactions/:transactionName",
    component: TransactionDetail,
    title: "Bond Transaction",
    parent: "transactions",
  },
  statements: { component: StatementList, needsBootstrap: true },
  "statement-detail": {
    path: "/statements/:statementName",
    component: StatementDetail,
    title: "Bond Statement",
    parent: "statements",
  },
  bonds: { component: BondList },
  "bond-detail": {
    path: "/bonds/:bondName",
    component: BondDetail,
    title: "Bond Master",
    parent: "bonds",
  },
  "market-dates": { component: MarketDateList },
  "market-date-detail": {
    path: "/market-dates/:marketDateName",
    component: MarketDateDetail,
    title: "Bond Market Date",
    parent: "market-dates",
  },
  "exchange-rates": { component: ExchangeRateList },
  "exchange-rate-detail": {
    path: "/exchange-rates/:exchangeRateName",
    component: ExchangeRateDetail,
    title: "Bond Exchange Rate",
    parent: "exchange-rates",
  },
  performance: { component: PortfolioPerformance, needsBootstrap: true },
  "interest-difference": {
    component: InterestDifference,
    needsBootstrap: true,
  },
  "yield-comparison": { component: YieldComparison },
};
