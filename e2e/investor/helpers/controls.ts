import { expect, type Page } from "@playwright/test";

export async function selectFrappeOption(
  page: Page,
  label: string,
  option: string
): Promise<void> {
  const combobox = page.getByRole("combobox", { name: label, exact: true });
  await combobox.click();
  const optionLocator = page
    .locator('[data-slot="item"]')
    .filter({ hasText: option })
    .first();
  await expect(optionLocator).toBeVisible();
  await optionLocator.click();
}

export async function expectDetailNavigation(
  page: Page,
  section: string,
  path: string,
  title: string
): Promise<void> {
  const breadcrumbs = page.getByRole("navigation", { name: "Breadcrumb" });
  const parent = breadcrumbs.getByRole("link", { name: section, exact: true });
  await expect(parent).toBeVisible();
  await expect(parent).toHaveAttribute("href", `/bond-investor${path}`);
  await expect(
    breadcrumbs.getByRole("heading", { name: title, exact: true })
  ).toBeVisible();
  await expect(
    page
      .getByRole("navigation", { name: "Investor navigation" })
      .getByRole("link", { name: section, exact: true })
  ).toHaveAttribute("aria-current", "page");
}
