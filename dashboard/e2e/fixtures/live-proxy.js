import { test as base } from "@playwright/test";

const ADMIN_KEY = "test-admin-key-for-live-e2e";
const PROXY_URL = "http://127.0.0.1:48787";

export const test = base.extend({
  livePage: async ({ page }, use) => {
    await page.addInitScript((adminKey) => {
      window.localStorage.setItem("cutctxAdminKey", adminKey);
    }, ADMIN_KEY);
    await use(page);
  },
  api: async ({ request }, use) => {
    await use(async (path, options = {}) => {
      const response = await request.fetch(`${PROXY_URL}${path}`, {
        ...options,
        headers: {
          "x-cutctx-admin-key": ADMIN_KEY,
          ...(options.headers || {}),
        },
      });
      if (!response.ok()) {
        throw new Error(`${options.method || "GET"} ${path} returned ${response.status()}: ${await response.text()}`);
      }
      return response.json();
    });
  },
});
