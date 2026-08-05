const { defineConfig } = require("playwright/test");

module.exports = defineConfig({
  testDir: "./tests",
  timeout: 15_000,
  forbidOnly: true,
  fullyParallel: false,
  workers: 1,
  reporter: "line",
  use: { baseURL: "http://127.0.0.1:41714", browserName: "chromium", headless: true },
  webServer: {
    command: "node static-server.cjs",
    url: "http://127.0.0.1:41714/health",
    reuseExistingServer: false,
    timeout: 10_000
  }
});
