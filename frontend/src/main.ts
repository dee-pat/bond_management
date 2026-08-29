import { createApp } from "vue";
import { FrappeUI } from "frappe-ui";

import App from "./App.vue";
import router from "./router";
import "frappe-ui/style.css";
import "./style.css";
import "./transaction.css";
import "./statement.css";
import "./bond.css";
import "./market-date.css";
import "./performance.css";
import "./yield-comparison.css";

router.afterEach((to) => {
  const title =
    typeof to.meta.title === "string" ? to.meta.title : "Bond Investor";
  document.title =
    title === "Bond Investor" ? title : `${title} · Bond Investor`;
});

createApp(App)
  .use(router)
  .use(FrappeUI, { call: false, resources: false, socketio: false })
  .mount("#app");
