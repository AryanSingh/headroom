# ChatGPT Emergency Context Budget Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Guarantee that ChatGPT subscription emergency truncation satisfies the Responses model token threshold as well as the serialized byte ceiling.

**Architecture:** Extend the existing request-body truncator with an optional over-budget callback, then reduce large payload components in a deterministic schema-safe order. Keep the final Responses context guard authoritative and preserve byte-only behavior for other callers.

**Tech Stack:** Python 3.11+, FastAPI handler code, pytest.

## Global Constraints

- Preserve all unrelated uncommitted changes in `responses.py` and its tests.
- Do not add dependencies.
- Do not mutate the caller's request body.
- Keep the final fail-closed HTTP 413 behavior for irreducible payloads.

---

### Task 1: Reproduce the token-budget overflow

**Files:**
- Modify: `tests/test_openai_responses_context_compaction.py`

**Interfaces:**
- Consumes: `_truncate_body_for_chatgpt(body, max_bytes, request_id)`.
- Produces: a regression test exercising an optional token-budget predicate.

- [ ] **Step 1: Write the failing test**

Create a payload containing large `tools`, `instructions`, function-call
`arguments`, encrypted content, an old tool result, and a newest user message.
Pass an `over_budget` callback based on serialized character count and assert
the result is under both budgets, starts with a valid non-tool-result item,
preserves the newest user message, and does not mutate the source body.

- [ ] **Step 2: Run the focused test and verify RED**

Run:

```bash
rtk pytest tests/test_openai_responses_context_compaction.py -k emergency_truncation_honors_token_budget -q
```

Expected: FAIL because `_truncate_body_for_chatgpt` does not accept or satisfy a
token-budget predicate.

### Task 2: Implement deterministic budget-driven reduction

**Files:**
- Modify: `cutctx/proxy/handlers/openai/responses.py`
- Test: `tests/test_openai_responses_context_compaction.py`

**Interfaces:**
- Consumes: `over_budget: Callable[[dict[str, Any]], bool] | None`.
- Produces: `_truncate_body_for_chatgpt(..., over_budget=...) -> dict[str, Any]`.

- [ ] **Step 1: Add a unified budget predicate**

Treat a body as oversized when its JSON bytes exceed `max_bytes` or the optional
callback returns true. Catch callback failures conservatively and continue with
the byte check.

- [ ] **Step 2: Expand recursive payload shrinking**

Cap large nested strings in content, output, arguments, encrypted content, and
unknown nested payload containers while preserving routing fields and valid
image placeholders.

- [ ] **Step 3: Add fixed-cost reductions**

When still over budget, remove `tools`, progressively halve instructions, and
apply a final recursive string cap to retained input items.

- [ ] **Step 4: Run the regression test and verify GREEN**

Run the focused command from Task 1. Expected: PASS.

### Task 3: Connect the model context guard and verify compatibility

**Files:**
- Modify: `cutctx/proxy/handlers/openai/responses.py`
- Test: `tests/test_openai_responses_context_compaction.py`

**Interfaces:**
- Consumes: `self._openai_responses_context_guard(payload, model=model)`.
- Produces: ChatGPT HTTP emergency truncation that targets the actual model threshold.

- [ ] **Step 1: Pass the guard-backed predicate**

In the ChatGPT context-guard retry path, pass a closure that returns the refusal
boolean from `_openai_responses_context_guard` for each candidate body.

- [ ] **Step 2: Preserve byte-only callers**

Keep compression-failure and WS-to-HTTP fallback calls compatible by leaving
the new argument optional.

- [ ] **Step 3: Run focused and surrounding tests**

Run:

```bash
rtk pytest tests/test_openai_responses_context_compaction.py -q
rtk pytest tests/test_openai_responses_compression_units.py tests/test_openai_codex_routing.py -q
```

Expected: all tests pass.

- [ ] **Step 4: Review the final diff**

Run:

```bash
rtk git diff -- cutctx/proxy/handlers/openai/responses.py tests/test_openai_responses_context_compaction.py docs/superpowers/specs/2026-07-15-chatgpt-emergency-context-budget-design.md docs/superpowers/plans/2026-07-15-chatgpt-emergency-context-budget.md
```

Confirm the change is limited to the budget reducer, its guard integration,
regression coverage, and these design documents.
