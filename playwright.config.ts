import { defineConfig, devices } from "@playwright/test";

import { administratorStorageState } from "./e2e/desk/fixtures";
import { investorStorageState } from "./e2e/investor/fixtures";

export default defineConfig({
  testDir: "./e2e",
  fullyParallel: false,
  forbidOnly: Boolean(process.env.CI),
  retries: process.env.CI ? 2 : 0,
  workers: 1,
  reporter: process.env.CI ? [["github"], ["blob"]] : "html",
  timeout: 60_000,
  expect: {
    timeout: 10_000,
  },
  use: {
    actionTimeout: 15_000,
    baseURL: process.env.BASE_URL || "http://localhost:8000",
    navigationTimeout: 30_000,
    screenshot: "only-on-failure",
    trace: "on-first-retry",
    video: "retain-on-failure",
  },
  projects: [
    {
      name: "investor-setup",
      testMatch: /investor\/auth\.setup\.ts/,
    },
    {
      name: "desk-setup",
      testMatch: /desk\/auth\.setup\.ts/,
    },
    {
      name: "investor-desktop",
      use: {
        ...devices["Desktop Chrome"],
        storageState: investorStorageState,
      },
      testMatch: /investor\/.*\.spec\.ts$/,
      testIgnore: /\.mobile\.spec\.ts$/,
      dependencies: ["investor-setup"],
    },
    {
      name: "investor-mobile",
      use: {
        ...devices["Pixel 7"],
        storageState: investorStorageState,
      },
      testMatch: /investor\/.*\.mobile\.spec\.ts$/,
      dependencies: ["investor-setup"],
    },
    {
      name: "desk",
      use: {
        ...devices["Desktop Chrome"],
        storageState: administratorStorageState,
      },
      testMatch: /desk\/.*\.spec\.ts$/,
      dependencies: ["desk-setup"],
    },
  ],
});
