# Current Model Routing Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Route eligible requests for current configured model labels in Aggressive mode and make every routing result visible in recent-request activity.

**Architecture:** Extend the existing exact-match `ModelRouterConfig` preset data; keep `ModelRouter.maybe_route` safety gates unchanged. Carry its existing routing trace into `RequestLog`, then render a compact summary in the React Overview table.

**Tech Stack:** Python 3.14, pytest, React/Vite dashboard, Playwright.

## Global Constraints

- Use exact model identifiers only; no wildcard or prefix model matching.
- Never allow the learned scorer to bypass deterministic high-risk/tool-context retention.
- Only route to targets already marked transport-safe for the applicable transport.
- Preserve compatibility with historical `RequestLog` JSONL records that lack routing fields.

---

### Task 1: Current-model route coverage

**Files:**
- Modify: `tests/test_model_router_presets.py`
- Modify: `tests/test_model_router.py`
- Modify: `cutctx/proxy/model_router.py`

**Interfaces:**
- Consumes: `ModelRouterConfig.economy_preset()` and `ModelRouter.maybe_route()`.
- Produces: Exact Aggressive routes for supported GPT-5 and Claude 5 labels.

- [ ] Write failing tests asserting Aggressive maps `gpt-5.6-terra` to `gpt-5.4-mini` and retains a tool-context request.
- [ ] Run `pytest -q tests/test_model_router_presets.py tests/test_model_router.py` and confirm the missing route assertion fails.
- [ ] Add only the exact preset entries and safe-target configuration needed for those tests.
- [ ] Re-run the focused router tests and confirm they pass.

### Task 2: Persist routing explanations

**Files:**
- Modify: `tests/test_model_routing_trace.py`
- Modify: `cutctx/proxy/models.py`
- Modify: `cutctx/proxy/outcome.py`

**Interfaces:**
- Consumes: `request_savings_metadata["model_routing_trace"]`.
- Produces: `RequestLog.model_routing` JSON-safe summary.

- [ ] Write a failing request-outcome test asserting an abstained trace is emitted in the request log.
- [ ] Run the test and confirm the summary field is absent.
- [ ] Copy the versioned trace's five public decision fields into `RequestLog` at outcome emission.
- [ ] Re-run the request-outcome and trace tests.

### Task 3: Activity-table explanation

**Files:**
- Modify: `dashboard/src/pages/Overview.jsx`
- Modify: `tests/test_dashboard_overview_request_trace_inspector.py`

**Interfaces:**
- Consumes: `recent_requests[].model_routing`.
- Produces: A Routing column with `Routed to <target>` or the named abstention reason.

- [ ] Write a failing Playwright test for a retained Terra row showing `workload_not_downgradeable`.
- [ ] Run the focused dashboard test and confirm it fails because the column is absent.
- [ ] Implement the minimal Routing column and explanatory table note.
- [ ] Re-run the dashboard test.

### Task 4: Integration verification and docs

**Files:**
- Modify: `docs/content/docs/model-routing-presets.mdx`

**Interfaces:**
- Consumes: route table and dashboard contract from Tasks 1–3.
- Produces: operator documentation that describes explicit routes and abstention visibility.

- [ ] Document current-model coverage, deterministic retention, and the learned scorer's abstention-only role.
- [ ] Run `pytest -q tests/test_model_router.py tests/test_model_router_presets.py tests/test_model_routing_trace.py tests/test_dashboard_overview_request_trace_inspector.py`.
- [ ] Run the relevant dashboard build/lint command and a targeted Playwright test when dependencies are available.
- [ ] Inspect the diff for unintended preset, telemetry, or generated-asset changes.
