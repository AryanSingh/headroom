import { expect } from "@playwright/test";
import { test } from "./fixtures/live-proxy.js";

async function configureLocalProvider(api) {
  const providers = await api("/v1/orchestration/providers");
  if (!providers.accounts.some((account) => account.id === "openai-live-e2e")) {
    await api("/v1/orchestration/providers/openai-live-e2e", {
      method: "PUT",
      data: {
        id: "openai-live-e2e",
        provider: "openai",
        display_name: "OpenAI Live E2E",
        auth_method: "api_key",
        base_url: "http://127.0.0.1:48788",
        organization_id: null,
        workspace_id: null,
        custom_headers: {},
        enabled: true,
        metadata: {},
      },
    });
    await api("/v1/orchestration/providers/openai-live-e2e/credential", {
      method: "PUT",
      data: { api_key: "local-e2e-key" },
    });
  }
  await api("/v1/orchestration/models/refresh/openai-live-e2e", { method: "POST" });
}

test("@live-proxy loads authenticated production orchestration state", async ({ livePage, api }) => {
  await livePage.goto("/orchestrator");
  await expect(livePage.getByRole("tab", { name: "Operate", exact: true })).toBeVisible();

  const config = await api("/v1/orchestration/config");
  expect(config.version).toBe(1);
});

test("@live-proxy Operate persists Off Auto and Aggressive through production config", async ({ livePage, api }) => {
  await livePage.goto("/orchestrator");
  const modes = livePage.getByRole("tablist", { name: "Routing mode" });

  for (const [label, expected] of [["Auto", "auto"], ["Aggressive", "aggressive"], ["Off", "off"]]) {
    await modes.getByRole("tab", { name: label, exact: true }).click();
    await expect(modes.getByRole("tab", { name: label, exact: true })).toHaveAttribute("aria-selected", "true");
    await expect.poll(async () => (await api("/stats?cached=1")).model_routing?.mode).toBe(expected);
    await livePage.reload();
    await expect(modes.getByRole("tab", { name: label, exact: true })).toHaveAttribute("aria-selected", "true");
  }
});

test("@live-proxy Operate turns Safe Savings off through the confirmed production path", async ({ livePage, api }) => {
  await livePage.goto("/orchestrator");
  const modes = livePage.getByRole("tablist", { name: "Routing mode" });
  await modes.getByRole("tab", { name: "Auto", exact: true }).click();
  await expect.poll(async () => (await api("/v1/orchestration/safe-savings/status")).enabled).toBe(true);
  await livePage.reload();

  await livePage.getByRole("button", { name: "Diagnostics and compatibility" }).click();
  const panel = livePage.getByRole("region", { name: "Guided Safe Savings" });
  await expect(panel).toBeVisible();
  livePage.once("dialog", (dialog) => dialog.accept());
  await panel.getByRole("button", { name: "Turn Safe Savings off" }).click();

  await expect.poll(async () => (await api("/v1/orchestration/safe-savings/status")).enabled).toBe(false);
  await expect(panel.getByText("Requests retain the originally requested model.", { exact: true })).toBeVisible();
});

test("@live-proxy Operate disables and re-enables a compatibility provider", async ({ livePage, api }) => {
  await livePage.goto("/orchestrator");
  await livePage.getByRole("button", { name: "Diagnostics and compatibility" }).click();

  await livePage.getByRole("button", { name: "Disable provider" }).first().click();
  await expect.poll(async () => (await api("/v1/providers")).providers[0].healthy).toBe(false);
  await livePage.getByRole("button", { name: "Enable provider" }).first().click();
  await expect.poll(async () => (await api("/v1/providers")).providers[0].healthy).toBe(true);
});

test("@live-proxy Contracts saves simulates promotes rolls back and pauses through production routes", async ({ livePage, api }) => {
  await configureLocalProvider(api);
  const initial = await api("/v1/orchestration/contracts");
  const starter = initial.contracts[0];
  const versionOne = { ...starter, version: "1", state: "draft" };
  await api(`/v1/orchestration/contracts/${versionOne.id}/draft`, {
    method: "PUT",
    data: { contract: versionOne, expected_revision: initial.revision },
  });
  await api(`/v1/orchestration/contracts/${versionOne.id}/versions/1/shadow`, { method: "POST" });
  await api(`/v1/orchestration/contracts/${versionOne.id}/versions/1/evidence`, {
    method: "PUT",
    data: {
      samples: 20,
      quality_scores: Array(20).fill(0.99),
      accepted: 20,
      fallbacks: 0,
      routed_savings_usd: Array(20).fill(0.05),
    },
  });
  await api(`/v1/orchestration/contracts/${versionOne.id}/versions/1/promote`, { method: "POST" });
  await api(`/v1/orchestration/contracts/${versionOne.id}/versions/1/promote`, { method: "POST" });

  await livePage.goto("/orchestrator");
  const primaryTabs = livePage.getByRole("tablist", { name: "Orchestrator workspaces" });
  await primaryTabs.getByRole("tab", { name: "Contracts", exact: true }).click();
  await livePage.getByRole("button", { name: "New contract" }).click();
  await livePage.getByRole("button", { name: "Save immutable draft" }).click();
  await expect(livePage.getByText("v2 · draft", { exact: true })).toBeVisible();

  const routingTabs = livePage.getByRole("tablist", { name: "Routing Studio workspaces" });
  await routingTabs.getByRole("tab", { name: "Simulator", exact: true }).click();
  await livePage.getByRole("button", { name: "Run draft simulation" }).click();
  await expect(livePage.getByText("Provider calls", { exact: true })).toBeVisible();
  await expect(livePage.getByText("0", { exact: true }).last()).toBeVisible();

  await routingTabs.getByRole("tab", { name: "Rollouts", exact: true }).click();
  await livePage.getByRole("button", { name: "Start shadow" }).click();
  await expect(livePage.getByText("Version 2", { exact: true })).toBeVisible();
  await api(`/v1/orchestration/contracts/${versionOne.id}/versions/2/evidence`, {
    method: "PUT",
    data: {
      samples: 20,
      quality_scores: Array(20).fill(0.99),
      accepted: 20,
      fallbacks: 0,
      routed_savings_usd: Array(20).fill(0.05),
    },
  });

  await livePage.reload();
  await primaryTabs.getByRole("tab", { name: "Contracts", exact: true }).click();
  await livePage.locator(".contract-list-items button").filter({ hasText: "v2" }).click();
  await routingTabs.getByRole("tab", { name: "Rollouts", exact: true }).click();
  await livePage.getByRole("button", { name: "Promote to canary" }).click();
  await livePage.getByRole("button", { name: "Promote to active" }).click();
  await livePage.getByRole("button", { name: "Roll back" }).click();
  await expect(livePage.getByText("Version 1", { exact: true })).toBeVisible();
  await livePage.getByRole("button", { name: "Pause rollout" }).click();

  const finalContracts = await api("/v1/orchestration/contracts");
  const states = Object.fromEntries(finalContracts.contracts.map((contract) => [contract.version, contract.state]));
  expect(states).toEqual({ "1": "paused", "2": "paused" });
});

test("@live-proxy Configuration manages a provider credential connection and model refresh", async ({ livePage, api }) => {
  await livePage.goto("/orchestrator");
  await livePage.getByRole("tablist", { name: "Orchestrator workspaces" })
    .getByRole("tab", { name: "Configuration", exact: true }).click();
  await livePage.getByRole("tab", { name: "Providers", exact: true }).click();

  await livePage.getByLabel("Provider", { exact: true }).selectOption("openai");
  await livePage.getByLabel("Account display name").fill("OpenAI Dashboard E2E");
  await livePage.getByLabel("Custom base URL").fill("http://127.0.0.1:48788");
  await livePage.getByLabel("API key").fill("dashboard-e2e-key");
  await livePage.getByRole("button", { name: "Add account" }).click();

  const card = livePage.locator(".orchestration-card").filter({ hasText: "OpenAI Dashboard E2E" });
  await expect(card.getByText("Credential stored", { exact: true })).toBeVisible();
  await card.getByRole("button", { name: "Test", exact: true }).click();
  await expect(livePage.getByText(/Connection healthy \(\d+ ms\)/)).toBeVisible();
  await card.getByRole("button", { name: "Refresh models" }).click();
  await expect(livePage.getByText("Model registry refreshed", { exact: true })).toBeVisible();

  const providers = await api("/v1/orchestration/providers");
  const account = providers.accounts.find((item) => item.display_name === "OpenAI Dashboard E2E");
  expect(account.credential_configured).toBe(true);
  expect(JSON.stringify(account)).not.toContain("dashboard-e2e-key");

  livePage.once("dialog", (dialog) => dialog.accept());
  await card.getByRole("button", { name: "Remove credential" }).click();
  await expect(card.getByText("Credential missing", { exact: true })).toBeVisible();
  const afterRemoval = await api("/v1/orchestration/providers");
  expect(afterRemoval.accounts.find((item) => item.id === account.id).credential_configured).toBe(false);
});

test("@live-proxy Configuration persists roles bindings settings preview search and keyboard navigation", async ({ livePage, api }) => {
  await configureLocalProvider(api);
  await livePage.goto("/orchestrator");
  await livePage.getByRole("tablist", { name: "Orchestrator workspaces" })
    .getByRole("tab", { name: "Configuration", exact: true }).click();

  const tabs = livePage.getByRole("tablist", { name: "Orchestration configuration" });
  const rolesTab = tabs.getByRole("tab", { name: "Roles", exact: true });
  await rolesTab.focus();
  await rolesTab.press("Home");
  await expect(tabs.getByRole("tab", { name: "Providers", exact: true })).toBeFocused();
  await rolesTab.click();

  await livePage.getByLabel("New custom role").fill("Worker Live");
  await livePage.getByRole("button", { name: "Add role" }).click();
  const roleCard = livePage.locator(".orchestration-role-card").filter({ hasText: "Worker Live" });
  const model = await api("/v1/orchestration/models");
  const deployment = model.models.find((item) => item.executable !== false).deployment_key;
  await roleCard.getByLabel("Model for Worker Live").selectOption(deployment);
  await roleCard.locator(".orchestration-binding-editor summary").click();
  await roleCard.getByLabel("New binding id for Worker Live").fill("worker-live-docs");
  await roleCard.getByLabel("New selector key for Worker Live").fill("workflow");
  await roleCard.getByLabel("New selector value for Worker Live").fill("docs");
  await roleCard.getByLabel("Worker Live new binding model").selectOption(deployment);
  await roleCard.getByRole("button", { name: "Add binding" }).click();
  await roleCard.getByLabel("Selectors for Worker Live worker-live-docs").fill("workflow=docs\nrepository=headroom");
  await roleCard.getByLabel("Required capabilities for Worker Live worker-live-docs").fill("reasoning, tool_calling");
  await roleCard.getByLabel("Enabled for Worker Live worker-live-docs").uncheck();
  await livePage.getByRole("button", { name: "Save changes" }).click();
  await expect(livePage.getByText("Changes saved", { exact: true })).toBeVisible();

  let config = await api("/v1/orchestration/config");
  expect(config.roles.some((role) => role.id === "worker-live")).toBe(true);
  expect(config.bindings.find((binding) => binding.id === "worker-live-docs")).toMatchObject({
    enabled: false,
    selectors: { workflow: "docs", repository: "headroom" },
    required_capabilities: ["reasoning", "tool_calling"],
  });

  await tabs.getByRole("tab", { name: "Routing", exact: true }).click();
  await livePage.getByLabel("Enforcement mode").selectOption("relaxed");
  await livePage.getByLabel("Routing policy").selectOption("balanced");
  await livePage.getByLabel("Retries per model").fill("3");
  await livePage.getByLabel("Timeout (seconds)", { exact: true }).fill("90");
  await livePage.getByLabel("Deployment cooldown (seconds)").fill("45");
  await livePage.getByRole("button", { name: "Save changes" }).click();
  config = await api("/v1/orchestration/config");
  expect(config.settings).toMatchObject({
    mode: "relaxed",
    policy: "balanced",
    retries: 3,
    timeout_seconds: 90,
    deployment_cooldown_seconds: 45,
  });

  await livePage.locator(".route-preview select").selectOption("worker-live");
  await livePage.getByRole("button", { name: "Preview" }).click();
  await expect(livePage.locator(".route-preview-result")).toContainText(deployment.split(":").at(-1));

  await tabs.getByRole("tab", { name: "Models", exact: true }).click();
  await livePage.getByLabel("Search models or capabilities").fill("GPT-5.4 Mini");
  await expect(livePage.getByText("GPT-5.4 Mini (E2E)", { exact: true }).first()).toBeVisible();

  await rolesTab.click();
  await roleCard.locator(".orchestration-binding-editor summary").click();
  await roleCard.getByRole("button", { name: "Remove binding" }).last().click();
  await livePage.getByRole("button", { name: "Save changes" }).click();
  config = await api("/v1/orchestration/config");
  expect(config.bindings.some((binding) => binding.id === "worker-live-docs")).toBe(false);
});
