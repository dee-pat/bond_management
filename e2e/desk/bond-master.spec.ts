import { expect, test } from "@playwright/test";

import { openDeskForm, type DeskTestWindow } from "./helpers/frappe";

const scheduleMethod =
  "bond_management.bond_management.doctype.bond_master.bond_master.get_recalculated_schedules";

test("derives quantity change from KES and the Kenya day-count convention", async ({
  page,
}) => {
  await openDeskForm(page, "/desk/bond-master/new", "Bond Master");

  const values = await page.evaluate(async () => {
    const form = (window as DeskTestWindow).cur_frm;
    if (!form) {
      throw new Error("Bond Master form did not load");
    }

    form.doc.currency = "KES";
    form.doc.day_count_convention = "Actual/364(Kenya)";
    await form.script_manager.trigger("day_count_convention");
    const kesQuantityChange = form.doc.quantity_change;

    form.doc.currency = "USD";
    await form.script_manager.trigger("currency");
    return {
      kesQuantityChange,
      usdQuantityChange: form.doc.quantity_change,
    };
  });

  expect(values.kesQuantityChange).toBe(1);
  expect(values.usdQuantityChange).toBe(0);
});

test("exposes withholding tax as a zero-default percentage", async ({
  page,
}) => {
  await openDeskForm(page, "/desk/bond-master/new", "Bond Master");

  const field = await page.evaluate(() => {
    const form = (window as DeskTestWindow).cur_frm;
    if (!form) {
      throw new Error("Bond Master form did not load");
    }
    const definition = form.get_field("withholding_tax").df;
    return {
      fieldtype: definition.fieldtype,
      defaultValue: String(definition.default),
    };
  });

  expect(field.fieldtype).toBe("Percent");
  expect(field.defaultValue).toBe("0");
});

test("applies a server-normalized first coupon date through the form setter", async ({
  page,
}) => {
  await page.route(`**/api/method/${scheduleMethod}`, async (route) => {
    await route.fulfill({
      json: {
        message: {
          quantity_change: 0,
          maturity_date: "2027-01-01",
          first_coupon_date: "2025-01-03",
          principal_schedule: [],
          coupon_schedule: [],
        },
      },
    });
  });

  await openDeskForm(page, "/desk/bond-master/new", "Bond Master");
  const request = page.waitForResponse((response) =>
    response.url().includes(scheduleMethod)
  );
  const setValueCalls = await page.evaluate(async () => {
    const form = (window as DeskTestWindow).cur_frm;
    if (!form) {
      throw new Error("Bond Master form did not load");
    }

    form.doc.issue_date = "2025-01-01";
    form.doc.face_value_per_unit = 100;
    form.doc.coupon_frequency = "2";
    form.doc.day_count_convention = "30E/360";
    form.add_child("principal_schedule", {
      repayment_date: "2027-01-01",
      principal_units: 100,
    });

    const calls: unknown[][] = [];
    const originalSetValue = form.set_value.bind(form);
    form.set_value = (...args) => {
      calls.push(args);
      return originalSetValue(...args);
    };
    await form.script_manager.trigger("first_coupon_date");
    return calls;
  });
  await request;

  expect(setValueCalls).toContainEqual(["first_coupon_date", "2025-01-03"]);
  await expect
    .poll(() =>
      page.evaluate(() => (window as DeskTestWindow).cur_frm?.is_dirty())
    )
    .toBe(true);
});
