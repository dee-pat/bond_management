import { expect, type Page } from "@playwright/test";

export interface DeskField {
  df: Record<string, unknown>;
}

export interface DeskChildRow {
  doctype: string;
  name: string;
}

export interface DeskForm {
  doctype: string;
  doc: Record<string, unknown>;
  fields: Array<{ df: { fieldname: string } }>;
  add_child(fieldname: string, values?: Record<string, unknown>): DeskChildRow;
  call(...args: unknown[]): Promise<{ message?: unknown }>;
  clear_table(fieldname: string): void;
  get_field(fieldname: string): DeskField;
  is_dirty(): boolean;
  refresh_field(fieldname: string): void;
  script_manager: {
    trigger(...args: unknown[]): Promise<unknown>;
  };
  set_value(...args: unknown[]): Promise<unknown> | unknown;
}

export interface DeskChart {
  colors: string[];
  data: {
    datasets: Array<{ name: string; values: Array<number | null> }>;
    labels: string[];
  };
  legendArea?: unknown;
  title: string;
}

export interface DeskTestWindow extends Window {
  cur_frm?: DeskForm;
  frappe: {
    call(options: Record<string, unknown>): Promise<{ message?: unknown }>;
    query_report: {
      chart?: DeskChart;
    };
    set_route(...args: unknown[]): unknown;
    ui: {
      form: {
        handlers: Record<string, Record<string, unknown>>;
      };
    };
    utils: {
      copy_to_clipboard(...args: string[]): Promise<unknown>;
    };
  };
  __testClipboardCalls?: string[][];
  __testCalls?: Record<string, number>;
}

export async function openDeskForm(
  page: Page,
  route: string,
  doctype: string
): Promise<void> {
  await page.goto(route);
  await expect(page.locator("body")).toHaveAttribute(
    "data-ajax-state",
    "complete"
  );
  await expect
    .poll(() =>
      page.evaluate(() => (window as DeskTestWindow).cur_frm?.doctype)
    )
    .toBe(doctype);
}

export async function captureClipboard(page: Page): Promise<void> {
  await page.evaluate(() => {
    const testWindow = window as DeskTestWindow;
    testWindow.__testClipboardCalls = [];
    testWindow.frappe.utils.copy_to_clipboard = async (...args) => {
      testWindow.__testClipboardCalls?.push(args);
    };
  });
}

export async function readClipboardCalls(page: Page): Promise<string[][]> {
  return page.evaluate(
    () => (window as DeskTestWindow).__testClipboardCalls ?? []
  );
}
