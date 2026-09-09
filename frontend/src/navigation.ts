export interface InvestorNavigationItem {
  name: string;
  label: string;
  path: string;
  icon: string;
}

export const INVESTOR_NAVIGATION: InvestorNavigationItem[] = [
	{ name: "home", label: "Home", path: "/", icon: "lucide-house" },
  {
    name: "transactions",
    label: "Bond Transactions",
    path: "/transactions",
		icon: "lucide-activity",
  },
  {
    name: "statements",
    label: "Bond Statements",
    path: "/statements",
		icon: "lucide-file-text",
  },
  {
    name: "bonds",
    label: "Bond Master",
    path: "/bonds",
		icon: "lucide-book-open",
  },
  {
    name: "market-dates",
    label: "Bond Market Dates",
    path: "/market-dates",
		icon: "lucide-calendar-days",
  },
  {
    name: "exchange-rates",
    label: "Bond Exchange Rates",
    path: "/exchange-rates",
		icon: "lucide-refresh-cw",
  },
  {
    name: "performance",
    label: "Portfolio Performance",
    path: "/performance",
		icon: "lucide-chart-bar",
  },
  {
    name: "yield-comparison",
    label: "Bond Yield Comparison",
    path: "/yield-comparison",
		icon: "lucide-trending-up",
  },
];
