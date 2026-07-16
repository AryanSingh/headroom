# Routing Safeguards Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Make automatic model downgrades capability-safe, terminally reject invalid provider requests, and accurately account for input and output savings.

**Architecture:** Request adapters derive a provider-neutral capability set and hand it to `prepare_model_routing`; the router compares it against declarative target capabilities before applying a downgrade. Orchestration adds a terminal invalid-request trigger, while route pricing and outcome finalization use both token dimensions.

**Tech Stack:** Python 3.11, pytest, dataclasses, LiteLLM optional price metadata.

## Global Constraints

- Preserve existing text-only preset routing behavior.
- Treat missing target capability declarations as insufficient proof for feature-bearing requests.
- Never mutate request payloads while inferring capabilities.
- Invalid request errors must not retry, fallback, or cool down a deployment.
- Keep trace additions backward-compatible and free of prompt/response content.

---

### Task 1: Capability-safe model routing

**Files:**
- Modify: `cutctx/proxy/model_router.py`
- Modify: `tests/test_model_router.py`

- [ ] Write failing tests for a low-complexity tool/JSON request retained with `target_missing_capabilities`, and for a target explicitly declaring parity that routes.
- [ ] Run `pytest -q tests/test_model_router.py -k capability` and confirm failure.
- [ ] Add route target/medium-target capability declarations, parse them from JSON, pass `required_capabilities` into `maybe_route`, and emit sorted missing requirements in metadata and trace.
- [ ] Re-run the focused test and the complete `tests/test_model_router.py` file.

### Task 2: Provider-neutral ingress capability extraction

**Files:**
- Modify: `cutctx/proxy/model_router.py`
- Modify: `cutctx/proxy/handlers/openai/chat.py`
- Modify: `cutctx/proxy/handlers/openai/responses.py`
- Modify: `cutctx/proxy/handlers/anthropic.py`
- Modify: `cutctx/proxy/handlers/gemini.py`
- Test: relevant existing handler routing tests

- [ ] Write failing helper-level tests covering tool calling, JSON/schema, vision/audio, and streaming inputs without body mutation.
- [ ] Run the focused tests and confirm failure.
- [ ] Add small shared extraction helpers for each wire shape and pass their result to `prepare_model_routing` in every ingress callsite.
- [ ] Verify text-only routing tests still route and capability-bearing requests abstain unless declared safe.

### Task 3: Terminal invalid-request failures

**Files:**
- Modify: `cutctx/orchestration/models.py`
- Modify: `cutctx/orchestration/service.py`
- Modify: `tests/test_orchestration_platform.py`

- [ ] Write failing tests that classify 400/422 as `invalid_request`, make one invocation only, and preserve 429/5xx fallback.
- [ ] Run the focused tests and confirm failure.
- [ ] Add `INVALID_REQUEST`, exclude it from defaults/cooldowns, and stop retry/fallback immediately in `execute` and `stream`.
- [ ] Re-run orchestration platform tests.

### Task 4: Output-aware savings

**Files:**
- Modify: `cutctx/proxy/model_router.py`
- Modify: `cutctx/proxy/outcome.py`
- Modify: `tests/test_model_router.py`
- Modify: `tests/test_request_outcome.py`

- [ ] Write failing tests for mixed input/output price deltas and an explicitly marked input-only estimate.
- [ ] Run focused tests and confirm failure.
- [ ] Add output price fields/cost lookup, extend `finalize_savings`, and thread output usage through outcome finalization while preserving input-token metric semantics.
- [ ] Re-run focused router and outcome tests.

### Task 5: Verification and documentation

**Files:**
- Modify: `docs/content/docs/model-routing-presets.mdx`
- Test: routing and orchestration suites; `benchmarks/model_routing_quality.py`

- [ ] Document capability abstention, terminal invalid requests, and partial-estimate savings.
- [ ] Run focused suites, the deterministic routing benchmark, format/lint checks, and inspect the final diff for trace/privacy compatibility.
