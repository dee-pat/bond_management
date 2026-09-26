import { expect, test } from "@playwright/test";

import { openDeskForm, type DeskTestWindow } from "./helpers/frappe";

test("syncs the canonical rate from reverse rate input", async ({ page }) => {
  await openDeskForm(
    page,
    "/desk/bond-exchange-rate/new",
    "Bond Exchange Rate"
  );

  const rates = await page.evaluate(async () => {
    const form = (window as DeskTestWindow).cur_frm;
    if (!form) {
      throw new Error("Bond Exchange Rate form did not load");
    }

    form.doc.reverse_rate = 129.45;
    await form.script_manager.trigger("reverse_rate");
    return {
      rate: Number(form.doc.rate),
      reverseRate: Number(form.doc.reverse_rate),
    };
  });

  expect(rates.rate).toBeCloseTo(1 / 129.45, 12);
  expect(rates.reverseRate).toBe(129.45);
});
