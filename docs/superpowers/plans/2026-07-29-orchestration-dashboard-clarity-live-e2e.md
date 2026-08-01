# Orchestration Dashboard Clarity and Live E2E Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [x]`) syntax for tracking.

**Goal:** Reorganize the Orchestrator dashboard into Operate, Contracts, and Configuration workspaces and prove every exposed mutation through browser tests backed by a real isolated FastAPI proxy.

**Architecture:** Split primary workspace navigation and the Operate presentation into focused React components while preserving the existing Routing Studio and Orchestration Studio as nested tools. Add a live Playwright fixture that launches the production proxy app with temporary stores and deterministic local provider behavior; keep mocked tests for concurrency and forced-failure cases.

**Tech Stack:** React 19, Vite 8, Playwright 1.61, FastAPI, pytest, existing Cutctx dashboard and orchestration APIs.

## Global Constraints

- Preserve the existing Cutctx visual tokens and component language in Evolve mode.
- Keep Off, Auto, and Aggressive routing semantics unchanged.
- Keep all advanced orchestration controls available.
- Do not call paid or external providers from tests.
- A live E2E test must use production HTTP routes without `page.route()` fulfillment.
- Every production behavior change follows a failing-test-first cycle.
- All shell commands use the repository-required `rtk` prefix.

---

### Task 1: Primary Workspace Navigation

**Files:**
- Create: `dashboard/src/components/OrchestratorWorkspaceTabs.jsx`
- Modify: `dashboard/src/pages/Orchestrator.jsx`
- Modify: `dashboard/src/index.css`
- Test: `dashboard/e2e/orchestrator.spec.js`

**Interfaces:**
- Consumes: `value: "operate" | "contracts" | "configuration"`, `onChange(nextWorkspace)`.
- Produces: an ARIA tablist with roving focus and three exclusive tabpanels.

- [x] **Step 1: Write failing navigation and hierarchy tests**

Add tests that assert Operate is the only visible primary workspace on load, Contracts and Configuration reveal their existing studios, and ArrowRight, Home, and End move focus and selection.

```js
test("separates operate contracts and configuration into primary workspaces", async ({ page }) => {
  await installOrchestratorRoutes(page);
  await page.goto("/orchestrator");
  await expect(page.getByRole("tabpanel", { name: "Operate" })).toBeVisible();
  await expect(page.getByText("Workload contracts, before provider calls")).toBeHidden();
  await page.getByRole("tab", { name: "Contracts", exact: true }).click();
  await expect(page.getByText("Workload contracts, before provider calls")).toBeVisible();
  await page.getByRole("tab", { name: "Configuration", exact: true }).click();
  await expect(page.getByText("Provider-neutral model control plane")).toBeVisible();
});
```

- [x] **Step 2: Run the new test and confirm the current stacked page fails**

Run: `cd dashboard && rtk proxy env CI=true npx playwright test e2e/orchestrator.spec.js --project=chromium --grep "separates operate"`

Expected: FAIL because the primary workspace tabs and tabpanels do not exist.

- [x] **Step 3: Implement the accessible workspace component**

Create `OrchestratorWorkspaceTabs` with `WORKSPACES`, roving `tabIndex`, ArrowLeft, ArrowRight, Home, and End handling. In `Orchestrator.jsx`, store `workspace`, render the selector before page content, and render only the selected workspace.

```jsx
<OrchestratorWorkspaceTabs value={workspace} onChange={setWorkspace} />
<section role="tabpanel" aria-label="Operate" hidden={workspace !== "operate"}>...</section>
<section role="tabpanel" aria-label="Contracts" hidden={workspace !== "contracts"}><RoutingStudio /></section>
<section role="tabpanel" aria-label="Configuration" hidden={workspace !== "configuration"}><OrchestrationStudio searchQuery={searchQuery} /></section>
```

- [x] **Step 4: Add responsive workspace styles**

Use existing CSS variables. Make the primary tabs a three-column segmented surface on desktop and a horizontally scrollable, 44px-tall control below 700px. Ensure hidden tabpanels do not consume layout space.

- [x] **Step 5: Run focused and existing mocked browser tests**

Run: `cd dashboard && rtk proxy env CI=true npx playwright test e2e/orchestrator.spec.js --project=chromium`

Expected: all orchestration mocked tests pass.

- [x] **Step 6: Commit**

Run: `rtk git add dashboard/src/components/OrchestratorWorkspaceTabs.jsx dashboard/src/pages/Orchestrator.jsx dashboard/src/index.css dashboard/e2e/orchestrator.spec.js && rtk proxy env GIT_EDITOR=true git commit -m "feat(dashboard): organize orchestrator into task workspaces"`

### Task 2: Operate Command Surface and Diagnostics Disclosure

**Files:**
- Create: `dashboard/src/components/OrchestratorOperate.jsx`
- Modify: `dashboard/src/pages/Orchestrator.jsx`
- Modify: `dashboard/src/index.css`
- Test: `dashboard/e2e/orchestrator.spec.js`

**Interfaces:**
- Consumes: normalized routing mode, update callbacks, stats, routing evidence, policy/provider/Safe Savings state, and `onNavigate(workspace)`.
- Produces: compact live controls, deterministic next-action copy, and collapsed diagnostics.

- [x] **Step 1: Write failing tests for hierarchy and recommendations**

Add cases for routing off with no roles, evidence ready, unhealthy provider, diagnostics collapsed by default, and diagnostic errors staying hidden until expanded.

```js
await expect(page.getByRole("heading", { name: "Route requests" })).toBeVisible();
await expect(page.getByText("Set up role assignments")).toBeVisible();
await expect(page.getByRole("button", { name: "Diagnostics and compatibility" })).toHaveAttribute("aria-expanded", "false");
await expect(page.getByText("Provider policy unavailable", { exact: false })).toBeHidden();
```

- [x] **Step 2: Run the tests and confirm they fail because Operate is not extracted**

Run: `cd dashboard && rtk proxy env CI=true npx playwright test e2e/orchestrator.spec.js --project=chromium --grep "recommended action|diagnostics"`

Expected: FAIL on missing command heading or disclosure.

- [x] **Step 3: Extract Operate and implement recommendation derivation**

Create a pure `getOrchestratorRecommendation` export for unit-like browser assertions and an `OrchestratorOperate` component. Move routing mode, savings, evidence summary, Safe Savings, policy, readiness, and legacy provider panels from the page into the component. Keep the command section outside `<details>` and place diagnostics inside it.

```js
export function getOrchestratorRecommendation({ configAvailable, roleCount, mode, evidenceStatus, providers }) {
  if (!configAvailable) return { kind: "blocked", label: "Update the proxy", target: null };
  if (providers.some((provider) => provider.healthy === false)) return { kind: "warning", label: "Check provider health", target: "configuration" };
  if (mode === "off" && roleCount === 0) return { kind: "setup", label: "Set up role assignments", target: "configuration" };
  if (evidenceStatus === "ready") return { kind: "release", label: "Review rollout gates", target: "contracts" };
  if (evidenceStatus === "collecting") return { kind: "observe", label: "Continue collecting evidence", target: null };
  if (mode === "off") return { kind: "enable", label: "Start with Auto routing", target: null };
  return { kind: "healthy", label: "Routing is operational", target: null };
}
```

- [x] **Step 4: Verify existing mode, Safe Savings, and provider action tests stay green**

Run: `cd dashboard && rtk proxy env CI=true npx playwright test e2e/orchestrator.spec.js --project=chromium`

Expected: all mocked orchestration tests pass.

- [x] **Step 5: Commit**

Run: `rtk git add dashboard/src/components/OrchestratorOperate.jsx dashboard/src/pages/Orchestrator.jsx dashboard/src/index.css dashboard/e2e/orchestrator.spec.js && rtk proxy env GIT_EDITOR=true git commit -m "feat(dashboard): focus orchestrator operate workflow"`

### Task 3: Contract and Configuration State Clarity

**Files:**
- Modify: `dashboard/src/components/routing-studio/RoutingStudio.jsx`
- Modify: `dashboard/src/components/routing-studio/RolloutPanel.jsx`
- Modify: `dashboard/src/components/OrchestrationStudio.jsx`
- Modify: `dashboard/src/index.css`
- Test: `dashboard/e2e/orchestrator.spec.js`

**Interfaces:**
- Produces: visible contract lifecycle steps, rollout gate explanations, and `clean | dirty | saving | saved | failed` configuration save state.

- [x] **Step 1: Write failing tests for lifecycle and dirty persistence state**

```js
await page.getByRole("tab", { name: "Contracts", exact: true }).click();
await expect(page.getByLabel("Contract lifecycle")).toContainText("Draft");
await page.getByRole("tab", { name: "Configuration", exact: true }).click();
await page.getByRole("tab", { name: "Routing", exact: true }).click();
await page.getByLabel("Retries per model").fill("3");
await expect(page.getByText("Unsaved changes")).toBeVisible();
```

- [x] **Step 2: Run and confirm failure on missing lifecycle/save state**

Run: `cd dashboard && rtk proxy env CI=true npx playwright test e2e/orchestrator.spec.js --project=chromium --grep "lifecycle|unsaved changes"`

- [x] **Step 3: Implement lifecycle indicator and controlled config updates**

Add the five-stage lifecycle above nested contract tabs. In Orchestration Studio, centralize local edits through `updateConfig(next)` so every edit marks the form dirty. Save sets `saving`, then `saved` only after the PUT response; failure retains dirty state and displays the error.

- [x] **Step 4: Make tables and mobile header non-obscuring**

Label table scroll regions and add Orchestrator-route mobile CSS that keeps dashboard chrome in document flow. Add reduced-motion and 44px primary-action rules.

- [x] **Step 5: Run mocked browser suite and capture desktop/mobile screenshots**

Run: `cd dashboard && rtk proxy env CI=true npx playwright test e2e/orchestrator.spec.js --project=chromium`

- [x] **Step 6: Commit**

Run: `rtk git add dashboard/src/components/routing-studio/RoutingStudio.jsx dashboard/src/components/routing-studio/RolloutPanel.jsx dashboard/src/components/OrchestrationStudio.jsx dashboard/src/index.css dashboard/e2e/orchestrator.spec.js && rtk proxy env GIT_EDITOR=true git commit -m "feat(dashboard): clarify orchestration lifecycle and save state"`

### Task 4: Isolated Live Proxy Browser Fixture

**Files:**
- Create: `tests/fixtures/orchestration_e2e_server.py`
- Create: `dashboard/e2e/fixtures/live-proxy.js`
- Modify: `dashboard/playwright.config.js`
- Create: `dashboard/e2e/orchestrator-live.spec.js`

**Interfaces:**
- Python launcher prints one JSON readiness line containing `proxy_url`, `admin_key`, and `provider_url`.
- JS fixture exposes `livePage`, `proxyUrl`, `adminKey`, and `api(path, options)`.

- [x] **Step 1: Write a failing live smoke test**

```js
test("@live-proxy loads authenticated production orchestration state", async ({ livePage, api }) => {
  await livePage.goto("/orchestrator");
  await expect(livePage.getByRole("tab", { name: "Operate" })).toBeVisible();
  const config = await api("/v1/orchestration/config");
  expect(config.version).toBe(1);
});
```

- [x] **Step 2: Run and confirm failure because the fixture does not exist**

Run: `cd dashboard && rtk proxy env CI=true npx playwright test e2e/orchestrator-live.spec.js --project=live-proxy`

Expected: FAIL resolving `./fixtures/live-proxy.js` or the missing project.

- [x] **Step 3: Implement the Python production-app launcher**

Use `tempfile.TemporaryDirectory`, choose free loopback ports, configure the normal admin key and orchestration storage environment, create the production app through the repository app factory, and run uvicorn. Start a local FastAPI provider stub that supports the production connection-test and model-discovery requests. On SIGTERM, close both servers and delete temporary state.

- [x] **Step 4: Implement the Playwright worker fixture**

Spawn the Python launcher with `uv run python`, parse its JSON readiness line, inject `cutctxAdminKey` and the supported proxy base URL before page load, expose authenticated API requests, and terminate the child in teardown. Do not intercept production API requests.

- [x] **Step 5: Add the `live-proxy` project and make the smoke test green**

Configure the project to match only `orchestrator-live.spec.js`, use one worker for isolated state, and retain the existing Chromium project for mocked tests.

- [x] **Step 6: Commit**

Run: `rtk git add tests/fixtures/orchestration_e2e_server.py dashboard/e2e/fixtures/live-proxy.js dashboard/e2e/orchestrator-live.spec.js dashboard/playwright.config.js && rtk proxy env GIT_EDITOR=true git commit -m "test(dashboard): add live orchestration proxy fixture"`

### Task 5: Complete the Live Control Matrix

**Files:**
- Modify: `dashboard/e2e/orchestrator-live.spec.js`
- Modify when a live test exposes a defect: the owning dashboard or backend file only.

**Interfaces:**
- Consumes: the live fixture and production endpoints.
- Produces: direct browser evidence for every control row in the design spec.

- [x] **Step 1: Add failing Operate live tests**

Cover Off/Auto/Aggressive persistence, Safe Savings confirmation/off state, and provider enable/disable. Assert via API and page reload.

- [x] **Step 2: Run failing Operate tests, implement only exposed defects, rerun green**

Run: `cd dashboard && rtk proxy env CI=true npx playwright test e2e/orchestrator-live.spec.js --project=live-proxy --grep "Operate"`

- [x] **Step 3: Add failing Contracts live tests**

Cover draft save/reload, simulation with zero provider calls, shadow, canary, active, pause, and rollback. Seed evidence only through production API/store affordances defined by the fixture.

- [x] **Step 4: Run failing Contracts tests, implement only exposed defects, rerun green**

Run: `cd dashboard && rtk proxy env CI=true npx playwright test e2e/orchestrator-live.spec.js --project=live-proxy --grep "Contracts"`

- [x] **Step 5: Add failing Configuration live tests**

Cover provider account plus credential, connection test, model refresh, credential removal, role/default binding save, selector binding add/edit/toggle/delete, routing settings save, route preview, search, and keyboard tab navigation.

- [x] **Step 6: Run failing Configuration tests, implement only exposed defects, rerun green**

Run: `cd dashboard && rtk proxy env CI=true npx playwright test e2e/orchestrator-live.spec.js --project=live-proxy --grep "Configuration"`

- [x] **Step 7: Add deterministic mocked rejection and recovery cases per mutation family**

Keep these in `orchestrator.spec.js`: duplicate-submit disabling, server rejection, no false persistence, and retry/reload recovery. Use route mocks only for the forced failure.

- [x] **Step 8: Run both orchestration browser suites**

Run: `cd dashboard && rtk proxy env CI=true npx playwright test e2e/orchestrator.spec.js e2e/orchestrator-live.spec.js`

- [x] **Step 9: Commit**

Run: `rtk git add dashboard/e2e dashboard/src cutctx tests/fixtures/orchestration_e2e_server.py && rtk proxy env GIT_EDITOR=true git commit -m "test(dashboard): cover live orchestration controls end to end"`

### Task 6: Full Verification and Completion Audit

**Files:**
- Modify if needed: `docs/superpowers/plans/2026-07-29-orchestration-dashboard-clarity-live-e2e.md` to check completed steps.
- Create: `audit/orchestration-dashboard-live-e2e-2026-07-29.md`

**Interfaces:**
- Produces: a requirement-by-requirement evidence record linked to commands and artifacts.

- [x] **Step 1: Run focused Python verification**

Run: `rtk proxy env CI=true uv run pytest -q tests/test_dashboard_orchestrator.py tests/test_dashboard_orchestrator_policy_e2e.py tests/test_orchestration_api.py tests/test_orchestration_workflow.py tests/test_orchestration_platform.py`

Expected: zero failures and no orchestration-related skips.

- [x] **Step 2: Run dashboard unit, mocked browser, and live browser tests**

Run: `cd dashboard && rtk proxy env CI=true npm test && rtk proxy env CI=true npx playwright test e2e/orchestrator.spec.js e2e/orchestrator-live.spec.js`

Expected: zero failures.

- [x] **Step 3: Run lint and production build**

Run: `cd dashboard && rtk proxy env CI=true npm run lint && rtk proxy env CI=true npm run build`

Expected: zero ESLint warnings and successful Vite build.

- [x] **Step 4: Capture and inspect visual evidence**

Save desktop and 390px screenshots under `output/playwright/orchestrator/`. Inspect each image. Assert document overflow is at most one pixel, active controls are not covered, and all three workspaces remain reachable.

- [x] **Step 5: Write the completion audit**

Map every control-matrix row and verification requirement to a test name, command result, or screenshot. Mark missing evidence as incomplete and continue implementation until the matrix has no gaps.

- [x] **Step 6: Run final repository hygiene checks and commit**

Run: `rtk git diff --check && rtk git status`

Run: `rtk git add audit/orchestration-dashboard-live-e2e-2026-07-29.md docs/superpowers/plans/2026-07-29-orchestration-dashboard-clarity-live-e2e.md output/playwright/orchestrator && rtk proxy env GIT_EDITOR=true git commit -m "docs: record orchestration dashboard live e2e evidence"`
