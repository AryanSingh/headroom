# Orchestrator Contracts and Routing Mode Reliability Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox syntax for tracking.

**Goal:** Make first-run workload contracts immediately usable and make routing-mode changes responsive, confirmed, recoverable, and fully tested.

**Architecture:** The backend synthesizes a non-persisted starter draft only when no durable or legacy contracts exist. The dashboard separates initial blocking load from background refresh, while Routing Studio owns a cancellable, timed, retryable contracts lifecycle.

**Tech Stack:** Python 3.11+, FastAPI, pytest, React 19, Vite 8, Playwright 1.61.

## Global Constraints

- Preserve unrelated dirty-worktree changes.
- Do not redesign the existing Orchestrator UI.
- Do not change routing preset definitions.
- Do not persist the starter before explicit Save.
- Every production behavior change requires a failing regression test first.
- Browser validation must use the authenticated packaged dashboard on port 8787.

---

## File map

- cutctx/orchestration/contracts.py: contract template schema and canonical starter.
- cutctx/orchestration/service.py: durable, legacy-derived, or starter contract priority.
- tests/test_orchestration_rollouts.py: service-level starter precedence and persistence.
- tests/test_orchestration_api.py: authenticated first-run GET/PUT/GET lifecycle.
- dashboard/src/lib/dashboard-context.jsx: initial-load versus background-refresh state.
- dashboard/src/pages/Orchestrator.jsx: non-blocking refresh and mode reconciliation.
- dashboard/src/components/routing-studio/api.js: timeout and cancellation composition.
- dashboard/src/components/routing-studio/RoutingStudio.jsx: retryable stale-safe loading.
- dashboard/e2e/orchestrator.spec.js: delayed refresh, persistence, timeout, retry, cleanup.
- audit/bug-report.md: final resolution evidence.

---

### Task 1: Synthesized first-run starter contract

**Files:**
- Modify: cutctx/orchestration/contracts.py
- Modify: cutctx/orchestration/service.py
- Test: tests/test_orchestration_rollouts.py
- Test: tests/test_orchestration_api.py

**Interfaces:**
- Produces: starter_implementation_contract() -> WorkloadContract
- Extends: WorkloadContract.template: str
- Preserves: OrchestrationService.list_contracts(contract_id: str | None = None)
- Consumed by: authenticated GET /v1/orchestration/contracts and the existing draft-save endpoint.

- [ ] **Step 1: Add failing service tests**

Add an empty-service helper and require the synthesized draft without disk mutation:

~~~python
def test_empty_store_and_empty_legacy_config_exposes_starter_draft(tmp_path: Path) -> None:
    service = _empty_service(tmp_path)

    contracts = service.list_contracts()

    assert [(item.id, item.version, item.state, item.baseline_model) for item in contracts] == [
        ("implementation", "1", "draft", "openai:gpt-5.4-mini")
    ]
    assert service.contract_store.revision == 0
~~~

Add these separate tests:

~~~python
def test_legacy_contracts_take_precedence_over_starter(tmp_path: Path) -> None:
    service = _service(tmp_path)
    contracts = service.list_contracts()
    assert len(contracts) == 1
    assert contracts[0].id == "implementation"
    assert contracts[0].state == "active"


def test_saved_contracts_replace_starter(tmp_path: Path) -> None:
    service = _empty_service(tmp_path)
    starter = service.list_contracts()[0]
    saved = service.put_contract_draft(starter, expected_revision=0)
    assert service.list_contracts() == [saved.contract]
    assert service.contract_store.revision == 1
~~~

- [ ] **Step 2: Run service tests and verify RED**

Run:

~~~bash
rtk pytest tests/test_orchestration_rollouts.py -q -k "starter or empty_store"
~~~

Expected: the empty-config starter assertion fails because list_contracts() returns an empty list.

- [ ] **Step 3: Add failing API lifecycle test**

Create a project config containing:

~~~json
{"providers":[],"models":[],"roles":[],"bindings":[],"settings":{}}
~~~

Point CUTCTX_ORCHESTRATION_CONFIG and CUTCTX_ORCHESTRATION_DIR at the temporary directory, then assert:

~~~python
first = client.get("/v1/orchestration/contracts", headers=headers)
assert first.status_code == 200
assert first.json()["revision"] == 0
assert first.json()["contracts"][0]["state"] == "draft"
assert first.json()["contracts"][0]["template"] == "implementation"

saved = client.put(
    "/v1/orchestration/contracts/implementation/draft",
    headers=headers,
    json={"contract": first.json()["contracts"][0], "expected_revision": 0},
)
assert saved.status_code == 201
assert saved.json()["revision"] == 1

second = client.get("/v1/orchestration/contracts", headers=headers)
assert second.json()["revision"] == 1
assert second.json()["contracts"] == [saved.json()["contract"]]
~~~

- [ ] **Step 4: Run API test and verify RED**

~~~bash
rtk pytest tests/test_orchestration_api.py -q -k "starter"
~~~

Expected: first GET returns an empty list or saving the returned shape fails because template is rejected.

- [ ] **Step 5: Implement the canonical starter**

First add template: str = "" to WorkloadContract. Add template to the allowed top-level parser keys and pass template=str(payload.get("template", "")).strip() into WorkloadContract. The existing dataclass serializer will include it.

Add starter_implementation_contract() using WorkloadContract, ContractRequirements, ContractObjective, ReliabilityBudget, and ContractEvaluationPolicy. Its exact values are:

- id implementation, name Implementation, version 1, state draft, template implementation;
- role aliases implementation and worker; task type implementation;
- baseline openai:gpt-5.4-mini; no fallback models;
- reasoning and tool_calling capabilities;
- quality floor 0.9, maximum cost 1 USD, maximum latency 120000ms;
- connect 10s, first token 30s, attempt 30s, idle 30s, total 120s;
- two attempts per deployment, two deployments, timeout/provider_outage fallbacks;
- 20 minimum samples, unsafe floor 0.8, maximum unsafe rate 0.01, canary 0.1.

Use sets for task_types, required_capabilities, fallback_triggers, and accepted_outcome_signals. Use tuples for role_aliases and fallback_models.

Update list_contracts():

~~~python
stored = self.contract_store.list_contracts(contract_id)
if stored or self.contract_store.revision:
    return stored
legacy = legacy_contracts_from_config(self.config)
if legacy:
    return [item for item in legacy if contract_id is None or item.id == contract_id]
starter = starter_implementation_contract()
return [starter] if contract_id in {None, starter.id} else []
~~~

- [ ] **Step 6: Run focused backend tests and verify GREEN**

~~~bash
rtk pytest tests/test_orchestration_rollouts.py tests/test_orchestration_api.py -q
~~~

Expected: all focused contract tests pass.

---

### Task 2: Non-blocking refresh and confirmed routing mode

**Files:**
- Modify: dashboard/src/lib/dashboard-context.jsx
- Modify: dashboard/src/pages/Orchestrator.jsx
- Test: dashboard/e2e/orchestrator.spec.js

**Interfaces:**
- Preserves: refresh() -> Promise<void>
- Produces: context field refreshing: boolean
- Preserves: patchDashboardConfig({ orchestrator_mode: mode })

- [ ] **Step 1: Add a failing delayed-refresh mode test**

Let initial stats report Aggressive. After the config POST, delay the next stats and health responses. Immediately assert:

~~~javascript
await page.getByRole("button", { name: "Balanced" }).click();
await expect(page.getByRole("button", { name: "Balanced" }))
  .toHaveAttribute("aria-pressed", "true");
await expect(page.getByRole("heading", {
  name: "Workload contracts, before provider calls",
})).toBeVisible();
await expect(page.getByRole("heading", { name: "Routing mode control" }))
  .toBeVisible();
~~~

Resolve the responses as Balanced and assert the preset becomes codex-gpt54mini-high.

- [ ] **Step 2: Run the test and verify RED**

~~~bash
cd dashboard && rtk test npx playwright test e2e/orchestrator.spec.js -g "keeps orchestrator mounted during mode refresh"
~~~

Expected: the headings disappear because refresh sets global loading true.

- [ ] **Step 3: Implement initial loading versus refreshing**

In dashboard-context.jsx add refreshing. refresh() sets refreshing true, awaits load and loadHistory, and clears refreshing in finally. It must not set loading true. The initial effect remains the only initial blocking load.

In Orchestrator.jsx, block only for loading with no stats and treat errors as fatal only when no stats snapshot exists.

- [ ] **Step 4: Reconcile optimistic mode**

Require the config response to acknowledge the requested mode, await background refresh, then clear optimisticMode:

~~~javascript
const result = await patchDashboardConfig({ orchestrator_mode: mode });
const acknowledged =
  result?.applied_live?.orchestrator_mode?.mode
  || result?.config?.orchestrator_mode;
if (acknowledged && acknowledged !== mode) {
  throw new Error("Backend acknowledged " + acknowledged + " instead of " + mode);
}
await refresh?.();
setOptimisticMode(null);
~~~

On failure, clear optimisticMode and keep the existing alert.

- [ ] **Step 5: Run mode tests and verify GREEN**

~~~bash
cd dashboard && rtk test npx playwright test e2e/orchestrator.spec.js -g "routing mode|mode refresh"
~~~

Expected: POST, mounted UI, delayed confirmation, and final mode assertions pass.

---

### Task 3: Timed, cancellable, retryable contract loading

**Files:**
- Modify: dashboard/src/components/routing-studio/api.js
- Modify: dashboard/src/components/routing-studio/RoutingStudio.jsx
- Test: dashboard/e2e/orchestrator.spec.js

**Interfaces:**
- Extends: routingStudioApi(path, { timeoutMs, signal, ...fetchOptions })
- Extends: listContracts({ signal } = {})
- Produces: Retry loading contracts button.

- [ ] **Step 1: Add a failing timeout-and-retry test**

Leave the first contracts request pending. Expect a timeout and Retry. Fulfill the retry with the starter and assert the editor:

~~~javascript
await expect(page.getByRole("button", { name: "Retry loading contracts" }))
  .toBeVisible({ timeout: 12_000 });
await page.getByRole("button", { name: "Retry loading contracts" }).click();
await expect(page.getByLabel("Contract name")).toHaveValue("Implementation");
~~~

Track request count and assert the first request cannot overwrite the retry result.

- [ ] **Step 2: Run the test and verify RED**

~~~bash
cd dashboard && rtk test npx playwright test e2e/orchestrator.spec.js -g "times out and retries contract loading"
~~~

Expected: Loading contracts remains and no Retry appears.

- [ ] **Step 3: Add timeout and cancellation composition**

routingStudioApi() destructures timeoutMs and caller signal so non-fetch options never reach fetch. It creates an internal AbortController, forwards caller abort once, starts a timer only when timeoutMs is positive, and removes the listener and timer in finally. Internal timeout becomes:

~~~javascript
throw new Error("Contracts request timed out. Check the proxy and try again.");
~~~

listContracts() uses a 10-second timeout and accepts an optional caller signal. Other mutations retain existing time behavior.

- [ ] **Step 4: Implement stale-safe loading and Retry**

RoutingStudio stores the active controller in a ref. loadContracts() aborts the previous controller, sets loading, clears loadError, and updates state only for the current request. Unmount aborts the controller.

Render:

~~~jsx
{loadError ? (
  <div className="routing-empty-state" role="alert">
    <strong>Could not load contracts</strong>
    <span>{loadError}</span>
    <button type="button" className="ghost-button" onClick={loadContracts}>
      Retry loading contracts
    </button>
  </div>
) : loading ? (
  <div className="routing-empty-state">Loading contracts…</div>
)}
~~~

Insert these branches before the current non-loading routing-studio-grid branch. Leave the current grid branch and all ContractList and ContractEditor props unchanged. Keep contract-load errors separate from simulation, save, evidence, and rollout errors.

- [ ] **Step 5: Run loading tests and verify GREEN**

~~~bash
cd dashboard && rtk test npx playwright test e2e/orchestrator.spec.js -g "contract loading|Routing Studio"
~~~

Expected: timeout, retry, stale protection, keyboard, responsive, simulation, and rollout tests pass.

---

### Task 4: Integration, assets, and final audit

**Files:**
- Modify: audit/bug-report.md
- Modify: .slim/deepwork/orchestrator-contracts-routing-mode.md
- Generated: cutctx/dashboard/index.html and cutctx/dashboard/assets/*

- [ ] **Step 1: Run backend orchestration suites**

~~~bash
rtk pytest tests/test_orchestration_contracts.py tests/test_orchestration_contract_store.py tests/test_orchestration_rollouts.py tests/test_orchestration_simulation.py tests/test_orchestration_api.py tests/test_dashboard_orchestrator.py -q
~~~

Expected: zero failures.

- [ ] **Step 2: Run the complete Orchestrator browser suite**

~~~bash
cd dashboard && rtk test npx playwright test e2e/orchestrator.spec.js
~~~

Expected: zero failures across desktop, 390px, keyboard, errors, retry, modes, rollout, evidence, providers, and preview.

- [ ] **Step 3: Lint and build**

~~~bash
cd dashboard && rtk lint npm run lint
cd dashboard && rtk npm run build
~~~

Expected: both exit 0.

- [ ] **Step 4: Sync packaged dashboard assets**

~~~bash
rtk proxy python scripts/sync_dashboard_assets.py
~~~

Verify cutctx/dashboard/index.html references the new JS/CSS names and no stale generated asset remains referenced.

- [ ] **Step 5: Run packaged-dashboard tests**

~~~bash
rtk pytest tests/test_dashboard_orchestrator_policy_e2e.py tests/test_product_operator_contracts.py -q
~~~

Expected: zero failures.

- [ ] **Step 6: Live authenticated Chrome validation**

Against http://127.0.0.1:8787/dashboard/orchestrator:

1. verify the synthesized Implementation starter;
2. save it and verify revision-backed durable state;
3. switch Balanced to Aggressive to Off to Balanced;
4. verify no full-page loading reset;
5. reload and verify backend-reported Balanced;
6. inspect console errors;
7. verify desktop and 390px presentation.

- [ ] **Step 7: Update audit evidence**

For each Orchestrator finding in audit/bug-report.md, add root cause, implemented fix, exact command result, live-browser evidence, and remaining limitations.

- [ ] **Step 8: Completion audit**

~~~bash
rtk git status --short
rtk git diff --check
rtk git diff --stat
~~~

Confirm unrelated user changes remain untouched and every design requirement has direct evidence.
