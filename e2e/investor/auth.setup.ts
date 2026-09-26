import fs from "node:fs";
import path from "node:path";

import { expect, test as setup } from "@playwright/test";

import { investorStorageState } from "./fixtures";
import { authenticateInvestor } from "./helpers/auth";

setup("authenticate", async ({ page }) => {
  fs.mkdirSync(path.dirname(investorStorageState), { recursive: true });
  await authenticateInvestor(page.request);

  await page.goto("/bond-investor");
  await expect(
    page.getByRole("heading", { name: "Bond Investor" })
  ).toBeVisible();
  await page.context().storageState({ path: investorStorageState });
});
