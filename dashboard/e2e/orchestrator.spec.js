import { test, expect } from "@playwright/test";

async function mockRoutingStudio(page, options = {}) {
  const contract = {
    id: "implementation",
    name: "Implementation",
    version: "2",
    state: options.contractState || "shadow",
    baseline_model: "anthropic:sonnet",
    task_types: ["implementation"],
    requirements: { required_capabilities: [], allowed_providers: [] },
    objective: { type: "highest_quality_within_budget", quality_floor: 0.95 },
    reliability: {
      attempt_timeout_seconds: 30,
      total_deadline_seconds: 120,
      attempts_per_deployment: 2,
      maximum_deployments: 2,
    },
    evaluation: {
      minimum_samples: 20,
      unsafe_quality_floor: 0.8,
      maximum_unsafe_rate: 0.01,
      canary_percentage: 0.1,
    },
  };
  await page.route("**/v1/orchestration/contracts/**/simulate*", async (route) => {
    const body = route.request().postDataJSON();
    await route.fulfill({
      status: 200,
      contentType: "application/json",
      body: JSON.stringify({
        executed: false,
        changed: true,
        live_receipt: {
          selected_model: "openai:gpt-5.4-mini",
          selected_deployment: "openai:main:gpt-5.4-mini",
        },
        draft_receipt: {
          contract_id: body.contract.id,
          contract_version: body.contract.version,
          contract_state: "draft",
          selected_model: body.contract.baseline_model,
          selected_deployment: "anthropic:main:sonnet",
          rejected_candidates: [
            { model: "openai:gpt-5.4-mini", reason: "quality_floor" },
          ],
          evidence: { source: "model_registry" },
          reliability_budget: body.contract.reliability,
        },
      }),
    });
  });
  await page.route("**/v1/orchestration/contracts", async (route) => {
    await route.fulfill({
      status: 200,
      contentType: "application/json",
      body: JSON.stringify({
        contracts: options.evidenceStatus ? [contract] : [],
        revision: options.evidenceStatus ? 2 : 0,
      }),
    });
  });
  await page.route("**/v1/orchestration/contracts/**/evidence", async (route) => {
    await route.fulfill({
      status: 200,
      contentType: "application/json",
      body: JSON.stringify({
        contract_id: "implementation",
        contract_version: "2",
        status: options.evidenceStatus || "collecting",
        samples: 20,
        minimum_samples: 20,
        coverage: 1,
        mean_quality: options.evidenceStatus === "quality_blocked" ? 0.89 : 0.97,
        quality_floor: 0.95,
        unsafe_rate: 0.02,
        maximum_unsafe_rate: 0.01,
        acceptance_rate: 0.85,
        fallback_rate: 0.05,
        raw_routed_savings_usd: 12.4,
        quality_safe_savings_usd: 9.8,
        abstention_reasons: { quality_floor: 3 },
      }),
    });
  });
  await page.route("**/v1/orchestration/contracts/**/shadow", async (route) => {
    await route.fulfill({
      status: 200,
      contentType: "application/json",
      body: JSON.stringify({ contract: { ...contract, state: "shadow" }, revision: 3 }),
    });
  });
}

test.describe("Orchestrator Modes", () => {
  test.beforeEach(async ({ page }) => {
    await page.addInitScript(() => {
      window.localStorage.setItem("cutctxAdminKey", "testkey");
    });

    await page.route("**/health", async (route) => {
      await route.fulfill({
        status: 200,
        contentType: "application/json",
        body: JSON.stringify({ status: "healthy", ready: true }),
      });
    });

    await page.route("**/stats?*", async (route) => {
      await route.fulfill({
        status: 200,
        contentType: "application/json",
        body: JSON.stringify({
          config: { orchestrator: false },
          model_routing: {
            mode: "off",
            requested: false,
            available: true,
            configured_routes: 0,
            preset: null,
          },
        }),
      });
    });

    await page.route("**/v1/orchestration/routing/evidence*", async (route) => {
      await route.fulfill({
        status: 200,
        contentType: "application/json",
        body: JSON.stringify({
          schema_version: 1,
          status: "collecting",
          samples: 7,
          sample_progress: { observed: 7, required: 20, fraction: 0.35 },
          constraints: {
            minimum_samples: 20,
            minimum_mean_quality: 0.9,
            maximum_unsafe_rate: 0.01,
            quality_floor: 0.8,
          },
          recommendation: null,
          frontier: [],
          segmented: { minimum_segment_samples: 20, dimensions: {} },
          shadow: { enabled: true, sample_rate: 0.1 },
          scorer: {
            status: "promoted",
            configured: true,
            training_samples: 200,
            minimum_confidence: 0.91,
          },
        }),
      });
    });
  });

  test("creates a coding-agent contract and previews the visible draft", async ({
    page,
  }) => {
    await mockRoutingStudio(page);
    await page.goto("/orchestrator");
    await page.getByRole("button", { name: "New contract" }).click();
    await page.getByLabel("Contract template").selectOption("implementation");
    await page.getByLabel("Quality floor").fill("0.95");
    await page.getByRole("tab", { name: "Simulator" }).click();
    await page.getByRole("button", { name: "Run draft simulation" }).click();
    await expect(
      page.getByText("Draft version 2", { exact: true }),
    ).toBeVisible();
    await expect(
      page.getByText("anthropic:sonnet", { exact: true }),
    ).toBeVisible();
    await page.screenshot({ path: "/tmp/routing-studio-desktop.png", fullPage: true });
  });

  test("routing studio reflows at 390px without page overflow", async ({ page }) => {
    await page.setViewportSize({ width: 390, height: 844 });
    await mockRoutingStudio(page);
    await page.goto("/orchestrator");
    await page.getByRole("button", { name: "New contract" }).click();
    await page.getByRole("tab", { name: "Simulator", exact: true }).click();
    await page.getByRole("button", { name: "Run draft simulation" }).click();
    await expect(page.locator(".sidebar-shell")).not.toHaveClass(/open/);
    const overflow = await page.evaluate(
      () => document.documentElement.scrollWidth - document.documentElement.clientWidth,
    );
    expect(overflow).toBeLessThanOrEqual(1);
    await expect(page.getByRole("button", { name: "Run draft simulation" })).toBeVisible();
    await page.screenshot({ path: "/tmp/routing-studio-mobile.png", fullPage: true });
  });

  test("routing studio tabs use arrow keys and one active tab stop", async ({
    page,
  }) => {
    await mockRoutingStudio(page);
    await page.goto("/orchestrator");
    const contracts = page.getByRole("tab", { name: "Contracts", exact: true });
    await contracts.focus();
    await contracts.press("ArrowRight");
    await expect(
      page.getByRole("tab", { name: "Simulator", exact: true }),
    ).toBeFocused();
    await expect(
      page.getByRole("tabpanel", { name: "Simulator" }),
    ).toBeVisible();
  });

  test("shows quality-safe savings and blocks unsafe promotion", async ({
    page,
  }) => {
    await mockRoutingStudio(page, { evidenceStatus: "quality_blocked" });
    await page.goto("/orchestrator");
    await page.getByRole("tab", { name: "Evidence", exact: true }).click();
    await expect(page.getByText("Quality-safe savings")).toBeVisible();
    await expect(page.getByText("$9.80", { exact: true })).toBeVisible();
    await page.getByRole("tab", { name: "Rollouts", exact: true }).click();
    await expect(
      page.getByRole("button", { name: "Promote to canary" }),
    ).toBeDisabled();
    await expect(page.getByText("Quality floor not met").first()).toBeVisible();
  });

  test("starts a draft in shadow without requiring promotion evidence", async ({
    page,
  }) => {
    await mockRoutingStudio(page, {
      evidenceStatus: "collecting",
      contractState: "draft",
    });
    await page.goto("/orchestrator");
    await page.getByRole("tab", { name: "Rollouts", exact: true }).click();
    const start = page.getByRole("button", { name: "Start shadow" });
    await expect(start).toBeEnabled();
    await start.click();
    await expect(page.getByText("Version 2", { exact: true })).toBeVisible();
  });

  test("selecting a routing mode posts orchestrator_mode", async ({ page }) => {
    const postUrls = [];
    const postedBodies = [];
    await page.route("**/config/flags*", async (route) => {
      if (route.request().method() === "POST") {
        postUrls.push(new URL(route.request().url()).pathname);
        postedBodies.push(route.request().postDataJSON());
        await route.fulfill({
          status: 200,
          contentType: "application/json",
          body: JSON.stringify({
            applied_live: { orchestrator_mode: { mode: "balanced" } },
          }),
        });
        return;
      }
      await route.fulfill({
        status: 200,
        contentType: "application/json",
        body: JSON.stringify({}),
      });
    });

    await page.goto("/orchestrator");

    await expect(
      page.locator("h2").filter({ hasText: "Routing mode control" }),
    ).toBeVisible();
    await expect(
      page.getByText("after role bindings are locked", { exact: false }),
    ).toBeVisible();
    await expect(page.getByRole("button", { name: "Off" })).toBeVisible();
    await expect(page.getByRole("button", { name: "Balanced" })).toBeVisible();
    await expect(
      page.getByRole("button", { name: "Aggressive" }),
    ).toBeVisible();
    await expect(
      page.getByText("Routing evidence", { exact: true }),
    ).toBeVisible();
    await expect(
      page.getByText("Collecting evidence", { exact: true }),
    ).toBeVisible();
    await expect(
      page.getByText("7 / 20 samples", { exact: true }),
    ).toBeVisible();
    await expect(
      page.getByText("Promoted calibrated scorer", { exact: true }),
    ).toBeVisible();
    await expect(
      page.getByText("200 training samples · minimum confidence 0.91", {
        exact: true,
      }),
    ).toBeVisible();

    await page.getByRole("button", { name: "Balanced" }).click();

    await expect.poll(() => postUrls.length).toBe(1);
    await expect(postUrls).toEqual(["/config/flags"]);
    await expect(postedBodies[0]).toMatchObject({
      orchestrator_mode: "balanced",
    });
  });

  test("publishes a polling snapshot when it supersedes a delayed initial load", async ({ page }) => {
    let requests = 0;
    const initialResolvers = [];
    await page.unroute("**/stats?*");
    await page.route("**/stats?*", async (route) => {
      requests += 1;
      if (requests <= 2) {
        await new Promise((resolve) => initialResolvers.push(resolve));
      }
      await route.fulfill({
        status: 200,
        contentType: "application/json",
        body: JSON.stringify({
          config: { orchestrator: false },
          model_routing: { mode: "off", requested: false },
        }),
      });
    });

    await page.goto("/orchestrator");
    await expect(page.getByRole("button", { name: "Off" })).toBeVisible({ timeout: 7_000 });
    initialResolvers.forEach((resolve) => resolve());
  });

  test("keeps the established page mounted and confirms a mode without waiting for history", async ({ page }) => {
    let delayRefresh = false;
    let releaseRefresh;
    const refreshGate = new Promise((resolve) => {
      releaseRefresh = resolve;
    });
    let historyRequested;
    const historyGate = new Promise((resolve) => {
      historyRequested = resolve;
    });

    await page.route("**/stats?*", async (route) => {
      if (delayRefresh) {
        await refreshGate;
      }
      await route.fulfill({
        status: 200,
        contentType: "application/json",
        body: JSON.stringify({
          config: { orchestrator: true },
          model_routing: { mode: delayRefresh ? "balanced" : "off", requested: delayRefresh },
        }),
      });
    });
    await page.route("**/stats-history", async (route) => {
      historyRequested();
      await historyGate;
      await route.fulfill({ status: 200, contentType: "application/json", body: JSON.stringify([]) });
    });
    await page.route("**/config/flags*", async (route) => {
      if (route.request().method() === "POST") {
        await route.fulfill({
          status: 200,
          contentType: "application/json",
          body: JSON.stringify({ applied_live: { orchestrator_mode: { mode: "balanced" } } }),
        });
        return;
      }
      await route.fulfill({ status: 200, contentType: "application/json", body: JSON.stringify({}) });
    });

    await page.goto("/orchestrator");
    await expect(page.getByRole("button", { name: "Off" })).toHaveAttribute("aria-pressed", "true");
    delayRefresh = true;
    await page.getByRole("button", { name: "Balanced" }).click();
    await expect(page.locator(".page-stack")).toBeVisible();
    await expect(page.getByRole("button", { name: "Balanced" })).toHaveAttribute("aria-pressed", "true");

    await releaseRefresh();
    await expect(page.getByText("Routing balanced", { exact: true })).toBeVisible();
    await expect(page.getByText("pending confirmation", { exact: false })).toHaveCount(0);
    await historyRequested;
  });

  test("requires an exact acknowledgement and keeps optimistic mode pending after stale or failed refresh", async ({ page }) => {
    let postCount = 0;
    let statsRequests = 0;
    await page.route("**/stats?*", async (route) => {
      statsRequests += 1;
      if (statsRequests === 2) {
        await route.fulfill({ status: 503, contentType: "application/json", body: JSON.stringify({ detail: "unavailable" }) });
        return;
      }
      await route.fulfill({
        status: 200,
        contentType: "application/json",
        body: JSON.stringify({ config: { orchestrator: false }, model_routing: { mode: "off", requested: false } }),
      });
    });
    await page.route("**/config/flags*", async (route) => {
      if (route.request().method() !== "POST") {
        await route.fulfill({ status: 200, contentType: "application/json", body: JSON.stringify({}) });
        return;
      }
      postCount += 1;
      await route.fulfill({
        status: 200,
        contentType: "application/json",
        body: JSON.stringify(postCount === 1 ? { applied_live: {} } : { applied_live: { orchestrator_mode: { mode: "balanced" } } }),
      });
    });

    await page.goto("/orchestrator");
    await page.getByRole("button", { name: "Balanced" }).click();
    await expect(page.getByText("acknowledge", { exact: false })).toBeVisible();
    await expect(page.getByRole("button", { name: "Off" })).toHaveAttribute("aria-pressed", "true");

    await page.getByRole("button", { name: "Balanced" }).click();
    await expect(page.getByRole("button", { name: "Balanced" })).toHaveAttribute("aria-pressed", "true");
    await expect(page.getByText("pending confirmation", { exact: false })).toBeVisible();
    await expect(page.locator(".page-stack")).toBeVisible();
  });

  test("shows the authenticated harness contract without implying model compatibility", async ({
    page,
  }) => {
    await page.route("**/v1/orchestration/config*", async (route) => {
      await route.fulfill({
        status: 200,
        contentType: "application/json",
        body: JSON.stringify({ roles: [], bindings: [], settings: {} }),
      });
    });
    await page.route("**/v1/orchestration/providers*", async (route) => {
      await route.fulfill({
        status: 200,
        contentType: "application/json",
        body: JSON.stringify({ catalog: [], accounts: [] }),
      });
    });
    await page.route("**/v1/orchestration/models*", async (route) => {
      await route.fulfill({
        status: 200,
        contentType: "application/json",
        body: JSON.stringify({ models: [] }),
      });
    });
    await page.route("**/v1/orchestration/executions*", async (route) => {
      await route.fulfill({
        status: 200,
        contentType: "application/json",
        body: JSON.stringify({ executions: [] }),
      });
    });
    await page.route(
      "**/v1/orchestration/harness-compatibility*",
      async (route) => {
        await route.fulfill({
          status: 200,
          contentType: "application/json",
          body: JSON.stringify({
            manifest_version: 1,
            harnesses: [
              {
                id: "codex",
                support_level: "native",
                routing: true,
                artifact_handoffs: true,
                hidden_session_sharing: false,
                notes: "Use native adapter/proxy paths.",
              },
            ],
          }),
        });
      },
    );

    await page.goto("/orchestrator");
    await page.getByRole("tab", { name: "Harnesses" }).click();

    await expect(
      page.getByRole("heading", { name: "Harness compatibility" }),
    ).toBeVisible();
    await expect(page.getByText("Codex", { exact: true })).toBeVisible();
    await expect(page.getByText("Native", { exact: true })).toBeVisible();
    await expect(
      page.getByText("Routing supported", { exact: true }),
    ).toBeVisible();
    await expect(
      page.getByText("Model deployment availability is verified separately.", {
        exact: true,
      }),
    ).toBeVisible();
  });

  test("keeps routing controls available when the harness manifest cannot load", async ({
    page,
  }) => {
    await page.route("**/v1/orchestration/config*", async (route) => {
      await route.fulfill({
        status: 200,
        contentType: "application/json",
        body: JSON.stringify({ roles: [], bindings: [], settings: {} }),
      });
    });
    await page.route("**/v1/orchestration/providers*", async (route) => {
      await route.fulfill({
        status: 200,
        contentType: "application/json",
        body: JSON.stringify({ catalog: [], accounts: [] }),
      });
    });
    await page.route("**/v1/orchestration/models*", async (route) => {
      await route.fulfill({
        status: 200,
        contentType: "application/json",
        body: JSON.stringify({ models: [] }),
      });
    });
    await page.route("**/v1/orchestration/executions*", async (route) => {
      await route.fulfill({
        status: 200,
        contentType: "application/json",
        body: JSON.stringify({ executions: [] }),
      });
    });
    await page.route(
      "**/v1/orchestration/harness-compatibility*",
      async (route) => {
        await route.fulfill({
          status: 503,
          contentType: "application/json",
          body: JSON.stringify({ detail: "unavailable" }),
        });
      },
    );

    await page.goto("/orchestrator");
    await expect(page.getByRole("tab", { name: "Routing" })).toBeVisible();
    await page.getByRole("tab", { name: "Harnesses" }).click();
    await expect(
      page.getByText("Harness compatibility is unavailable."),
    ).toBeVisible();
  });

  test("shows route eligibility evidence in the deterministic preview", async ({
    page,
  }) => {
    await page.route("**/v1/orchestration/config*", async (route) => {
      await route.fulfill({
        status: 200,
        contentType: "application/json",
        body: JSON.stringify({
          roles: [{ id: "worker", name: "Worker" }],
          bindings: [
            { id: "worker", role: "worker", model: "openai:account-a:shared" },
          ],
          settings: {
            mode: "strict",
            policy: "role_locked",
            retries: 1,
            timeout_seconds: 120,
          },
        }),
      });
    });
    await page.route("**/v1/orchestration/providers*", async (route) => {
      await route.fulfill({
        status: 200,
        contentType: "application/json",
        body: JSON.stringify({ catalog: [], accounts: [] }),
      });
    });
    await page.route("**/v1/orchestration/models*", async (route) => {
      await route.fulfill({
        status: 200,
        contentType: "application/json",
        body: JSON.stringify({ models: [] }),
      });
    });
    await page.route("**/v1/orchestration/executions*", async (route) => {
      await route.fulfill({
        status: 200,
        contentType: "application/json",
        body: JSON.stringify({ executions: [] }),
      });
    });
    await page.route(
      "**/v1/orchestration/harness-compatibility*",
      async (route) => {
        await route.fulfill({
          status: 200,
          contentType: "application/json",
          body: JSON.stringify({ harnesses: [] }),
        });
      },
    );
    await page.route("**/v1/orchestration/route*", async (route) => {
      await route.fulfill({
        status: 200,
        contentType: "application/json",
        body: JSON.stringify({
          provider: "openai",
          actual_model: "shared",
          reason: "equivalent_deployment_selected",
          fallback_used: false,
          required_capabilities: ["tool_calling"],
          policy_constraints: {
            allowed_providers: ["openai"],
            allowed_regions: [],
            allowed_data_classifications: [],
          },
          selection_evidence: {
            scores: [{ deployment: "openai:account-b:shared", score: 0.94 }],
            rejected: [
              { model: "openai:account-a:shared", reason: "cooling_down" },
            ],
          },
        }),
      });
    });

    await page.goto("/orchestrator");
    await page.getByRole("tab", { name: "Routing" }).click();
    await page.locator(".route-preview select").selectOption("worker");
    await page.getByRole("button", { name: "Preview" }).click();

    await expect(
      page.getByText("Candidate scores", { exact: true }),
    ).toBeVisible();
    await expect(
      page.getByText("openai:account-b:shared", { exact: true }),
    ).toBeVisible();
    await expect(page.getByText("Score 0.94", { exact: true })).toBeVisible();
    await expect(
      page.getByText("Rejected candidates", { exact: true }),
    ).toBeVisible();
    await expect(page.getByText("cooling_down", { exact: true })).toBeVisible();
    await expect(
      page.getByText("Required capabilities", { exact: true }),
    ).toBeVisible();
    await expect(page.getByText("tool_calling", { exact: true })).toBeVisible();
    await expect(
      page.getByText("Provider policy: openai", { exact: true }),
    ).toBeVisible();
  });

  test("exposes deployment cooldown beside retries and timeout", async ({
    page,
  }) => {
    await page.route("**/v1/orchestration/config*", async (route) => {
      await route.fulfill({
        status: 200,
        contentType: "application/json",
        body: JSON.stringify({
          roles: [],
          bindings: [],
          settings: {
            mode: "strict",
            policy: "role_locked",
            retries: 1,
            timeout_seconds: 120,
            deployment_cooldown_seconds: 45,
          },
        }),
      });
    });
    await page.route("**/v1/orchestration/providers*", async (route) => {
      await route.fulfill({
        status: 200,
        contentType: "application/json",
        body: JSON.stringify({ catalog: [], accounts: [] }),
      });
    });
    await page.route("**/v1/orchestration/models*", async (route) => {
      await route.fulfill({
        status: 200,
        contentType: "application/json",
        body: JSON.stringify({ models: [] }),
      });
    });
    await page.route("**/v1/orchestration/executions*", async (route) => {
      await route.fulfill({
        status: 200,
        contentType: "application/json",
        body: JSON.stringify({ executions: [] }),
      });
    });
    await page.route(
      "**/v1/orchestration/harness-compatibility*",
      async (route) => {
        await route.fulfill({
          status: 200,
          contentType: "application/json",
          body: JSON.stringify({ harnesses: [] }),
        });
      },
    );

    await page.goto("/orchestrator");
    await page.getByRole("tab", { name: "Routing" }).click();

    await expect(page.getByLabel("Deployment cooldown (seconds)")).toHaveValue(
      "45",
    );
  });

  test("shows weighted equivalent allocation evidence in the route preview", async ({
    page,
  }) => {
    await page.route("**/v1/orchestration/config*", async (route) => {
      await route.fulfill({
        status: 200,
        contentType: "application/json",
        body: JSON.stringify({
          roles: [{ id: "worker", name: "Worker" }],
          bindings: [],
          settings: {},
        }),
      });
    });
    await page.route("**/v1/orchestration/providers*", async (route) => {
      await route.fulfill({
        status: 200,
        contentType: "application/json",
        body: JSON.stringify({ catalog: [], accounts: [] }),
      });
    });
    await page.route("**/v1/orchestration/models*", async (route) => {
      await route.fulfill({
        status: 200,
        contentType: "application/json",
        body: JSON.stringify({ models: [] }),
      });
    });
    await page.route("**/v1/orchestration/executions*", async (route) => {
      await route.fulfill({
        status: 200,
        contentType: "application/json",
        body: JSON.stringify({ executions: [] }),
      });
    });
    await page.route(
      "**/v1/orchestration/harness-compatibility*",
      async (route) => {
        await route.fulfill({
          status: 200,
          contentType: "application/json",
          body: JSON.stringify({ harnesses: [] }),
        });
      },
    );
    await page.route("**/v1/orchestration/route*", async (route) => {
      await route.fulfill({
        status: 200,
        contentType: "application/json",
        body: JSON.stringify({
          provider: "openai",
          actual_model: "shared",
          reason: "equivalent_deployment_selected",
          fallback_used: false,
          selection_evidence: {
            strategy: "equivalent_weighted",
            cohort_fraction: 0.42,
            eligible_weights: [
              { deployment: "openai:account-b:shared", weight: 0.25 },
            ],
            rejected: [],
          },
        }),
      });
    });

    await page.goto("/orchestrator");
    await page.getByRole("tab", { name: "Routing" }).click();
    await page.locator(".route-preview select").selectOption("worker");
    await page.getByRole("button", { name: "Preview" }).click();

    await expect(
      page.getByText("Weighted allocation", { exact: true }),
    ).toBeVisible();
    await expect(page.getByText("Cohort 0.42", { exact: true })).toBeVisible();
    await expect(page.getByText("Weight 0.25", { exact: true })).toBeVisible();
  });
});
