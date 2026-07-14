# Deployment Cooldown and Route Explanations Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Isolate deployments after retry-exhausted provider failures and show route eligibility evidence in the Orchestrator.

**Architecture:** The dynamic model registry stores a deployment-scoped cooldown expiry in existing model metadata. The routing engine queries that overlay before candidate selection and records `cooling_down` in its receipt. The service opens the cooldown after its existing retry budget is exhausted. The React route preview renders existing `selection_evidence` rather than introducing a second decision engine.

**Tech Stack:** Python dataclasses/pytest, FastAPI orchestration API, React, Playwright, Vite.

## Global Constraints

- Keep provider/account/wire-mode/harness checks fail closed.
- A cooldown is scoped to one full deployment key and must not mutate durable model health.
- Strict mode may only select an explicitly configured same-model equivalent.
- Streaming never switches provider after the first emitted byte.
- Use TDD: each production behavior follows an observed failing test.

---

### Task 1: Registry cooldown overlay

**Files:**

- Modify: `cutctx/orchestration/registry.py`
- Test: `tests/test_orchestration_platform.py`

**Interfaces:**

- Produces `DynamicModelRegistry.cool_down(deployment_key: str, duration_seconds: float, *, now: float | None = None) -> ModelRecord`.
- Produces `DynamicModelRegistry.cooldown_remaining_seconds(deployment_key: str, *, now: float | None = None) -> float | None`.

- [ ] **Step 1: Write the failing test**

```python
def test_registry_cooldown_is_deployment_scoped_persisted_and_expires(tmp_path: Path) -> None:
    cache = tmp_path / "models.json"
    registry = DynamicModelRegistry(cache)
    registry.register(_model("openai", "shared", account_id="account-a"))
    registry.register(_model("openai", "shared", account_id="account-b"))

    registry.cool_down("openai:account-a:shared", 30, now=100.0)

    assert registry.cooldown_remaining_seconds("openai:account-a:shared", now=110.0) == 20.0
    assert registry.cooldown_remaining_seconds("openai:account-b:shared", now=110.0) is None
    restored = DynamicModelRegistry(cache)
    assert restored.cooldown_remaining_seconds("openai:account-a:shared", now=110.0) == 20.0
    assert restored.cooldown_remaining_seconds("openai:account-a:shared", now=131.0) is None
```

- [ ] **Step 2: Verify RED**

Run: `rtk pytest tests/test_orchestration_platform.py::test_registry_cooldown_is_deployment_scoped_persisted_and_expires -q`

Expected: FAIL because `cool_down` does not exist.

- [ ] **Step 3: Implement the smallest registry API**

Store `cooldown_until_epoch = float(now or time.time()) + duration_seconds` in only the target record’s `metadata`, call `_save_cache()`, and reject non-positive/non-finite durations. `cooldown_remaining_seconds` returns `None` for no/expired/malformed values; on expiry it removes the field and persists the metadata.

- [ ] **Step 4: Verify GREEN**

Run the Task 1 test. Expected: PASS.

### Task 2: Treat cooldown as an eligibility rejection

**Files:**

- Modify: `cutctx/orchestration/engine.py`
- Test: `tests/test_orchestration_platform.py`

**Interfaces:**

- Consumes `registry.cooldown_remaining_seconds`.
- Produces `selection_evidence.rejected[]` entries with `reason: "cooling_down"`.

- [ ] **Step 1: Write the failing test**

```python
def test_cooling_primary_selects_declared_same_model_equivalent_in_strict_mode() -> None:
    primary = _model("openai", "shared", account_id="account-a")
    equivalent = _model("openai", "shared", account_id="account-b")
    registry = DynamicModelRegistry()
    registry.register(primary)
    registry.register(equivalent)
    registry.cool_down(primary.deployment_key, 30)
    config = OrchestrationConfig(
        roles=[Role(id="worker", name="Worker")],
        bindings=[RouteBinding(id="worker", role="worker", model=primary.deployment_key,
                               equivalent_deployments=[equivalent.deployment_key])],
        settings=RoutingSettings(mode="strict"),
    )

    decision = DeterministicRoutingEngine(config, registry).route(RoutingRequest(role="worker"))

    assert decision.account_id == "account-b"
    assert {"model": primary.deployment_key, "reason": "cooling_down"} in decision.selection_evidence["rejected"]
```

- [ ] **Step 2: Verify RED**

Run: `rtk pytest tests/test_orchestration_platform.py::test_cooling_primary_selects_declared_same_model_equivalent_in_strict_mode -q`

Expected: FAIL because the cooled primary remains eligible.

- [ ] **Step 3: Implement the smallest engine guard**

At the start of `_first_eligible`, after resolving the model and before availability/capability checks, call `registry.cooldown_remaining_seconds(model.deployment_key)`. Return the candidate rejection reason `cooling_down` when it is positive. Do not add policy or transport exceptions.

- [ ] **Step 4: Verify GREEN**

Run the Task 2 test. Expected: PASS.

### Task 3: Open cooldown only after retry exhaustion

**Files:**

- Modify: `cutctx/orchestration/models.py`
- Modify: `cutctx/orchestration/service.py`
- Test: `tests/test_orchestration_platform.py`

**Interfaces:**

- Adds `RoutingSettings.deployment_cooldown_seconds: float = 30.0`.
- `OrchestrationService.execute` and `stream` invoke `registry.cool_down` only after a triggering failure has exhausted retries for the current deployment.

- [ ] **Step 1: Write the failing non-streaming test**

```python
@pytest.mark.asyncio
async def test_retry_exhausted_failure_cools_only_failed_deployment_and_next_route_avoids_it(tmp_path: Path) -> None:
    service = _service(tmp_path, {"openai": httpx.ReadTimeout("timeout"), "anthropic": {"content": []}})
    service.config.settings.retries = 0
    service.config.settings.deployment_cooldown_seconds = 30

    decision, _response = await service.execute(RoutingRequest(role="worker"), messages=[])

    assert decision.provider == "anthropic"
    assert service.model_registry.cooldown_remaining_seconds("openai:openai-main:gpt-5.4-mini") is not None
    assert service.route(RoutingRequest(role="worker")).provider == "anthropic"
```

- [ ] **Step 2: Verify RED**

Run: `rtk pytest tests/test_orchestration_platform.py::test_retry_exhausted_failure_cools_only_failed_deployment_and_next_route_avoids_it -q`

Expected: FAIL because the failed OpenAI deployment has no cooldown.

- [ ] **Step 3: Implement the minimal failure hook**

Add the setting to `RoutingSettings`. Immediately before `engine.fallback` in the retry-exhausted branches of `execute` and the pre-first-byte branch of `stream`, call a small service helper that cools the current `RoutingDecision` deployment only for `timeout`, `rate_limit`, `provider_outage`, `auth_failure`, and `quota_exhausted`. Do not cool `unknown` or post-byte streaming failures until their failure is recorded; post-byte failure still calls the helper before breaking.

- [ ] **Step 4: Verify GREEN**

Run the Task 3 test. Expected: PASS.

### Task 4: Explain the receipt in route preview

**Files:**

- Modify: `dashboard/e2e/orchestrator.spec.js`
- Modify: `dashboard/src/components/OrchestrationStudio.jsx`
- Modify: `dashboard/src/index.css`

**Interfaces:**

- Consumes `/route` response `selection_evidence` with `scores` and `rejected` arrays.
- Produces read-only candidate score and rejection lists in `.route-preview-result`.

- [ ] **Step 1: Write the failing browser test**

Have the mocked `/route` response include:

```json
{
  "provider": "openai",
  "actual_model": "shared",
  "reason": "equivalent_deployment_selected",
  "fallback_used": false,
  "selection_evidence": {
    "scores": [{"deployment": "openai:account-b:shared", "score": 0.94}],
    "rejected": [{"model": "openai:account-a:shared", "reason": "cooling_down"}]
  }
}
```

Assert the Routing preview displays `Candidate scores`, `openai:account-b:shared`, `0.94`, `Rejected candidates`, and `cooling_down`.

- [ ] **Step 2: Verify RED**

Run from `dashboard/`: `rtk test npx playwright test e2e/orchestrator.spec.js --grep "shows route eligibility evidence"`

Expected: FAIL because the preview only shows provider/model/reason.

- [ ] **Step 3: Implement the minimal rendering**

Add small semantic `ul` sections below the existing preview summary. Render only non-empty score/rejection arrays. Give the score an accessible textual label such as `Score 0.94`; keep model/rejection identifiers as text, and use the existing muted/card styles without adding a new data fetch.

- [ ] **Step 4: Verify GREEN**

Run the Task 4 test. Expected: PASS.

### Task 5: Verify and package

**Files:**

- Modify: `docs/content/docs/model-routing-presets.mdx`
- Generated: `cutctx/dashboard/index.html`, `cutctx/dashboard/assets/index-*.js`, `cutctx/dashboard/assets/index-*.css`

- [ ] **Step 1: Document cooldown semantics**

Add a `Deployment cooldowns` section that states the trigger set, retry-exhaustion boundary, deployment scope, automatic expiry, and no mid-stream switch boundary.

- [ ] **Step 2: Build and sync proxy-served assets**

Run:

```bash
cd dashboard && rtk test npm run build
cd .. && rtk proxy python3 scripts/sync_dashboard_assets.py
```

- [ ] **Step 3: Full verification**

Run:

```bash
rtk pytest tests/test_model_router.py tests/test_model_router_presets.py tests/test_orchestration_platform.py tests/test_orchestration_api.py tests/test_dashboard_orchestrator.py tests/test_dashboard_orchestrator_policy_e2e.py tests/test_dashboard_asset_sync.py -q
cd dashboard && rtk lint
cd dashboard && rtk test npx playwright test e2e/orchestrator.spec.js
cd .. && rtk git diff --check
```

Expected: all commands exit 0.
