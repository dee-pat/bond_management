import { createRouter, createWebHistory } from "vue-router";

import { INVESTOR_NAVIGATION } from "./navigation";
import InvestorShell from "./pages/InvestorShell.vue";

export default createRouter({
  history: createWebHistory("/bond-investor"),
  routes: [
    ...INVESTOR_NAVIGATION.map((item) => ({
      path: item.path,
      name: item.name,
      component: InvestorShell,
      meta: { title: item.name === "home" ? "Bond Investor" : item.label },
    })),
    {
      path: "/transactions/:transactionName",
      name: "transaction-detail",
      component: InvestorShell,
      meta: { title: "Bond Transaction" },
    },
    {
      path: "/statements/:statementName",
      name: "statement-detail",
      component: InvestorShell,
      meta: { title: "Bond Statement" },
    },
    {
      path: "/bonds/:bondName",
      name: "bond-detail",
      component: InvestorShell,
      meta: { title: "Bond Master" },
    },
    {
      path: "/market-dates/:marketDateName",
      name: "market-date-detail",
      component: InvestorShell,
      meta: { title: "Bond Market Date" },
    },
    {
      path: "/exchange-rates/:exchangeRateName",
      name: "exchange-rate-detail",
      component: InvestorShell,
      meta: { title: "Bond Exchange Rate" },
    },
    {
      path: "/:pathMatch(.*)*",
      name: "not-found",
      component: InvestorShell,
      meta: { title: "Page not found" },
    },
  ],
});
