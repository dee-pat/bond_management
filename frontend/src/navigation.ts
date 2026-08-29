export interface InvestorNavigationItem {
  name: string;
  label: string;
  path: string;
  icon: string;
}

export const INVESTOR_NAVIGATION: InvestorNavigationItem[] = [
  { name: "home", label: "Home", path: "/", icon: "home" },
  {
    name: "transactions",
    label: "Bond Transactions",
    path: "/transactions",
    icon: "activity",
  },
  {
    name: "statements",
    label: "Bond Statements",
    path: "/statements",
    icon: "file-text",
  },
  {
    name: "bonds",
    label: "Bond Master",
    path: "/bonds",
    icon: "book-open",
  },
  {
    name: "market-dates",
    label: "Bond Market Dates",
    path: "/market-dates",
    icon: "calendar",
  },
  {
    name: "exchange-rates",
    label: "Bond Exchange Rates",
    path: "/exchange-rates",
    icon: "refresh-cw",
  },
  {
    name: "performance",
    label: "Portfolio Performance",
    path: "/performance",
    icon: "bar-chart-2",
  },
  {
    name: "yield-comparison",
    label: "Bond Yield Comparison",
    path: "/yield-comparison",
    icon: "trending-up",
  },
];
