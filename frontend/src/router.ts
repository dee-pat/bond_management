import { createRouter, createWebHistory } from "vue-router";

import { INVESTOR_NAVIGATION } from "./navigation";
import { PAGE_BY_ROUTE } from "./page-registry";
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
    ...Object.entries(PAGE_BY_ROUTE).flatMap(([name, page]) =>
      page?.path
        ? [
            {
              path: page.path,
              name,
              component: InvestorShell,
              meta: { title: page.title },
            },
          ]
        : []
    ),
    {
      path: "/:pathMatch(.*)*",
      name: "not-found",
      component: InvestorShell,
      meta: { title: "Page not found" },
    },
  ],
});
