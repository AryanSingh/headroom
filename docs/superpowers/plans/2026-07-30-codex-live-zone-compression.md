# Codex Live-Zone Compression Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Deliver measurable, cache-stable compression for fresh Codex tool outputs without breaking subscription continuations, session resume, or tool calls.

**Architecture:** Preserve the existing `mutable_tail_only` subscription policy. Strengthen its extraction and router contracts so a fresh tool-result tail can be reversibly compacted before the provider sees it; every opaque continuation or failure must pass through byte-for-byte unchanged.

**Tech Stack:** Python 3.11, FastAPI proxy, OpenAI Responses handler, ContentRouter, CCR, pytest.

## Global Constraints

- Never mutate user/assistant/reasoning/tool-call input or a frozen/opaque continuation.
- A compressor failure must fail open to the original request; it must not interrupt a Codex session.
- The compact payload must be strictly smaller on the provider tokenizer and wire bytes.
- Direct-compression savings and provider-cache savings remain distinct telemetry.

---

### Task 1: Pin the live-zone and continuation compatibility contract

**Files:**
- Modify: `tests/test_openai_responses_compression_units.py`
- Modify: `tests/test_openai_responses_subscription_compat.py`

- [ ] Write failing tests that submit a source-code `function_call_output` as the final mutable input and assert a nonzero direct saving plus an unchanged envelope.
- [ ] Run each new test with `.venv/bin/python -m pytest <nodeid> -q` and confirm it fails because the current router returns `router_no_change`.
- [ ] Add cases proving `previous_response_id`, remote compaction, opaque response state, tool arguments, and tool declarations remain byte-identical.
- [ ] Add a compressor-exception case proving the original request is forwarded and the failure reason is `subscription_compression_failed`.

### Task 2: Make reversible live-tail code routing reachable

**Files:**
- Modify: `cutctx/proxy/handlers/openai/responses.py`
- Modify: `cutctx/transforms/compression_units.py` only if a provider-owned live-tail hint is required
- Test: `tests/test_openai_responses_compression_units.py`

- [ ] After the Task 1 red test, trace the unit's `ContentRouter` strategy and pass only the minimal provider metadata needed for reversible code compression of an eligible mutable tail.
- [ ] Keep candidate construction restricted to `payload["input"][-1]["output"]`; retain `_validate_chatgpt_subscription_tool_output_candidate` as the final allowlist/wire-size gate.
- [ ] Run the focused tests until green, then run the complete compression-unit test module.

### Task 3: Prove session continuity and upstream-safe fallback

**Files:**
- Modify: `tests/test_openai_responses_subscription_compat.py`
- Modify: `tests/test_openai_responses_context_compaction.py`

- [ ] Add a two-turn fixture: first turn sends a fresh output tail and receives its compact stable form; second turn is an opaque resume and is forwarded unchanged.
- [ ] Assert the code never injects or removes tools, changes `call_id`, alters `previous_response_id`, or raises a client-visible exception when compression or retrieval backing fails.
- [ ] Run the subscription compatibility and context compaction modules until green.

### Task 4: Verification and reporting

**Files:**
- Verify: `tests/test_openai_responses_compression_units.py`
- Verify: `tests/test_openai_responses_context_compaction.py`
- Verify: `tests/test_openai_responses_subscription_compat.py`
- Verify: `tests/test_proxy_openai_responses_integration.py`

- [ ] Run formatter/linter checks with `uvx ruff@0.9.4 check` and `uvx ruff@0.9.4 format --check` for changed Python files.
- [ ] Run all four Responses suites using the isolated Python 3.11 runtime.
- [ ] Run the full `tests/` suite if the local native build completes; otherwise report the exact build blocker and preserve targeted evidence.
- [ ] Record the before/after direct-compression result and each no-regression invariant in the final handoff.
