# Orchestration Routing and Roles Dashboard Refresh Implementation Plan

> For agentic workers: REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (-) syntax for tracking.

**Goal:** Fix the Orchestrator dashboard so routing and roles are correct, fully functional, and consistent with the backend orchestration contract while preserving the existing six-tab structure.

**Architecture:** Keep the current dashboard shell and tab navigation, but split responsibilities cleanly across provider management, model discovery, advanced role bindings, routing policy controls, and read-only execution history. The main correction is progressive disclosure in the Roles tab: simple default assignment stays fast, while selector-driven bindings and routing metadata live in an expandable advanced editor that writes the same config contract the backend already validates.

**Tech Stack:** React 19, Vite, Lucide icons, dashboard JSON API, Playwright, pytest.

## Global Constraints

- Preserve the existing six tabs: Providers, Models, Harnesses, Roles, Routing, Activity.
- Do not change the meaning of strict versus relaxed enforcement.
- Use the existing orchestration API contracts under /v1/orchestration.
- Keep routing decisions deterministic and previewable from the selected role.
- Do not introduce new backend endpoints.

---

### Task 1: Fix the OrchestrationStudio tab functionality

**Files:**
- Modify: dashboard/src/components/OrchestrationStudio.jsx
- Create: dashboard/src/components/RoleBindingEditor.jsx
- Modify: tests/test_dashboard_orchestrator_policy_e2e.py

**Interfaces:**
- Consumes: orchestration config, models, providers, harnesses, and route preview API responses
- Produces: a working tabbed control surface with model search, role assignment, and deterministic preview coverage

- [ ] **Step 1: Add the failing regression test for the Models tab search**

    def test_orchestrator_models_tab_search_filters_without_error() -> None:
        with sync_playwright() as pw:
            browser = pw.chromium.launch()
            try:
                page = browser.new_page(viewport={"width": 1440, "height": 1400})
                page.add_init_script(
                    """
                    window.localStorage.setItem('cutctxAdminKey', 'testkey');
                    """
                )
                _install_dashboard_routes(page)

                page.goto("http://cutctx.local/dashboard/orchestrator")
                page.wait_for_load_state("networkidle")
                page.get_by_role("tab", name="Models").click()

                search = page.get_by_label("Search models or capabilities")
                expect(search).to_be_visible()
                search.fill("gpt")
                expect(page.get_by_text("GPT-5.4 Mini", exact=True)).to_be_visible()
            finally:
                browser.close()

- [ ] **Step 2: Implement the missing search state and keep the model list defensive**

Wire modelSearch into local React state, reuse the existing filter logic, and keep the empty state readable when no models match or no models exist.

- [ ] **Step 3: Add an advanced binding editor without removing the simple default assignment**

Keep the current role row selector as the default path, and move selector-driven binding edits into RoleBindingEditor.jsx so each role can manage:

- binding id;
- selectors;
- required capabilities;
- fallback chain;
- equivalent deployments;
- enabled state;
- default model assignment.

The role row should remain the quick path for common assignments; the advanced editor should surface only when an operator wants full routing control.

- [ ] **Step 4: Add route-preview coverage for role-specific evidence**

Extend the dashboard test fixture so the preview path proves the selected role, provider/model, required capabilities, policy constraints, and fallback/equivalent-deployment evidence render correctly.

- [ ] **Step 5: Run the targeted OrchestrationStudio regression slice**

Run: rtk pytest tests/test_dashboard_orchestrator_policy_e2e.py -q

Expected: the dashboard policy E2E slice passes and the Models tab no longer throws at render time.

- [ ] **Step 6: Commit the component and test updates**

    git add dashboard/src/components/OrchestrationStudio.jsx dashboard/src/components/RoleBindingEditor.jsx tests/test_dashboard_orchestrator_policy_e2e.py
    git commit -m "fix(dashboard): repair orchestration routing and roles tabs"

### Task 2: Tighten the Orchestrator routing mode controls

**Files:**
- Modify: dashboard/src/pages/Orchestrator.jsx
- Modify: dashboard/e2e/orchestrator.spec.js

**Interfaces:**
- Consumes: dashboard stats, policy status, routing evidence, provider status, and config flag responses
- Produces: a routing control section that clearly matches the backend policy values and preview semantics

- [ ] **Step 1: Add browser coverage for the routing selector and evidence panels**

    test("routing mode selector updates the active mode and exposes policy evidence", async ({ page }) => {
      await page.goto("/orchestrator");
      await page.getByRole("button", { name: "Balanced" }).click();
      await expect(page.getByText("Routing balanced")).toBeVisible();
      await expect(page.getByText("Routing evidence")).toBeVisible();
    });

- [ ] **Step 2: Align the mode labels and preview copy with backend terms**

Keep the existing Off/Balanced/Aggressive choices, but make the surrounding copy explain that the mode controls routing aggressiveness rather than overriding role bindings. Ensure the mode selector and the policy/status cards speak the same language as cutctx/orchestration/models.py and cutctx/orchestration/engine.py.

- [ ] **Step 3: Verify the provider policy and evidence panels still render**

Keep the routing evidence, provider decision cards, fallback posture, and provider health controls visible under both populated and empty data.

- [ ] **Step 4: Run the dashboard browser suite**

Run: cd dashboard && npx playwright test e2e/orchestrator.spec.js

Expected: routing-mode and evidence coverage pass, including the deterministic preview path.

- [ ] **Step 5: Commit the routing-control updates**

    git add dashboard/src/pages/Orchestrator.jsx dashboard/e2e/orchestrator.spec.js
    git commit -m "fix(dashboard): clarify orchestrator routing controls"

### Task 3: Visual and interaction polish pass

**Files:**
- Modify: dashboard/src/index.css
- Modify: any dashboard component that still needs spacing, contrast, or responsive fixes after the functional changes

**Interfaces:**
- Consumes: the refactored dashboard components
- Produces: a coherent operator interface with readable hierarchy, visible focus states, and stable responsive layout

- [ ] **Step 1: Review the dashboard at desktop and compact widths**

Use the browser to inspect the refreshed Orchestrator page at a wide desktop viewport and a smaller laptop width. Confirm the tabs, forms, cards, and tables keep their structure without overflow or clipped content.

- [ ] **Step 2: Adjust spacing, typography, and state affordances**

Keep the current dark-theme visual language, but make active states, disabled states, empty states, and alert states clearer and more readable.

- [ ] **Step 3: Run the dashboard lint/build pass**

Run: cd dashboard && rtk npm run lint && rtk npm run build

Expected: lint passes with zero warnings and the production build completes successfully.

- [ ] **Step 4: Capture the final browser evidence**

Take a final browser pass over the updated routing and roles surface to verify the hierarchy still reads cleanly after the CSS work.

- [ ] **Step 5: Commit the polish updates**

    git add dashboard/src/index.css
    git commit -m "style(dashboard): polish orchestration operator surface"
