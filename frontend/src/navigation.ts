export interface InvestorNavigationItem {
  name: string;
  label: string;
  path: string;
}

export const INVESTOR_NAVIGATION: InvestorNavigationItem[] = [
  { name: "home", label: "Home", path: "/" },
  {
    name: "transactions",
    label: "Bond Transactions",
    path: "/transactions",
  },
  {
    name: "statements",
    label: "Bond Statements",
    path: "/statements",
  },
  {
    name: "bonds",
    label: "Bond Master",
    path: "/bonds",
  },
  {
    name: "market-dates",
    label: "Bond Market Dates",
    path: "/market-dates",
  },
  {
    name: "exchange-rates",
    label: "Bond Exchange Rates",
    path: "/exchange-rates",
  },
  {
    name: "performance",
    label: "Portfolio Performance",
    path: "/performance",
  },
  {
    name: "yield-comparison",
    label: "Bond Yield Comparison",
    path: "/yield-comparison",
  },
];
