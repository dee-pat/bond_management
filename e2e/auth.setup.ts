import fs from "node:fs";
import path from "node:path";

import { expect, test as setup } from "@playwright/test";

import { authenticateInvestor } from "./support/auth";

const authFile = "e2e/.auth/user.json";

setup("authenticate", async ({ page }) => {
  fs.mkdirSync(path.dirname(authFile), { recursive: true });
  await authenticateInvestor(page.request);

  await page.goto("/bond-investor");
  await expect(
    page.getByRole("heading", { name: "Bond Investor" })
  ).toBeVisible();
  await page.context().storageState({ path: authFile });
});
