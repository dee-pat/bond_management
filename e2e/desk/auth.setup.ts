import fs from "node:fs";
import path from "node:path";

import { test as setup } from "@playwright/test";

import { administratorStorageState } from "./fixtures";
import { authenticateAdministrator } from "./helpers/auth";
import { openDeskForm } from "./helpers/frappe";

setup("authenticate as Administrator", async ({ page }) => {
  fs.mkdirSync(path.dirname(administratorStorageState), { recursive: true });
  await authenticateAdministrator(page.request);

  await openDeskForm(page, "/desk/bond-master/new", "Bond Master");
  await page.context().storageState({ path: administratorStorageState });
});
