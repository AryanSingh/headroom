# Provider-Complete Tool Context Routing Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Ensure every supported recent tool-call or tool-result representation keeps model routing on the requested strong model.

**Architecture:** Add one recursive private predicate in `cutctx/proxy/model_router.py` and use it inside the existing bounded recent-context gate. Extend focused unit tests and the versioned routing-quality corpus without changing preset targets, scoring thresholds, or cost accounting.

**Tech Stack:** Python 3.10+, pytest, JSON benchmark fixtures.

## Global Constraints

- Every production change must be preceded by a failing test.
- Recent tool context must classify as `TaskComplexity.HIGH`.
- Tool context outside the existing eight-message recent window must not permanently pin a conversation to the strong model.
- Preserve the existing `recent_tool_context` routing signal and public trace schema.
- Do not modify the user's current OpenAI schema-compaction changes.

---

### Task 1: Provider-neutral recent tool-context detection

**Files:**
- Modify: `tests/test_model_router.py`
- Modify: `cutctx/proxy/model_router.py:153-182`

**Interfaces:**
- Consumes: `messages: list[dict[str, Any]]` and `_recent_context_window(messages)`.
- Produces: `_contains_tool_context(value: Any) -> bool`, used only by `classify_task_complexity` and `assess_task_complexity`.

- [ ] **Step 1: Write failing tests for provider-native call shapes**

Add parametrized cases covering a top-level Responses `function_call`, Chat Completions `tool_calls`, a nested `function_call` content block, and top-level `local_shell_call_output`. Each history ends with `{"role": "user", "content": "Show status."}` and asserts `classify_task_complexity(messages) is TaskComplexity.HIGH`.

- [ ] **Step 2: Run the focused tests and verify RED**

Run: `CI=true rtk pytest -q tests/test_model_router.py -k 'provider_native_tool_context'`

Expected: all new cases fail with `TaskComplexity.LOW` instead of `TaskComplexity.HIGH`.

- [ ] **Step 3: Implement the minimal recursive predicate**

Add `_contains_tool_context(value: Any) -> bool` that returns true for `role == "tool"`, non-empty `tool_calls`, non-empty legacy `function_call`, known call/result types, any string type ending in `_call` or `_call_output`, and recursively nested dictionaries/lists. Replace the narrow comprehension in `classify_task_complexity` with `any(_contains_tool_context(message) for message in recent_messages)`. Use the same predicate in `assess_task_complexity` so the existing `recent_tool_context` signal covers every recognized shape.

- [ ] **Step 4: Run the focused tests and verify GREEN**

Run: `CI=true rtk pytest -q tests/test_model_router.py -k 'provider_native_tool_context or stale_tool_context or recent_tool'`

Expected: all selected tests pass.

- [ ] **Step 5: Run the complete model-router unit file**

Run: `CI=true rtk pytest -q tests/test_model_router.py`

Expected: all tests pass.

### Task 2: Versioned routing-quality evidence

**Files:**
- Modify: `benchmarks/fixtures/model_routing_quality_v2.json`
- Modify: `docs/content/docs/model-routing-presets.mdx`

**Interfaces:**
- Consumes: versioned schema-2 routing cases.
- Produces: provider-shape cases with `expected_tier: "strong"` and documentation of provider-complete recent tool-context gating.

- [ ] **Step 1: Add versioned provider-shape cases**

Add separate Codex/OpenAI cases for Responses `function_call`, Chat `tool_calls`, and a `local_shell_call_output`, each ending in a short otherwise-Mini-eligible user request and labeled `strong` in category `tool_use`.

- [ ] **Step 2: Verify the benchmark evidence**

Run: `CI=true rtk proxy .venv/bin/python benchmarks/model_routing_quality.py --ci --output /tmp/model-routing-quality-provider-shapes.json`

Expected: exit 0, zero unsafe Mini downgrades, and the new cases predicted `strong`.

- [ ] **Step 3: Document the expanded gate**

Update the complexity-heuristic section to state that the recent-context gate recognizes Anthropic tool blocks, OpenAI Chat `tool_calls`, and OpenAI Responses call/output items.

- [ ] **Step 4: Run integration-focused routing tests**

Run: `CI=true rtk pytest -q tests/test_model_router.py tests/test_openai_codex_routing.py tests/test_anthropic_model_routing.py`

Expected: all tests pass.

### Task 3: Final verification and audit reconciliation

**Files:**
- Update: `.slim/deepwork/core-product-audit.md`
- Update: `audit/core-token-compression-routing-audit-2026-07-15.md`

**Interfaces:**
- Consumes: final test and benchmark evidence.
- Produces: an evidence-backed closure note for the verified routing defect.

- [ ] **Step 1: Run lint on changed Python files**

Run: `CI=true rtk ruff check cutctx/proxy/model_router.py tests/test_model_router.py benchmarks/model_routing_quality.py`

Expected: no errors.

- [ ] **Step 2: Run the focused full verification set**

Run: `CI=true rtk pytest -q tests/test_model_router.py tests/test_openai_codex_routing.py tests/test_anthropic_model_routing.py tests/test_request_outcome.py tests/test_savings_orchestration.py`

Expected: all tests pass.

- [ ] **Step 3: Reconcile audit state**

Mark the tool-context finding fixed only after the commands above pass. Record exact test counts and benchmark case count; leave downstream-task evidence as an open follow-up.
