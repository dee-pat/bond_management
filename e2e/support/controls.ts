import { expect, type Page } from "@playwright/test";

export async function selectFrappeOption(
	page: Page,
	label: string,
	option: string,
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
