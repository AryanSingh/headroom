# Codex Subscription Safe Mutable-Tail Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use `test-driven-development` task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Compress only the newest verified tool-output tail in a ChatGPT/Codex subscription Responses payload while preserving opaque continuations and every historical prefix item unchanged.

**Architecture:** Extend the existing subscription classifier with `mutable_tail_only`. The subscription helper will compress an isolated copy of the final output item and splice back only its `output` field after structural, token, and serialized-byte validation. Opaque continuations continue to take the byte-faithful passthrough path.

**Tech Stack:** Python 3.12, pytest, existing OpenAI Responses handler and `ContentRouter` fixtures.

## Global Constraints

- Preserve remote compaction, `previous_response_id`, encrypted/opaque continuation data, malformed input, and all history.
- Do not run schema compaction, routing overrides, memory, or deduplication on this subscription path.
- A candidate must reduce both provider tokens and serialized JSON bytes.
- Every failure forwards the original payload; no new WebSocket refusal behavior.

---

### Task 1: Add a test-first mutable-tail classifier

**Files:**

- Modify: `tests/test_openai_responses_compression_units.py`
- Modify: `cutctx/proxy/handlers/openai/responses.py`

**Interface:** `_classify_chatgpt_subscription_compression(payload) -> tuple[str, str | None]` returns `("mutable_tail_only", None)` only when the final `input` item has an allowlisted output type, non-empty `call_id`, and string `output`, after opaque-state checks pass.

- [ ] Write the failing test:

```python
def test_chatgpt_subscription_classifier_marks_final_output_as_mutable_tail():
    handler = _handler_with_router(ContentRouter())
    payload = {
        "input": [
            {"type": "function_call_output", "call_id": "historic", "output": "old"},
            {"type": "message", "role": "user", "content": "continue"},
            {"type": "local_shell_call_output", "call_id": "current", "output": "new"},
        ]
    }
    assert handler._classify_chatgpt_subscription_compression(payload) == (
        "mutable_tail_only", None
    )
```

- [ ] Run it and observe RED:

```bash
uv run --extra dev pytest tests/test_openai_responses_compression_units.py::test_chatgpt_subscription_classifier_marks_final_output_as_mutable_tail -q
```

Expected: FAIL because the current classifier returns `tool_outputs_only`.

- [ ] Implement the smallest branch after malformed/opaque checks:

```python
tail = items[-1]
if (
    tail.get("type") in self.OPENAI_RESPONSES_OUTPUT_TYPES
    and isinstance(tail.get("output"), str)
    and isinstance(tail.get("call_id"), str)
    and tail["call_id"]
):
    return "mutable_tail_only", None
```

- [ ] Rerun the same test and observe GREEN.

### Task 2: Isolate the final output before compression

**Files:**

- Modify: `tests/test_openai_responses_compression_units.py`
- Modify: `cutctx/proxy/handlers/openai/responses.py`

**Interface:** `_compress_chatgpt_subscription_tool_outputs` mutates only `payload["input"][-1]["output"]` for `mutable_tail_only`; every preceding input item compares equal to its original.

- [ ] Write the failing test:

```python
def test_chatgpt_subscription_compresses_only_current_output_tail():
    router = ContentRouter()
    router.compress = MethodType(_compress_to_kept_words, router)
    handler = _handler_with_router(router)
    long_text = " ".join(f"word{i}" for i in range(180))
    payload = {
        "model": "gpt-5.4",
        "input": [
            {"type": "function_call_output", "call_id": "historic", "output": long_text},
            {"type": "message", "role": "user", "content": "continue"},
            {"type": "local_shell_call_output", "call_id": "current", "output": long_text},
        ],
    }
    updated, modified, *_ = handler._compress_chatgpt_subscription_tool_outputs(
        payload, model="gpt-5.4", request_id="req_mutable_tail"
    )
    assert modified is True
    assert updated["input"][:-1] == payload["input"][:-1]
    assert updated["input"][-1]["output"] == "kept words"
```

- [ ] Run it and observe RED:

```bash
uv run --extra dev pytest tests/test_openai_responses_compression_units.py::test_chatgpt_subscription_compresses_only_current_output_tail -q
```

Expected: FAIL because the generic router currently rewrites all eligible output entries.

- [ ] Implement only an isolated one-item candidate:

```python
tail_candidate = {"input": [copy.deepcopy(payload["input"][-1])]}
compressed_tail, modified, *_ = self._compress_openai_responses_live_text_units_with_router(
    tail_candidate, model=model, request_id=request_id, timing=timing
)
candidate = copy.deepcopy(payload)
candidate["input"][-1]["output"] = compressed_tail["input"][0]["output"]
```

Do not pass tools, instructions, or historical input through the generic payload compressor.

- [ ] Rerun the test and observe GREEN.

### Task 3: Require token and wire-byte savings

**Files:**

- Modify: `tests/test_openai_responses_compression_units.py`
- Modify: `cutctx/proxy/handlers/openai/responses.py`

**Interface:** `_validate_chatgpt_subscription_tool_output_candidate` returns `(False, 0)` if a structurally valid candidate fails provider-token or serialized-byte reduction.

- [ ] Write the failing test:

```python
def test_subscription_tail_validator_rejects_token_saving_wire_inflation():
    handler = _handler_with_router(ContentRouter())
    original = {"input": [{"type": "function_call_output", "call_id": "c1", "output": "one two"}]}
    candidate = {"input": [{"type": "function_call_output", "call_id": "c1", "output": "one" + "x" * 100}]}
    assert handler._validate_chatgpt_subscription_tool_output_candidate(
        original, candidate, tokenizer=TokenCounter()
    ) == (False, 0)
```

- [ ] Run it and observe RED:

```bash
uv run --extra dev pytest tests/test_openai_responses_compression_units.py::test_subscription_tail_validator_rejects_token_saving_wire_inflation -q
```

Expected: FAIL because the current validator only compares token count.

- [ ] Add the minimal validation after structural checks:

```python
if len(json.dumps(candidate, separators=(",", ":")).encode()) >= len(
    json.dumps(original, separators=(",", ":")).encode()
):
    return False, 0
```

- [ ] Run the new regression plus `tests/test_openai_responses_compression_units.py` and observe GREEN.

### Task 4: Preserve WebSocket dispatch behavior

**Files:**

- Modify: `tests/test_openai_codex_ws_lifecycle.py`
- Modify: `tests/test_openai_responses_context_compaction.py`
- Modify: `cutctx/proxy/handlers/openai/responses.py` only if a focused test exposes a dispatch gap.

**Interface:** both first and later subscription `response.create` frames call the existing async subscription helper; opaque frames return unchanged and mutable-tail frames preserve every earlier item.

- [ ] Write focused lifecycle regressions using the existing fake WebSocket fixture.
- [ ] Run them first:

```bash
uv run --extra dev pytest tests/test_openai_codex_ws_lifecycle.py -k 'subscription and compression' -q
```

- [ ] Make the smallest dispatch repair only if the test shows a bypass or incorrect reserialization.
- [ ] Verify focused suites:

```bash
uv run --extra dev pytest \
  tests/test_openai_responses_compression_units.py \
  tests/test_openai_responses_context_compaction.py \
  tests/test_openai_codex_ws_lifecycle.py \
  tests/test_openai_codex_ws_timings.py -q
```

### Task 5: Verify release readiness

- [ ] Run lint and formatting:

```bash
uvx ruff@0.9.4 check cutctx/proxy/handlers/openai/responses.py tests/test_openai_responses_compression_units.py tests/test_openai_codex_ws_lifecycle.py
uvx ruff@0.9.4 format --check cutctx/proxy/handlers/openai/responses.py tests/test_openai_responses_compression_units.py tests/test_openai_codex_ws_lifecycle.py
```

- [ ] Run the release-equivalent suite:

```bash
uv run --extra ee --extra dev pytest tests -k 'not slow and not real_llm and not live and not e2e' -q
```

- [ ] Record commands, results, and the remaining limitation—no real subscription pilot—inside `.slim/deepwork/codex-subscription-compression.md`.

## Execution evidence

- `tests/test_openai_responses_compression_units.py`,
  `tests/test_openai_responses_context_compaction.py`,
  `tests/test_openai_codex_ws_lifecycle.py`, and
  `tests/test_openai_codex_ws_timings.py`: **92 passed** (2026-07-29).
- `uvx ruff@0.9.4 check` passed for the changed handler and focused test
  modules; `ruff format --check` passed after formatting the added test.
- The release-equivalent command is running separately. It is known to enter
  a CPU-intensive CoreML compressor test despite the supplied marker filter;
  its exit status must be recorded before this plan is marked release-ready.
