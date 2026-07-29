import { expect } from "@playwright/test";
import { test } from "./fixtures/live-proxy.js";

test("@live-proxy loads authenticated production orchestration state", async ({ livePage, api }) => {
  await livePage.goto("/orchestrator");
  await expect(livePage.getByRole("tab", { name: "Operate", exact: true })).toBeVisible();

  const config = await api("/v1/orchestration/config");
  expect(config.version).toBe(1);
});
