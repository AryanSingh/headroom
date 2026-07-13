# Model Routing Evidence Loop Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Remove shadow-evaluation latency from primary responses and expose privacy-safe routing quality/cost evidence in the authenticated Orchestrator UI.

**Architecture:** Preserve the deterministic router and existing evidence store. Schedule transport-specific shadow helpers as retained background tasks, build a read-only evidence report from sanitized records, expose it through the orchestration API, and render its readiness and recommended frontier point in the dashboard.

**Tech Stack:** Python 3.11+, asyncio, FastAPI/Pydantic, pytest/anyio, React 19, Playwright, Vite/ESLint.

## Global Constraints

- Prefix every shell command with `rtk`; use `rtk proxy` when raw output is required.
- No production behavior without a failing test observed first.
- Deterministic safety gates remain authoritative and unchanged.
- Evidence must never expose prompt text, response text, raw workspace/repository identity, credentials, or local evidence paths.
- Shadow evaluation failure must never alter or delay the primary response.
- Preserve all pre-existing working-tree changes, especially `dashboard/src/components/OrchestrationStudio.jsx`, `dashboard/src/index.css`, `restart-proxy.sh`, and `tests/test_orchestration_api.py`.
- No new runtime dependencies.

---

### Task 1: Retained non-blocking shadow tasks

**Files:**
- Modify: `cutctx/proxy/model_routing_evals.py`
- Modify: `cutctx/proxy/handlers/openai/chat.py`
- Modify: `cutctx/proxy/handlers/openai/responses.py`
- Modify: `cutctx/proxy/handlers/anthropic.py`
- Test: `tests/test_model_routing_evals.py`

**Interfaces:**
- Produces: `schedule_model_routing_shadow(coroutine: Coroutine[Any, Any, Any]) -> asyncio.Task[Any]`, which schedules immediately, retains the task until completion, consumes exceptions, and does not await the coroutine.
- Consumes: existing awaitable transport helpers `_maybe_model_routing_chat_shadow`, `_maybe_model_routing_responses_shadow`, and `_maybe_model_routing_shadow`.

- [ ] **Step 1: Write failing scheduler tests**

Add tests that create a coroutine blocked on an `anyio.Event`, call `schedule_model_routing_shadow`, assert the call returns with an unfinished task, release the event, await the task, and assert completion. Add a second test whose coroutine raises and assert the task completes without propagating through the scheduler or leaving an unconsumed exception.

- [ ] **Step 2: Verify RED**

Run: `rtk pytest tests/test_model_routing_evals.py -q`

Expected: collection or assertion failure because `schedule_model_routing_shadow` does not exist.

- [ ] **Step 3: Implement the minimal scheduler**

Use `asyncio.get_running_loop().create_task(coroutine)`, retain tasks in a module-level set, and attach a done callback that discards the task and calls `task.exception()` unless cancelled. Export the function through `__all__`.

- [ ] **Step 4: Verify GREEN**

Run: `rtk pytest tests/test_model_routing_evals.py -q`

Expected: all tests pass.

- [ ] **Step 5: Route primary handlers through the scheduler**

At the three non-streaming response-path call sites, replace `await self._maybe_model_routing_*_shadow(...)` with `schedule_model_routing_shadow(self._maybe_model_routing_*_shadow(...))`. Keep the helper methods themselves awaitable so their focused transport tests remain deterministic.

- [ ] **Step 6: Verify transport regressions**

Run: `rtk pytest tests/test_openai_chat_model_routing_shadow.py tests/test_openai_responses_model_routing_shadow.py tests/test_anthropic_model_routing.py -q`

Expected: all tests pass.

### Task 2: Versioned evidence readiness report and API

**Files:**
- Modify: `cutctx/proxy/model_routing_evals.py`
- Modify: `cutctx/proxy/routes/orchestration.py`
- Test: `tests/test_model_routing_evals.py`
- Test: `tests/test_orchestration_api.py`

**Interfaces:**
- Produces: `build_model_routing_evidence_report(records, *, minimum_samples=20, minimum_mean_quality=0.90, maximum_unsafe_rate=0.01, quality_floor=0.80) -> dict[str, Any]`.
- Produces: authenticated `GET /v1/orchestration/routing/evidence`.

- [ ] **Step 1: Write failing report tests**

Add one test per readiness state:

- empty records returns `no_evidence` and no recommendation;
- fewer than `minimum_samples` returns `collecting` and sample progress;
- sufficient unsafe records returns `quality_blocked`;
- sufficient safe records returns `ready` with the recommended confidence, mean quality, unsafe rate, routing rate, and verified total savings.

Assert the serialized report contains none of the test prompt text, response text, workspace path, repository name, or evidence path.

- [ ] **Step 2: Verify report RED**

Run: `rtk pytest tests/test_model_routing_evals.py -q`

Expected: failure because `build_model_routing_evidence_report` does not exist.

- [ ] **Step 3: Implement the report builder**

Reuse `build_quality_cost_frontier`, `recommend_confidence_threshold`, and `build_segmented_recommendations`. Do not change their existing semantics. Gate the report-level recommendation on `minimum_samples` and derive the four explicit statuses.

- [ ] **Step 4: Verify report GREEN**

Run: `rtk pytest tests/test_model_routing_evals.py -q`

Expected: all tests pass.

- [ ] **Step 5: Write failing authenticated API tests**

In `tests/test_orchestration_api.py`, configure `CUTCTX_MODEL_ROUTING_EVAL_PATH` to a temporary JSONL file. Assert unauthenticated access is rejected, an empty file returns `no_evidence`, and seeded safe records return `ready`. Assert the response does not contain the temporary path or any raw identity values.

- [ ] **Step 6: Verify API RED**

Run: `rtk pytest tests/test_orchestration_api.py -q`

Expected: 404 for `/v1/orchestration/routing/evidence`.

- [ ] **Step 7: Implement the API endpoint**

Add validated query parameters for `minimum_samples`, `minimum_mean_quality`, `maximum_unsafe_rate`, and `quality_floor`. Load `ModelRoutingEvalStore`, build the report, and add `shadow_enabled` and `shadow_sample_rate` without returning the configured path.

- [ ] **Step 8: Verify API GREEN**

Run: `rtk pytest tests/test_orchestration_api.py -q`

Expected: all tests pass.

### Task 3: Evidence-first Orchestrator card

**Files:**
- Modify: `dashboard/src/pages/Orchestrator.jsx`
- Modify: `dashboard/src/index.css`
- Modify: `tests/test_dashboard_orchestrator_policy_e2e.py`
- Modify: `dashboard/e2e/orchestrator.spec.js`

**Interfaces:**
- Consumes: `GET /v1/orchestration/routing/evidence` schema version 1.
- Produces: operator-visible states `No evidence`, `Collecting evidence`, `Quality blocked`, and `Ready to promote`.

- [ ] **Step 1: Write failing browser assertions**

Extend the Python Playwright fixture with a complete `routing/evidence` response and assert the page renders `Routing evidence`, the readiness label, sample progress, measured mean quality, unsafe rate, verified savings, and recommended confidence. Extend the JS Playwright fixture with a collecting response and assert `Collecting evidence` appears without hiding routing mode controls.

- [ ] **Step 2: Verify browser RED**

Run: `rtk pytest tests/test_dashboard_orchestrator_policy_e2e.py -q`

Expected: failure because the evidence card is absent.

- [ ] **Step 3: Implement data loading and card states**

Fetch `/v1/orchestration/routing/evidence` alongside existing policy/provider data. Add isolated loading and error state. Render a compact panel directly after the routing savings metrics, with measured values from `recommendation` only when ready and explicit copy for empty, collecting, and blocked states.

- [ ] **Step 4: Add focused responsive styles**

Reuse existing panel, metric, graph key/value, and status classes where possible. Add only evidence-status modifiers needed to distinguish ready, collecting, blocked, and empty states. Preserve the existing user changes in `dashboard/src/index.css`.

- [ ] **Step 5: Verify browser GREEN**

Run: `rtk pytest tests/test_dashboard_orchestrator_policy_e2e.py -q`

Run: `rtk npm run lint --prefix dashboard`

Run: `rtk npm run build --prefix dashboard`

Expected: all commands pass with no warnings or errors.

### Task 4: Documentation and full verification

**Files:**
- Modify: `docs/content/docs/model-routing-presets.mdx`

- [ ] **Step 1: Update operator documentation**

Document that sampled non-streaming baseline evaluation is scheduled after the candidate response and does not delay it. Document the evidence endpoint, four readiness states, default constraints, privacy guarantees, and the fact that recommendations are read-only until explicitly promoted in a future staged-rollout feature.

- [ ] **Step 2: Run focused Python verification**

Run: `rtk pytest tests/test_model_router.py tests/test_model_routing_evals.py tests/test_orchestration_api.py tests/test_openai_chat_model_routing_shadow.py tests/test_openai_responses_model_routing_shadow.py tests/test_anthropic_model_routing.py tests/test_dashboard_orchestrator.py tests/test_dashboard_orchestrator_policy_e2e.py -q`

Expected: all tests pass.

- [ ] **Step 3: Run repository regression tests appropriate to the changed surfaces**

Run: `rtk ruff check cutctx/proxy/model_routing_evals.py cutctx/proxy/routes/orchestration.py cutctx/proxy/handlers/openai/chat.py cutctx/proxy/handlers/openai/responses.py cutctx/proxy/handlers/anthropic.py tests/test_model_routing_evals.py tests/test_orchestration_api.py`

Run: `rtk npm run lint --prefix dashboard`

Run: `rtk npm run build --prefix dashboard`

Expected: all commands pass.

- [ ] **Step 4: Inspect the final diff for unrelated changes**

Run: `rtk git diff --check`

Run: `rtk git status --short`

Expected: no whitespace errors; only planned files plus the user’s pre-existing files are modified.
