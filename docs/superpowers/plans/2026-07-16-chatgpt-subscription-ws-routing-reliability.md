# ChatGPT Subscription WebSocket Routing Reliability Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Prevent CutCtx from downgrading ChatGPT-subscription Codex WebSocket turns and make immediate upstream error frames diagnosable.

**Architecture:** Add an explicit routing-policy input that can prohibit even preset allowlisted targets on a transport. Apply it to both initial and subsequent subscription WebSocket frames, while leaving API-key routing unchanged. Log only bounded upstream error metadata.

**Tech Stack:** Python 3.11, pytest, FastAPI/Starlette WebSockets, `websockets`.

## Global Constraints

- Preserve existing API-key/OpenAI model routing.
- Never log request bodies, credentials, or unbounded upstream content.
- Use TDD: observe each regression test fail before production edits.

---

### Task 1: Subscription WebSocket Model Preservation

**Files:**
- Modify: `tests/test_model_router.py`
- Modify: `cutctx/proxy/model_router.py`
- Modify: `cutctx/proxy/handlers/openai/responses.py`

**Interfaces:**
- Consumes: `prepare_model_routing(..., implicit_downgrade_allowed: bool)`
- Produces: `prepare_model_routing(..., allow_transport_safe_targets: bool = True)`

- [ ] **Step 1: Write the failing routing-policy test**

Add a test using `ModelRouterConfig.codex_gpt54mini_high_preset()` that calls
`prepare_model_routing` with `implicit_downgrade_allowed=False` and
`allow_transport_safe_targets=False`, then asserts the requested
`gpt-5.6-sol` model is retained.

- [ ] **Step 2: Run the test and verify RED**

Run: `rtk pytest tests/test_model_router.py -k subscription_websocket_preserves_requested_model`

Expected: FAIL because `allow_transport_safe_targets` is not accepted.

- [ ] **Step 3: Implement the minimal policy input**

Add the keyword argument, require it before consulting
`transport_safe_targets`, and pass `False` from both ChatGPT-subscription
WebSocket routing call sites.

- [ ] **Step 4: Run focused routing tests and verify GREEN**

Run: `rtk pytest tests/test_model_router.py tests/test_openai_codex_routing.py`

Expected: all selected tests pass.

### Task 2: Bounded Upstream Error Diagnostics

**Files:**
- Modify: `tests/test_openai_responses_context_compaction.py`
- Modify: `cutctx/proxy/handlers/openai/responses.py`

**Interfaces:**
- Produces: a helper that extracts bounded `type`, error type, code, and message from an upstream WebSocket error event.

- [ ] **Step 1: Write failing tests for bounded extraction**

Cover nested error objects, structured message objects, and truncation of long
messages without retaining unrelated payload content.

- [ ] **Step 2: Run the tests and verify RED**

Run: `rtk pytest tests/test_openai_responses_context_compaction.py -k upstream_error_summary`

Expected: FAIL because the helper does not exist.

- [ ] **Step 3: Implement and call the helper**

Log one warning when an upstream event has `type == "error"`; include request
ID and bounded summary fields only.

- [ ] **Step 4: Run focused handler tests and verify GREEN**

Run: `rtk pytest tests/test_openai_responses_context_compaction.py tests/test_openai_codex_routing.py`

Expected: all selected tests pass.

### Task 3: Regression and Live Verification

**Files:**
- Verify only; no additional source changes expected.

- [ ] **Step 1: Run lint and focused regression suite**

Run: `rtk ruff check cutctx/proxy/model_router.py cutctx/proxy/handlers/openai/responses.py tests/test_model_router.py tests/test_openai_codex_routing.py tests/test_openai_responses_context_compaction.py`

Run: `rtk pytest tests/test_model_router.py tests/test_openai_codex_routing.py tests/test_openai_responses_context_compaction.py`

- [ ] **Step 2: Restart and inspect the live proxy**

Restart the local port `8787` proxy with the existing
`CUTCTX_MODEL_ROUTING_PRESET=codex-gpt54mini-high` configuration, confirm
`/health` is ready, and inspect the next Codex WebSocket log entry for the
requested model and absence of an immediate upstream error.
