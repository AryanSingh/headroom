# ChatGPT Subscription Safe Tool-Output Compression Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Compress eligible ChatGPT subscription tool-output strings while preserving every provider-owned continuation field and the existing reconnect/restart recovery behavior.

**Architecture:** Add a subscription-specific classifier, output-only compressor, and structural invariant validator beside the existing general Responses compressor. Route ChatGPT-authenticated HTTP requests and both WebSocket frame paths through that narrow helper; opaque, resumed, compacted, malformed, or failed candidates fall back to the sanitized original payload without closing the session.

**Tech Stack:** Python 3.11+, FastAPI/Starlette, asyncio, OpenAI Responses API, pytest, anyio, pytest-asyncio, hermetic HTTP/WebSocket replay harness.

## Global Constraints

- Preserve the existing session-recovery behavior for encrypted, opaque, compacted, and resumed ChatGPT subscription requests.
- Only replace a string `output` field on an input item whose type belongs to `OPENAI_RESPONSES_OUTPUT_TYPES`.
- Never change model, tools, instructions, messages, reasoning, encrypted content, IDs, item order, item count, request options, metadata, or envelope shape.
- Do not run tool-surface slimming, tool-schema compaction, positional-array conversion, latest-user-tail compression, message compression, or model routing for ChatGPT subscription compression.
- Keep remote-compaction requests on their existing exact-bypass path.
- Apply the same policy to the first WebSocket frame, later WebSocket frames, and HTTP fallback.
- Classifier, compressor, tokenizer, or validator failures must forward the sanitized original payload and must not close a WebSocket.
- Attribute tokens and bytes only for candidates accepted by the structural validator.
- Keep API-key OpenAI, OpenCode, Anthropic, and native-proxy behavior unchanged.
- All shell commands in this repository must be prefixed with `rtk`.

---

## File Structure

- Modify `cutctx/proxy/handlers/openai/responses.py`: own the subscription classifier, validator, output-only compression helper, executor wrapper, and HTTP/WebSocket call-site routing.
- Modify `tests/test_openai_responses_context_compaction.py`: specify classification, invariant validation, and exact passthrough contracts.
- Modify `tests/test_openai_responses_compression_units.py`: specify accepted compression, accepted attribution, and fail-open behavior of the focused helper.
- Modify `tests/test_openai_codex_ws_lifecycle.py`: specify first-frame, later-frame, opaque-resume, model-preservation, and connection-liveness behavior.
- Modify `tests/test_openai_codex_routing.py`: specify HTTP ordinary-turn compression and protected continuation behavior.
- Modify `tests/agent_e2e/fixtures/codex-websocket-direct/frame.json`: make the first fixture frame contain a compressible ordinary tool output while retaining provider-owned tools.
- Modify `tests/agent_e2e/fixtures/codex-websocket-direct/resume-frame.json`: make the second fixture frame an opaque continuation that must remain unchanged.
- Modify `tests/agent_e2e/fixtures/codex-websocket-direct/scenario.json`: describe the ordinary-then-opaque two-turn safety scenario.
- Modify `tests/agent_e2e/harness.py`: allow an individual replay test to start the real proxy with optimization enabled.
- Modify `tests/agent_e2e/test_replay_harness.py`: assert accepted first-turn compression and exact protected second-turn forwarding.

### Task 1: Subscription Safety Classifier and Structural Validator

**Files:**
- Modify: `cutctx/proxy/handlers/openai/responses.py:1380-1515`
- Modify: `tests/test_openai_responses_context_compaction.py:410-475`

**Interfaces:**
- Consumes: `_is_remote_compaction_subscription_request(payload: dict[str, Any]) -> bool`, `_contains_opaque_responses_continuation(payload: dict[str, Any]) -> bool`, and `OpenAIResponsesMixin.OPENAI_RESPONSES_OUTPUT_TYPES`.
- Produces: `_classify_chatgpt_subscription_compression(payload: dict[str, Any]) -> tuple[str, str | None]` and `_validate_chatgpt_subscription_tool_output_candidate(original: dict[str, Any], candidate: dict[str, Any], *, tokenizer: Any) -> tuple[bool, int]`.

- [ ] **Step 1: Replace the blanket-passthrough unit test with classifier contract tests**

Add these tests to `tests/test_openai_responses_context_compaction.py` after `test_codex_subscription_payload_skips_tool_schema_compaction`:

```python
@pytest.mark.parametrize(
    ("payload", "reason"),
    [
        (
            {
                "model": "gpt-5.4",
                "input": [
                    {"type": "reasoning", "encrypted_content": "opaque"},
                    {
                        "type": "function_call_output",
                        "call_id": "call_1",
                        "output": "compressible output " * 200,
                    },
                ],
            },
            "subscription_opaque_continuation",
        ),
        (
            {
                "model": "gpt-5.4",
                "previous_response_id": "resp_123",
                "input": [
                    {
                        "type": "function_call_output",
                        "call_id": "call_1",
                        "output": "compressible output " * 200,
                    }
                ],
            },
            "subscription_previous_response_resume",
        ),
        (
            {
                "model": "gpt-5.4",
                "input": [{"type": "compaction", "payload": "provider-owned"}],
                "client_metadata": {"remote_compaction": True},
            },
            "subscription_remote_compaction",
        ),
        (
            {"model": "gpt-5.4", "input": "unknown input container"},
            "subscription_no_eligible_output",
        ),
    ],
)
def test_chatgpt_subscription_classifier_rejects_protected_payloads(
    payload: dict[str, Any],
    reason: str,
) -> None:
    handler = _HandlerHarness(ContentRouter(ContentRouterConfig()))

    policy, actual_reason = handler._classify_chatgpt_subscription_compression(payload)

    assert policy == "passthrough"
    assert actual_reason == reason


def test_chatgpt_subscription_classifier_allows_only_recognized_string_outputs() -> None:
    handler = _HandlerHarness(ContentRouter(ContentRouterConfig()))
    payload = {
        "model": "gpt-5.4",
        "input": [
            {
                "type": "function_call_output",
                "call_id": "call_1",
                "output": "compressible output " * 200,
            }
        ],
    }

    policy, reason = handler._classify_chatgpt_subscription_compression(payload)

    assert policy == "tool_outputs_only"
    assert reason is None
```

- [ ] **Step 2: Run the classifier tests and verify the missing-method failure**

Run:

```bash
rtk pytest -q \
  tests/test_openai_responses_context_compaction.py::test_chatgpt_subscription_classifier_rejects_protected_payloads \
  tests/test_openai_responses_context_compaction.py::test_chatgpt_subscription_classifier_allows_only_recognized_string_outputs
```

Expected: FAIL because `_classify_chatgpt_subscription_compression` does not exist.

- [ ] **Step 3: Implement the classifier beside the existing Responses unit adapter**

Add this method before `_compress_openai_responses_live_text_units_with_router` in `cutctx/proxy/handlers/openai/responses.py`:

```python
    def _classify_chatgpt_subscription_compression(
        self,
        payload: dict[str, Any],
    ) -> tuple[str, str | None]:
        """Select the narrow mutation policy for a ChatGPT subscription payload."""
        if _is_remote_compaction_subscription_request(payload):
            return "passthrough", "subscription_remote_compaction"
        previous_response_id = payload.get("previous_response_id")
        if isinstance(previous_response_id, str) and previous_response_id:
            return "passthrough", "subscription_previous_response_resume"
        if _contains_opaque_responses_continuation(payload):
            return "passthrough", "subscription_opaque_continuation"

        items = payload.get("input")
        if not isinstance(items, list) or any(not isinstance(item, dict) for item in items):
            return "passthrough", "subscription_no_eligible_output"
        if any(item.get("type") == "compaction" for item in items):
            return "passthrough", "subscription_opaque_continuation"

        eligible = any(
            item.get("type") in self.OPENAI_RESPONSES_OUTPUT_TYPES
            and isinstance(item.get("output"), str)
            for item in items
        )
        if not eligible:
            return "passthrough", "subscription_no_eligible_output"
        return "tool_outputs_only", None
```

- [ ] **Step 4: Run the classifier tests and verify they pass**

Run the command from Step 2.

Expected: 5 parameterized/test cases PASS.

- [ ] **Step 5: Add validator acceptance and rejection tests**

Add the following tests in the same test file:

```python
def test_chatgpt_subscription_validator_accepts_only_smaller_output_strings() -> None:
    handler = _HandlerHarness(ContentRouter(ContentRouterConfig()))
    original = {
        "model": "gpt-5.4",
        "tools": [{"type": "function", "name": "read_fixture"}],
        "input": [
            {
                "type": "function_call_output",
                "call_id": "call_1",
                "output": "one two three four five six",
            }
        ],
    }
    candidate = copy.deepcopy(original)
    candidate["input"][0]["output"] = "one two"

    valid, saved = handler._validate_chatgpt_subscription_tool_output_candidate(
        original,
        candidate,
        tokenizer=_StubTokenizer(),
    )

    assert valid is True
    assert saved == 4


@pytest.mark.parametrize(
    "mutate",
    [
        lambda body: body.update({"model": "gpt-5.6-sol"}),
        lambda body: body.update({"tools": []}),
        lambda body: body["input"][0].update({"call_id": "call_changed"}),
        lambda body: body["input"].reverse(),
        lambda body: body["input"][1].update({"encrypted_content": "changed"}),
        lambda body: body.update({"metadata": {"changed": True}}),
        lambda body: body["input"][0].update({"output": "one two three four five six seven"}),
    ],
)
def test_chatgpt_subscription_validator_rejects_wider_or_larger_mutations(mutate) -> None:
    handler = _HandlerHarness(ContentRouter(ContentRouterConfig()))
    original = {
        "model": "gpt-5.4",
        "tools": [{"type": "function", "name": "read_fixture"}],
        "input": [
            {
                "type": "function_call_output",
                "call_id": "call_1",
                "output": "one two three four five six",
            },
            {"type": "reasoning", "encrypted_content": "opaque"},
        ],
    }
    candidate = copy.deepcopy(original)
    candidate["input"][0]["output"] = "one two"
    mutate(candidate)

    valid, saved = handler._validate_chatgpt_subscription_tool_output_candidate(
        original,
        candidate,
        tokenizer=_StubTokenizer(),
    )

    assert valid is False
    assert saved == 0
```

Also add `import copy` at the top of `tests/test_openai_responses_context_compaction.py`.

- [ ] **Step 6: Run the validator tests and verify the missing-method failure**

Run:

```bash
rtk pytest -q \
  tests/test_openai_responses_context_compaction.py::test_chatgpt_subscription_validator_accepts_only_smaller_output_strings \
  tests/test_openai_responses_context_compaction.py::test_chatgpt_subscription_validator_rejects_wider_or_larger_mutations
```

Expected: FAIL because `_validate_chatgpt_subscription_tool_output_candidate` does not exist.

- [ ] **Step 7: Implement the validator**

Add this method immediately after the classifier:

```python
    def _validate_chatgpt_subscription_tool_output_candidate(
        self,
        original: dict[str, Any],
        candidate: dict[str, Any],
        *,
        tokenizer: Any,
    ) -> tuple[bool, int]:
        """Prove that a candidate changed only smaller allowlisted output strings."""
        if original.keys() != candidate.keys():
            return False, 0
        for key in original:
            if key != "input" and original[key] != candidate[key]:
                return False, 0

        original_items = original.get("input")
        candidate_items = candidate.get("input")
        if not isinstance(original_items, list) or not isinstance(candidate_items, list):
            return False, 0
        if len(original_items) != len(candidate_items):
            return False, 0

        total_saved = 0
        changed_outputs = 0
        for original_item, candidate_item in zip(original_items, candidate_items, strict=True):
            if not isinstance(original_item, dict) or not isinstance(candidate_item, dict):
                return False, 0
            if original_item.keys() != candidate_item.keys():
                return False, 0
            if original_item == candidate_item:
                continue
            if original_item.get("type") not in self.OPENAI_RESPONSES_OUTPUT_TYPES:
                return False, 0
            original_output = original_item.get("output")
            candidate_output = candidate_item.get("output")
            if not isinstance(original_output, str) or not isinstance(candidate_output, str):
                return False, 0
            original_without_output = {k: v for k, v in original_item.items() if k != "output"}
            candidate_without_output = {k: v for k, v in candidate_item.items() if k != "output"}
            if original_without_output != candidate_without_output:
                return False, 0
            before = tokenizer.count_text(original_output)
            after = tokenizer.count_text(candidate_output)
            if after >= before:
                return False, 0
            total_saved += before - after
            changed_outputs += 1

        if changed_outputs == 0:
            return False, 0
        return True, total_saved
```

- [ ] **Step 8: Run the Task 1 tests**

Run:

```bash
rtk pytest -q tests/test_openai_responses_context_compaction.py
```

Expected: PASS, including the existing provider-owned tool-schema test.

- [ ] **Step 9: Commit the classifier and validator**

```bash
rtk git add cutctx/proxy/handlers/openai/responses.py tests/test_openai_responses_context_compaction.py
rtk git commit -m "feat: classify safe ChatGPT subscription compression"
```

### Task 2: Focused Output-Only Compressor and Executor

**Files:**
- Modify: `cutctx/proxy/handlers/openai/responses.py:1515-1565,2213-2250`
- Modify: `tests/test_openai_responses_compression_units.py:120-230`

**Interfaces:**
- Consumes: `_classify_chatgpt_subscription_compression`, `_validate_chatgpt_subscription_tool_output_candidate`, `_compress_openai_responses_live_text_units_with_router`, `self.openai_provider.get_token_counter(model)`, and `self._run_compression_in_executor`.
- Produces: `_compress_chatgpt_subscription_tool_outputs(payload: dict[str, Any], *, model: str, request_id: str, timing: dict[str, float] | None = None) -> tuple[dict[str, Any], bool, int, list[str], str | None, int, int, int]` and `_compress_chatgpt_subscription_tool_outputs_in_executor(payload: dict[str, Any], *, model: str, request_id: str) -> tuple[dict[str, Any], bool, int, list[str], str | None, int, int, int, dict[str, float]]`.

- [ ] **Step 1: Add an accepted-compression test that also checks attribution**

Add this test to `tests/test_openai_responses_compression_units.py`:

```python
def test_chatgpt_subscription_helper_compresses_only_tool_output_and_attributes_savings():
    router = ContentRouter()

    def compress(self, content: str, **_kwargs):
        return RouterCompressionResult(
            compressed="kept words",
            original=content,
            strategy_used=CompressionStrategy.KOMPRESS,
        )

    router.compress = MethodType(compress, router)
    handler = _handler_with_router(router)
    long_text = " ".join(f"word{i}" for i in range(180))
    payload = {
        "model": "gpt-5.4",
        "tools": [{"type": "function", "name": "read_fixture", "description": long_text}],
        "instructions": long_text,
        "input": [
            {
                "type": "function_call_output",
                "call_id": "call_1",
                "output": long_text,
            },
            {
                "type": "message",
                "role": "user",
                "content": [{"type": "input_text", "text": long_text}],
            },
        ],
    }

    updated, modified, saved, transforms, reason, before, after, attempted = (
        handler._compress_chatgpt_subscription_tool_outputs(
            payload,
            model="gpt-5.4",
            request_id="req_subscription_safe",
        )
    )

    assert modified is True
    assert saved == 178
    assert attempted == 180
    assert reason is None
    assert after < before
    assert updated["input"][0]["output"] == "kept words"
    assert updated["input"][1] == payload["input"][1]
    assert updated["tools"] == payload["tools"]
    assert updated["instructions"] == payload["instructions"]
    assert transforms == ["router:openai:responses:function_call_output:kompress"]
```

- [ ] **Step 2: Add fail-open tests for protected input, invariant failure, and compressor failure**

Add these tests below the accepted-compression test:

```python
def test_chatgpt_subscription_helper_passthrough_preserves_opaque_payload():
    handler = _handler_with_router(ContentRouter())
    payload = {
        "model": "gpt-5.6-sol",
        "input": [
            {"type": "reasoning", "encrypted_content": "opaque"},
            {
                "type": "function_call_output",
                "call_id": "call_1",
                "output": "compressible output " * 200,
            },
        ],
    }

    result = handler._compress_chatgpt_subscription_tool_outputs(
        payload,
        model="gpt-5.6-sol",
        request_id="req_subscription_opaque",
    )

    assert result[0] is payload
    assert result[1:5] == (False, 0, [], "subscription_opaque_continuation")
    assert result[5] == result[6]
    assert result[7] == 0


def test_chatgpt_subscription_helper_rejects_router_mutation_outside_output(monkeypatch):
    handler = _handler_with_router(ContentRouter())
    payload = {
        "model": "gpt-5.4",
        "input": [
            {
                "type": "function_call_output",
                "call_id": "call_1",
                "output": "compressible output " * 200,
            }
        ],
    }
    candidate = copy.deepcopy(payload)
    candidate["model"] = "gpt-5.6-sol"
    candidate["input"][0]["output"] = "short"
    monkeypatch.setattr(
        handler,
        "_compress_openai_responses_live_text_units_with_router",
        lambda *args, **kwargs: (candidate, True, 399, ["unsafe"], {"applied": 1}, [], 400),
    )

    result = handler._compress_chatgpt_subscription_tool_outputs(
        payload,
        model="gpt-5.4",
        request_id="req_subscription_invariant",
    )

    assert result[0] is payload
    assert result[1:5] == (False, 0, [], "subscription_invariant_failed")


def test_chatgpt_subscription_helper_fails_open_when_router_raises(monkeypatch):
    handler = _handler_with_router(ContentRouter())
    payload = {
        "model": "gpt-5.4",
        "input": [
            {
                "type": "function_call_output",
                "call_id": "call_1",
                "output": "compressible output " * 200,
            }
        ],
    }

    def raise_compression(*args, **kwargs):
        raise RuntimeError("synthetic compressor failure")

    monkeypatch.setattr(
        handler,
        "_compress_openai_responses_live_text_units_with_router",
        raise_compression,
    )

    result = handler._compress_chatgpt_subscription_tool_outputs(
        payload,
        model="gpt-5.4",
        request_id="req_subscription_failure",
    )

    assert result[0] is payload
    assert result[1:5] == (False, 0, [], "subscription_compression_failed")
```

Add `import copy` to this test file.

- [ ] **Step 3: Run the focused helper tests and verify the missing-method failure**

Run:

```bash
rtk pytest -q tests/test_openai_responses_compression_units.py -k chatgpt_subscription_helper
```

Expected: FAIL because `_compress_chatgpt_subscription_tool_outputs` does not exist.

- [ ] **Step 4: Implement the synchronous focused helper**

Add this method after `_validate_chatgpt_subscription_tool_output_candidate`:

```python
    def _compress_chatgpt_subscription_tool_outputs(
        self,
        payload: dict[str, Any],
        *,
        model: str,
        request_id: str,
        timing: dict[str, float] | None = None,
    ) -> tuple[dict[str, Any], bool, int, list[str], str | None, int, int, int]:
        """Compress only validated mutable tool outputs for ChatGPT subscription traffic."""
        input_bytes = len(json.dumps(payload).encode("utf-8"))
        try:
            policy, passthrough_reason = self._classify_chatgpt_subscription_compression(payload)
            if policy != "tool_outputs_only":
                return payload, False, 0, [], passthrough_reason, input_bytes, input_bytes, 0

            candidate, modified, _router_saved, transforms, _units, _strategies, attempted = (
                self._compress_openai_responses_live_text_units_with_router(
                    copy.deepcopy(payload),
                    model=model,
                    request_id=request_id,
                    timing=timing,
                )
            )
            if not modified:
                return (
                    payload,
                    False,
                    0,
                    [],
                    "subscription_no_eligible_output",
                    input_bytes,
                    input_bytes,
                    attempted,
                )

            tokenizer = self.openai_provider.get_token_counter(model)
            valid, validated_saved = self._validate_chatgpt_subscription_tool_output_candidate(
                payload,
                candidate,
                tokenizer=tokenizer,
            )
            if not valid:
                return (
                    payload,
                    False,
                    0,
                    [],
                    "subscription_invariant_failed",
                    input_bytes,
                    input_bytes,
                    attempted,
                )

            output_bytes = len(json.dumps(candidate).encode("utf-8"))
            return (
                candidate,
                True,
                validated_saved,
                list(dict.fromkeys(transforms)),
                None,
                input_bytes,
                output_bytes,
                attempted,
            )
        except Exception as exc:
            logger.warning(
                "[%s] ChatGPT subscription tool-output compression failed open: %s: %s",
                request_id,
                type(exc).__name__,
                exc,
            )
            return (
                payload,
                False,
                0,
                [],
                "subscription_compression_failed",
                input_bytes,
                input_bytes,
                0,
            )
```

- [ ] **Step 5: Run the focused helper tests and verify they pass**

Run the command from Step 3.

Expected: 4 tests PASS.

- [ ] **Step 6: Add an executor-wrapper test**

Add this test to `tests/test_openai_responses_compression_units.py`:

```python
@pytest.mark.asyncio
async def test_chatgpt_subscription_helper_uses_bounded_executor():
    handler = _handler_with_router(ContentRouter())
    handler._run_compression_in_executor = AsyncMock(
        return_value=(
            {"model": "gpt-5.4", "input": []},
            False,
            0,
            [],
            "subscription_no_eligible_output",
            32,
            32,
            0,
        )
    )

    result = await handler._compress_chatgpt_subscription_tool_outputs_in_executor(
        {"model": "gpt-5.4", "input": []},
        model="gpt-5.4",
        request_id="req_subscription_executor",
    )

    assert handler._run_compression_in_executor.await_count == 1
    assert result[-1] == {}
```

Add `from unittest.mock import AsyncMock` and `import pytest` to the file if they are not already imported.

- [ ] **Step 7: Implement the bounded executor wrapper**

Add this method immediately after `_compress_openai_responses_payload_in_executor`:

```python
    async def _compress_chatgpt_subscription_tool_outputs_in_executor(
        self,
        payload: dict[str, Any],
        *,
        model: str,
        request_id: str,
    ) -> tuple[dict[str, Any], bool, int, list[str], str | None, int, int, int, dict[str, float]]:
        timing: dict[str, float] = {}

        def _compress():  # noqa: ANN202
            return self._compress_chatgpt_subscription_tool_outputs(
                payload,
                model=model,
                request_id=request_id,
                timing=timing,
            )

        result = await self._run_compression_in_executor(
            _compress,
            timeout=COMPRESSION_TIMEOUT_SECONDS,
        )
        return (*result, timing)
```

- [ ] **Step 8: Run all compression-unit tests**

Run:

```bash
rtk pytest -q tests/test_openai_responses_compression_units.py
```

Expected: PASS.

- [ ] **Step 9: Commit the focused compressor**

```bash
rtk git add cutctx/proxy/handlers/openai/responses.py tests/test_openai_responses_compression_units.py
rtk git commit -m "feat: compress safe ChatGPT tool outputs"
```

### Task 3: HTTP Fallback Integration

**Files:**
- Modify: `cutctx/proxy/handlers/openai/responses.py:2880-3065`
- Modify: `tests/test_openai_codex_routing.py:449-535`

**Interfaces:**
- Consumes: `_compress_chatgpt_subscription_tool_outputs_in_executor` from Task 2 and the existing general `_compress_openai_responses_payload_in_executor` for API-key traffic.
- Produces: one HTTP routing branch in which ChatGPT subscription requests skip tool-surface slimming and use only the focused helper.

- [ ] **Step 1: Add an HTTP ordinary-turn compression test**

Add this test before `test_handle_openai_responses_opaque_continuation_preserves_model_and_payload`:

```python
def test_handle_openai_responses_chatgpt_compresses_only_ordinary_tool_output(monkeypatch):
    long_output = "compressible output " * 200
    tools = [
        {
            "type": "function",
            "name": "read_fixture",
            "description": "provider-owned description " * 40,
            "parameters": {"type": "object", "properties": {}},
        }
    ]
    request = _build_request(
        {
            "model": "gpt-5.4",
            "input": [
                {
                    "type": "function_call_output",
                    "call_id": "call_1",
                    "output": long_output,
                }
            ],
            "tools": tools,
        },
        {
            "Authorization": "Bearer sk-test",
            "ChatGPT-Account-ID": "acct-from-jwt",
            "User-Agent": "Codex Desktop/1.0",
        },
    )
    handler = _DummyOpenAIHandler()
    handler.config.optimize = True
    compressed = {
        "model": "gpt-5.4",
        "input": [
            {
                "type": "function_call_output",
                "call_id": "call_1",
                "output": "short output",
            }
        ],
        "tools": tools,
        "store": False,
        "stream": True,
    }
    handler._compress_chatgpt_subscription_tool_outputs_in_executor = AsyncMock(
        return_value=(
            compressed,
            True,
            398,
            ["router:openai:responses:function_call_output:kompress"],
            None,
            5000,
            500,
            400,
            {},
        )
    )
    handler._compress_openai_responses_payload_in_executor = AsyncMock(
        side_effect=AssertionError("subscription traffic used the general compressor")
    )
    monkeypatch.setattr("cutctx.tokenizers.get_tokenizer", lambda model: _DummyTokenizer())

    response = anyio.run(handler.handle_openai_responses, request)

    assert response.status_code == 200
    assert handler.captured_stream_request is not None
    _, _, body = handler.captured_stream_request
    assert body["input"][0]["output"] == "short output"
    assert body["tools"] == tools
```

Add `AsyncMock` to the existing `unittest.mock` import.

- [ ] **Step 2: Run the HTTP test and verify it fails on the current general-compressor path**

Run:

```bash
rtk pytest -q tests/test_openai_codex_routing.py::test_handle_openai_responses_chatgpt_compresses_only_ordinary_tool_output
```

Expected: FAIL because the ChatGPT request calls the general compressor or does not call the focused helper.

- [ ] **Step 3: Split the HTTP optimization path by authentication mode**

In `handle_openai_responses`, keep the existing remote-compaction outer guard and replace the shared slimming/compression call with this branch structure:

```python
                tool_scaffolding_tokens = estimate_tool_scaffolding_tokens(
                    body.get("tools"),
                    tokenizer,
                )
                tool_surface_tokens_saved = 0
                original_tools_payload = copy.deepcopy(body.get("tools"))
                if is_chatgpt_auth:
                    (
                        body,
                        _modified,
                        _tokens_saved,
                        _transforms,
                        _reason,
                        _bytes_before,
                        _bytes_after,
                        _attempted_tokens,
                        _compression_timing,
                    ) = await self._compress_chatgpt_subscription_tool_outputs_in_executor(
                        body,
                        model=model,
                        request_id=request_id,
                    )
                else:
                    tool_surface_result = slim_tool_surface(
                        body.get("tools"),
                        query=tool_surface_query,
                        tokenizer=tokenizer,
                        tool_choice=body.get("tool_choice"),
                        config=self.config,
                        messages=body.get("input"),
                    )
                    tool_surface_tokens_saved = tool_surface_result.tokens_saved
                    if tool_surface_result.modified:
                        body["tools"] = tool_surface_result.tools
                        tokens_saved += tool_surface_tokens_saved
                        optimized_tokens = max(0, original_tokens - tokens_saved)
                        schema_savings_metadata = merge_savings_metadata(
                            schema_savings_metadata,
                            {"api_surface_slimming": {"tokens": tool_surface_result.tokens_saved}},
                        )
                        transforms_applied = [
                            "openai:responses:tool_surface_slimming",
                            *list(transforms_applied),
                        ]
                    (
                        body,
                        _modified,
                        _tokens_saved,
                        _transforms,
                        _reason,
                        _bytes_before,
                        _bytes_after,
                        _attempted_tokens,
                        _compression_timing,
                    ) = await self._compress_openai_responses_payload_in_executor(
                        body,
                        model=model,
                        request_id=request_id,
                    )
```

Keep the existing post-call accounting and logging. Guard `_tool_schema_savings_metadata` with `not is_chatgpt_auth` in addition to its current transform check so subscription tools can never contribute schema-compaction attribution.

- [ ] **Step 4: Run HTTP routing tests**

Run:

```bash
rtk pytest -q \
  tests/test_openai_codex_routing.py::test_handle_openai_responses_chatgpt_compresses_only_ordinary_tool_output \
  tests/test_openai_codex_routing.py::test_handle_openai_responses_opaque_continuation_preserves_model_and_payload \
  tests/test_openai_codex_routing.py::test_remote_compaction_subscription_body_is_forwarded_unchanged \
  tests/test_openai_codex_routing.py::test_handle_openai_responses_opaque_continuation_still_shrinks_oversized_images
```

Expected: all selected tests PASS.

- [ ] **Step 5: Commit the HTTP integration**

```bash
rtk git add cutctx/proxy/handlers/openai/responses.py tests/test_openai_codex_routing.py
rtk git commit -m "feat: route ChatGPT HTTP compression safely"
```

### Task 4: First and Later WebSocket Frame Integration

**Files:**
- Modify: `cutctx/proxy/handlers/openai/responses.py:4735-4925,5225-5435`
- Modify: `tests/test_openai_codex_ws_lifecycle.py:373-560`

**Interfaces:**
- Consumes: `_compress_chatgpt_subscription_tool_outputs_in_executor` and the existing WebSocket metrics/logging tuple contract.
- Produces: identical subscription compression policy for first and later `response.create` frames, with general compression retained for non-subscription WebSockets.

- [ ] **Step 1: Add a first-frame test that proves tools remain intact and output compresses**

Add this test after `test_ws_chatgpt_subscription_preserves_requested_model_before_forwarding`:

```python
@pytest.mark.asyncio
async def test_ws_chatgpt_first_frame_uses_safe_tool_output_compressor():
    tools = [{"type": "function", "name": "read_fixture", "description": "provider owned"}]
    inner = {
        "model": "gpt-5.4",
        "tools": tools,
        "input": [
            {
                "type": "function_call_output",
                "call_id": "call_1",
                "output": "compressible output " * 200,
            }
        ],
    }
    frame = json.dumps({"type": "response.create", "response": inner})
    upstream = _FakeUpstream(
        [
            json.dumps({"type": "response.created", "response": {"id": "r_1"}}),
            json.dumps({"type": "response.completed", "response": {"id": "r_1"}}),
        ]
    )
    client_ws = _FakeWebSocket(frames=[frame])
    client_ws.headers["chatgpt-account-id"] = "acct-123"
    handler = _DummyOpenAIHandler()
    handler.config.optimize = True
    handler._compress_chatgpt_subscription_tool_outputs_in_executor = AsyncMock(
        return_value=(
            {**inner, "input": [{**inner["input"][0], "output": "short output"}]},
            True,
            398,
            ["router:openai:responses:function_call_output:kompress"],
            None,
            5000,
            500,
            400,
            {},
        )
    )
    handler._compress_openai_responses_payload_in_executor = AsyncMock(
        side_effect=AssertionError("subscription first frame used the general compressor")
    )

    with patch.dict(sys.modules, {"websockets": _make_fake_websockets_module(upstream)}):
        await handler.handle_openai_responses_ws(client_ws)

    forwarded = json.loads(upstream.sent[0])["response"]
    assert forwarded["tools"] == tools
    assert forwarded["input"][0]["output"] == "short output"
```

Add `AsyncMock` to the existing mock imports.

- [ ] **Step 2: Add later-frame compression and opaque fail-open tests**

Add these tests after `test_ws_second_turn_preserves_requested_model_under_chatgpt_auth`:

```python
@pytest.mark.asyncio
async def test_ws_chatgpt_later_frame_uses_safe_tool_output_compressor():
    second_inner = {
        "model": "gpt-5.6-terra",
        "input": [
            {
                "type": "function_call_output",
                "call_id": "call_2",
                "output": "compressible output " * 200,
            }
        ],
    }
    client_ws = _FakeWebSocket(
        frames=[_first_frame(), json.dumps({"type": "response.create", "response": second_inner})]
    )
    client_ws.headers["chatgpt-account-id"] = "acct-123"
    upstream = _FakeUpstream(
        [
            json.dumps({"type": "response.created", "response": {"id": "r_1"}}),
            json.dumps({"type": "response.completed", "response": {"id": "r_1"}}),
        ]
    )
    handler = _DummyOpenAIHandler()
    handler.config.optimize = True
    calls = 0

    async def compress_subscription(payload, *, model, request_id):
        nonlocal calls
        calls += 1
        if calls == 1:
            size = len(json.dumps(payload).encode())
            return payload, False, 0, [], "subscription_no_eligible_output", size, size, 0, {}
        candidate = copy.deepcopy(payload)
        candidate["input"][0]["output"] = "short output"
        return candidate, True, 398, ["router:openai:responses:function_call_output:kompress"], None, 5000, 500, 400, {}

    handler._compress_chatgpt_subscription_tool_outputs_in_executor = compress_subscription

    with patch.dict(sys.modules, {"websockets": _make_fake_websockets_module(upstream)}):
        await asyncio.wait_for(handler.handle_openai_responses_ws(client_ws), timeout=5.0)

    second_forwarded = json.loads(upstream.sent[1])["response"]
    assert second_forwarded["model"] == "gpt-5.6-terra"
    assert second_forwarded["input"][0]["output"] == "short output"


@pytest.mark.asyncio
async def test_ws_chatgpt_safe_compressor_failure_forwards_opaque_frame_without_closing():
    inner = {
        "model": "gpt-5.6-sol",
        "input": [
            {"type": "reasoning", "encrypted_content": "opaque-model-bound-continuation"},
            {"type": "message", "role": "user", "content": [{"type": "input_text", "text": "continue"}]},
        ],
    }
    client_ws = _FakeWebSocket(
        frames=[json.dumps({"type": "response.create", "response": inner})]
    )
    client_ws.headers["chatgpt-account-id"] = "acct-123"
    upstream = _FakeUpstream(
        [
            json.dumps({"type": "response.created", "response": {"id": "r_1"}}),
            json.dumps({"type": "response.completed", "response": {"id": "r_1"}}),
        ]
    )
    handler = _DummyOpenAIHandler()
    handler.config.optimize = True
    handler._compress_chatgpt_subscription_tool_outputs_in_executor = AsyncMock(
        side_effect=RuntimeError("synthetic optional compression failure")
    )
    handler._openai_responses_context_guard = MagicMock(
        return_value=(True, 294_402, 242_400, 258_400)
    )

    with patch.dict(sys.modules, {"websockets": _make_fake_websockets_module(upstream)}):
        await handler.handle_openai_responses_ws(client_ws)

    forwarded = json.loads(upstream.sent[0])["response"]
    assert forwarded["model"] == "gpt-5.6-sol"
    assert forwarded["input"] == inner["input"]
    assert client_ws.close_code != 1009
```

Add `import copy` to the file.

- [ ] **Step 3: Run the new WebSocket tests and verify they fail on inconsistent call sites**

Run:

```bash
rtk pytest -q tests/test_openai_codex_ws_lifecycle.py -k 'safe_tool_output_compressor or later_frame_uses_safe or safe_compressor_failure'
```

Expected: FAIL because first frame uses the general compressor and later frames remain full passthrough.

- [ ] **Step 4: Route the first frame through the focused helper and skip subscription slimming**

In the first-frame compression block, set subscription tool-surface values without calling or mutating through `slim_tool_surface`, then select the compressor:

```python
                            _tool_scaffolding_tokens = estimate_tool_scaffolding_tokens(
                                _inner.get("tools") if isinstance(_inner, dict) else None,
                                get_tokenizer(_model),
                            )
                            _tool_surface_saved = 0
                            if is_chatgpt_auth:
                                _tool_surface_result = None
                            else:
                                _tool_surface_result = slim_tool_surface(
                                    _inner.get("tools") if isinstance(_inner, dict) else None,
                                    query=extract_responses_query(
                                        _inner if isinstance(_inner, dict) else {}
                                    ),
                                    tokenizer=get_tokenizer(_model),
                                    config=self.config,
                                    tool_choice=_inner.get("tool_choice")
                                    if isinstance(_inner, dict)
                                    else None,
                                    messages=_inner if isinstance(_inner, dict) else None,
                                )
                                _tool_surface_saved = _tool_surface_result.tokens_saved
                                if _tool_surface_result.modified and isinstance(_inner, dict):
                                    _inner = {**_inner, "tools": _tool_surface_result.tools}
                                    ws_savings_metadata = merge_savings_metadata(
                                        ws_savings_metadata,
                                        {"api_surface_slimming": {"tokens": _tool_surface_saved}},
                                    )

                            _original_ws_tools = copy.deepcopy(_inner.get("tools"))
                            if is_chatgpt_auth:
                                compression_result = (
                                    await self._compress_chatgpt_subscription_tool_outputs_in_executor(
                                        _inner,
                                        model=_model,
                                        request_id=request_id,
                                    )
                                )
                            else:
                                compression_result = (
                                    await self._compress_openai_responses_payload_in_executor(
                                        _inner,
                                        model=_model,
                                        request_id=request_id,
                                    )
                                )
                            (
                                _new_inner,
                                _modified,
                                _ws_saved,
                                _ws_transforms,
                                _ws_reason,
                                _bytes_before,
                                _bytes_after,
                                _ws_attempted_tokens,
                                _ws_compression_timing,
                            ) = compression_result
```

Update the later accounting check from `_tool_surface_result.modified` to `_tool_surface_result is not None and _tool_surface_result.modified`.

- [ ] **Step 5: Route later frames through the same helper**

In `_maybe_compress_response_create_frame`, replace the unconditional slimming call and the `allow_payload_mutation=not is_chatgpt_auth` call with:

```python
                                frame_surface_saved = 0
                                if not is_chatgpt_auth:
                                    frame_surface_result = slim_tool_surface(
                                        inner_payload.get("tools")
                                        if isinstance(inner_payload, dict)
                                        else None,
                                        query=extract_responses_query(
                                            inner_payload if isinstance(inner_payload, dict) else {}
                                        ),
                                        config=self.config,
                                        tokenizer=get_tokenizer(model_for_frame),
                                        tool_choice=inner_payload.get("tool_choice")
                                        if isinstance(inner_payload, dict)
                                        else None,
                                        messages=inner_payload
                                        if isinstance(inner_payload, dict)
                                        else None,
                                    )
                                    frame_surface_saved = frame_surface_result.tokens_saved
                                    if frame_surface_result.modified and isinstance(
                                        inner_payload, dict
                                    ):
                                        inner_payload = {
                                            **inner_payload,
                                            "tools": frame_surface_result.tools,
                                        }
                                        ws_savings_metadata = merge_savings_metadata(
                                            ws_savings_metadata,
                                            {"api_surface_slimming": {"tokens": frame_surface_saved}},
                                        )

                                original_frame_tools = copy.deepcopy(inner_payload.get("tools"))
                                if is_chatgpt_auth:
                                    frame_compression_result = (
                                        await self._compress_chatgpt_subscription_tool_outputs_in_executor(
                                            inner_payload,
                                            model=model_for_frame,
                                            request_id=request_id,
                                        )
                                    )
                                else:
                                    frame_compression_result = (
                                        await self._compress_openai_responses_payload_in_executor(
                                            inner_payload,
                                            model=model_for_frame,
                                            request_id=request_id,
                                        )
                                    )
                                (
                                    new_inner,
                                    modified,
                                    frame_saved,
                                    frame_transforms,
                                    frame_reason,
                                    bytes_before,
                                    bytes_after,
                                    frame_attempted_tokens,
                                    frame_compression_timing,
                                ) = frame_compression_result
```

Keep the existing sanitizer before this branch and keep `implicit_downgrade_allowed=False` for ChatGPT auth. Broaden the existing opaque-continuation refusal exemption to every ChatGPT subscription frame because this helper is optional and must always fail open.

In the first-frame compression exception handler, change the refusal condition so an optional subscription compressor failure always forwards the sanitized original frame:

```python
                    if _ws_action.refuse and not is_chatgpt_auth:
                        logger.error(
                            "[%s] WS /v1/responses REFUSING to forward frame after "
                            "compression failure (reason=%s, bytes=%d)",
                            request_id,
                            _ws_action.reason,
                            _ws_action.frame_bytes,
                        )
                        termination_cause = "compression_refused"
                        with contextlib.suppress(Exception):
                            await websocket.close(
                                code=1009,
                                reason=(
                                    "cutctx: compression "
                                    f"{_ws_action.reason} — please compact context and retry"
                                ),
                            )
                        return
```

In the later-frame exception handler, make the equivalent change:

```python
                                if guard_refuse and not is_chatgpt_auth:
                                    logger.error(
                                        "[%s] WS /v1/responses refusing frame after "
                                        "compression failure (reason=%s, estimated_tokens=%d "
                                        "threshold=%d context_limit=%d model=%s frame=%d)",
                                        request_id,
                                        refusal_reason,
                                        guard_estimated,
                                        guard_threshold,
                                        guard_limit,
                                        str(inner_payload.get("model") or "unknown"),
                                        frame_index,
                                    )
                                    termination_cause = "context_refused"
                                    with contextlib.suppress(Exception):
                                        await websocket.close(
                                            code=1009,
                                            reason=(
                                                "cutctx: context too large — compact context and retry"
                                            ),
                                        )
                                    with contextlib.suppress(Exception):
                                        await upstream.close()
                                    return raw_msg, False, "context_refused"
```

The non-subscription fail-closed behavior remains unchanged. ChatGPT subscription frames fail open because their helper is optional and their authoritative continuation size is known only to the provider.

- [ ] **Step 6: Run the focused WebSocket lifecycle tests**

Run:

```bash
rtk pytest -q \
  tests/test_openai_codex_ws_lifecycle.py::test_ws_chatgpt_first_frame_uses_safe_tool_output_compressor \
  tests/test_openai_codex_ws_lifecycle.py::test_ws_chatgpt_later_frame_uses_safe_tool_output_compressor \
  tests/test_openai_codex_ws_lifecycle.py::test_ws_chatgpt_safe_compressor_failure_forwards_opaque_frame_without_closing \
  tests/test_openai_codex_ws_lifecycle.py::test_ws_opaque_continuation_ignores_approximate_context_refusal \
  tests/test_openai_codex_ws_lifecycle.py::test_ws_second_turn_preserves_requested_model_under_chatgpt_auth \
  tests/test_openai_codex_ws_lifecycle.py::test_ws_first_frame_compression_uses_bounded_executor
```

Expected: all selected tests PASS.

- [ ] **Step 7: Commit the WebSocket integration**

```bash
rtk git add cutctx/proxy/handlers/openai/responses.py tests/test_openai_codex_ws_lifecycle.py
rtk git commit -m "feat: safely compress ChatGPT websocket outputs"
```

### Task 5: Restart/Resume Replay Regression

**Files:**
- Modify: `tests/agent_e2e/fixtures/codex-websocket-direct/frame.json`
- Modify: `tests/agent_e2e/fixtures/codex-websocket-direct/resume-frame.json`
- Modify: `tests/agent_e2e/fixtures/codex-websocket-direct/scenario.json`
- Modify: `tests/agent_e2e/harness.py:152-184`
- Modify: `tests/agent_e2e/test_replay_harness.py:40-56`

**Interfaces:**
- Consumes: `ReplayHarness.run("codex-websocket-direct") -> ReplayResult` and the strict upstream request capture.
- Produces: `ReplayHarness(fixture_root: str | Path, *, optimize: bool = False)` plus a real-network ordinary turn, proxy restart, and opaque resume fixture.

- [ ] **Step 1: Change the first WebSocket fixture frame into an ordinary tool-output turn**

Replace `tests/agent_e2e/fixtures/codex-websocket-direct/frame.json` with:

```json
{
  "type": "response.create",
  "response": {
    "model": "gpt-5.4",
    "input": [
      {
        "type": "function_call_output",
        "call_id": "call_fixture_compressible",
        "output": "alpha beta gamma delta epsilon zeta eta theta iota kappa lambda mu alpha beta gamma delta epsilon zeta eta theta iota kappa lambda mu alpha beta gamma delta epsilon zeta eta theta iota kappa lambda mu alpha beta gamma delta epsilon zeta eta theta iota kappa lambda mu alpha beta gamma delta epsilon zeta eta theta iota kappa lambda mu alpha beta gamma delta epsilon zeta eta theta iota kappa lambda mu alpha beta gamma delta epsilon zeta eta theta iota kappa lambda mu alpha beta gamma delta epsilon zeta eta theta iota kappa lambda mu alpha beta gamma delta epsilon zeta eta theta iota kappa lambda mu alpha beta gamma delta epsilon zeta eta theta iota kappa lambda mu alpha beta gamma delta epsilon zeta eta theta iota kappa lambda mu alpha beta gamma delta epsilon zeta eta theta iota kappa lambda mu alpha beta gamma delta epsilon zeta eta theta iota kappa lambda mu alpha beta gamma delta epsilon zeta eta theta iota kappa lambda mu alpha beta gamma delta epsilon zeta eta theta iota kappa lambda mu alpha beta gamma delta epsilon zeta eta theta iota kappa lambda mu alpha beta gamma delta epsilon zeta eta theta iota kappa lambda mu alpha beta gamma delta epsilon zeta eta theta iota kappa lambda mu alpha beta gamma delta epsilon zeta eta theta iota kappa lambda mu alpha beta gamma delta epsilon zeta eta theta iota kappa lambda mu"
      }
    ],
    "tools": [
      {
        "type": "function",
        "name": "read_fixture",
        "description": "Provider-owned fixture tool description that must remain unchanged.",
        "parameters": {"type": "object", "properties": {}}
      }
    ],
    "client_metadata": {"thread_id": "thread_fixture_713f09b80e62"},
    "stream": false,
    "store": true
  }
}
```

- [ ] **Step 2: Change the second WebSocket fixture frame into protected opaque continuation state**

Replace `tests/agent_e2e/fixtures/codex-websocket-direct/resume-frame.json` with:

```json
{
  "type": "response.create",
  "response": {
    "model": "gpt-5.6-sol",
    "input": [
      {
        "type": "reasoning",
        "encrypted_content": "encrypted_fixture_ws_resume_fef929fde341"
      },
      {
        "type": "custom_tool_call_output",
        "call_id": "call_fixture_resume",
        "output": "this output remains unchanged because it shares an opaque continuation request"
      },
      {
        "type": "message",
        "role": "user",
        "content": [{"type": "input_text", "text": "continue"}]
      }
    ],
    "tools": [],
    "stream": false,
    "store": true
  }
}
```

- [ ] **Step 3: Make the scenario restart the proxy between the ordinary and opaque turns**

Replace `tests/agent_e2e/fixtures/codex-websocket-direct/scenario.json` with:

```json
{
  "schema_version": 1,
  "id": "codex-websocket-direct",
  "client": "codex",
  "client_version": "0.145.0-alpha.18",
  "tags": [
    "oauth-auth", "websocket", "multi-turn", "tool-output-compression",
    "encrypted-continuation", "proxy-restart", "field-preservation",
    "stream-true", "store-false"
  ],
  "runtimes": ["python"],
  "unsupported_runtimes": [
    {
      "runtime": "native",
      "reason": "Native subscription WebSocket routing is not implemented.",
      "tracking_issue": "CUTCTX-NATIVE-RESPONSES-SUBSCRIPTION"
    }
  ],
  "steps": [
    {
      "action": "request",
      "transport": "websocket",
      "path": "/v1/responses",
      "headers_fixture": "headers.json",
      "body_fixture": "frame.json",
      "upstream_script": "success-ws.json"
    },
    {"action": "restart_proxy"},
    {
      "action": "request",
      "transport": "websocket",
      "path": "/v1/responses",
      "headers_fixture": "headers.json",
      "body_fixture": "resume-frame.json",
      "upstream_script": "resume-success-ws.json"
    }
  ],
  "assertions": {
    "required_body_values": {"$.store": false, "$.stream": true},
    "preserved_paths": ["$.model", "$.tools"],
    "terminal_event": "response.completed"
  }
}
```

- [ ] **Step 4: Add an opt-in optimization switch to the replay harness**

Change the `ReplayHarness` constructor and `_start_proxy` configuration in `tests/agent_e2e/harness.py`:

```python
class ReplayHarness:
    def __init__(self, fixture_root: str | Path, *, optimize: bool = False) -> None:
        self.fixture_root = Path(fixture_root)
        self.optimize = optimize
        self.upstream = ScriptedUpstream()
        self.upstream_server = ThreadedUvicorn(self.upstream.app)
        self.proxy_port = _unused_port()
        self.proxy_server: ThreadedUvicorn | None = None
```

```python
        config = ProxyConfig(
            host="127.0.0.1",
            port=self.proxy_port,
            optimize=self.optimize,
            image_optimize=False,
            audio_optimize=False,
            cache_enabled=False,
            rate_limit_enabled=False,
            cost_tracking_enabled=False,
            subscription_tracking_enabled=False,
            anthropic_api_url=self.upstream_server.url,
            openai_api_url=self.upstream_server.url,
        )
```

The default remains `False`, so every existing replay scenario keeps its current behavior.

- [ ] **Step 5: Strengthen the replay assertion**

Replace `test_subscription_websocket_sanitizes_every_response_create_frame` with:

```python
@pytest.mark.timeout(30)
def test_subscription_websocket_compresses_ordinary_output_and_preserves_opaque_resume() -> None:
    scenario_dir = FIXTURES / "codex-websocket-direct"
    original_first = json.loads((scenario_dir / "frame.json").read_text(encoding="utf-8"))[
        "response"
    ]
    original_resume = json.loads(
        (scenario_dir / "resume-frame.json").read_text(encoding="utf-8")
    )["response"]

    with ReplayHarness(FIXTURES, optimize=True) as harness:
        result = harness.run("codex-websocket-direct")

    assert result.proxy_restarts == 1
    assert len(result.upstream_requests) == 2
    first = result.upstream_requests[0]["body"]
    resumed = result.upstream_requests[1]["body"]
    assert first["store"] is False
    assert first["stream"] is True
    assert first["model"] == original_first["model"]
    assert first["tools"] == original_first["tools"]
    assert first["input"][0]["call_id"] == original_first["input"][0]["call_id"]
    assert len(first["input"][0]["output"].split()) < len(
        original_first["input"][0]["output"].split()
    )
    assert resumed["store"] is False
    assert resumed["stream"] is True
    assert resumed["model"] == original_resume["model"]
    assert resumed["input"] == original_resume["input"]
    assert resumed["tools"] == original_resume["tools"]
    assert result.terminal_events == ["response.completed", "response.completed"]
```

Add `import json` at the top of `tests/agent_e2e/test_replay_harness.py`.

- [ ] **Step 6: Run the WebSocket replay test**

Run:

```bash
rtk pytest -q tests/agent_e2e/test_replay_harness.py::test_subscription_websocket_compresses_ordinary_output_and_preserves_opaque_resume
```

Expected: PASS with one proxy restart, two `response.completed` events, a shorter first output, and an unchanged opaque second input.

- [ ] **Step 7: Run the existing real proxy restart/resume regression**

Run:

```bash
rtk pytest -q tests/agent_e2e/test_replay_harness.py::test_captured_codex_resume_succeeds_after_real_proxy_restart
```

Expected: PASS with one proxy restart and two completed HTTP turns.

- [ ] **Step 8: Commit the replay regression**

```bash
rtk git add \
  tests/agent_e2e/fixtures/codex-websocket-direct/frame.json \
  tests/agent_e2e/fixtures/codex-websocket-direct/resume-frame.json \
  tests/agent_e2e/fixtures/codex-websocket-direct/scenario.json \
  tests/agent_e2e/harness.py \
  tests/agent_e2e/test_replay_harness.py
rtk git commit -m "test: protect ChatGPT compression resume behavior"
```

### Task 6: Full Regression and Attribution Verification

**Files:**
- Modify only if a failing assertion reveals a defect: `cutctx/proxy/handlers/openai/responses.py`
- Test: `tests/test_openai_responses_context_compaction.py`
- Test: `tests/test_openai_responses_compression_units.py`
- Test: `tests/test_openai_codex_ws_lifecycle.py`
- Test: `tests/test_openai_codex_routing.py`
- Test: `tests/agent_e2e/test_replay_harness.py`
- Test: surrounding OpenAI and model-router suites discovered by `rtk find`.

**Interfaces:**
- Consumes: all implementation and test contracts from Tasks 1-5.
- Produces: verified evidence that accepted subscription frames report savings while opaque/restarted sessions remain resumable.

- [ ] **Step 1: Run the focused implementation suites**

```bash
rtk pytest -q \
  tests/test_openai_responses_context_compaction.py \
  tests/test_openai_responses_compression_units.py \
  tests/test_openai_codex_ws_lifecycle.py \
  tests/test_openai_codex_routing.py
```

Expected: PASS with no failure, error, or timeout.

- [ ] **Step 2: Run all replay scenarios**

```bash
rtk pytest -q tests/agent_e2e/test_replay_harness.py
```

Expected: PASS, including both the WebSocket ordinary/opaque scenario and the HTTP proxy-restart scenario.

- [ ] **Step 3: Run surrounding OpenAI handler and router suites**

```bash
rtk pytest -q \
  tests/test_openai_*.py \
  tests/test_model_router.py \
  tests/test_model_routing_presets.py
```

Expected: PASS. API-key Responses tests must continue to observe general tool-schema/content compression, and ChatGPT tests must preserve requested models.

- [ ] **Step 4: Run static checks on the modified Python files**

```bash
rtk ruff check \
  cutctx/proxy/handlers/openai/responses.py \
  tests/test_openai_responses_context_compaction.py \
  tests/test_openai_responses_compression_units.py \
  tests/test_openai_codex_ws_lifecycle.py \
  tests/test_openai_codex_routing.py \
  tests/agent_e2e/test_replay_harness.py
```

Expected: no lint errors.

- [ ] **Step 5: Inspect the final diff for forbidden subscription mutations**

```bash
rtk git diff --check
rtk git diff -- cutctx/proxy/handlers/openai/responses.py tests/test_openai_responses_context_compaction.py tests/test_openai_responses_compression_units.py tests/test_openai_codex_ws_lifecycle.py tests/test_openai_codex_routing.py tests/agent_e2e
```

Expected: no whitespace errors; ChatGPT-authenticated branches call only `_compress_chatgpt_subscription_tool_outputs_in_executor`, never mutate tools, and retain the opaque-continuation refusal exemption.

- [ ] **Step 6: Commit any verification-only correction**

If Step 1-5 required a production or assertion correction, stage only the files changed for that correction and commit:

```bash
rtk git add cutctx/proxy/handlers/openai/responses.py tests
rtk git commit -m "fix: preserve ChatGPT compression invariants"
```

If no correction was needed, do not create an empty commit.

## Completion Evidence

Before reporting completion, record these facts from the passing tests and final diff:

- An ordinary ChatGPT subscription tool-output string is shorter upstream and contributes positive `tokens_saved`.
- The first WebSocket frame and later WebSocket frames use the same focused helper.
- Subscription tool definitions remain exactly equal before and after processing.
- Encrypted continuation and `previous_response_id` requests remain passthrough.
- The opaque WebSocket path does not close with code 1009 after an optional compression failure.
- The HTTP proxy-restart replay still completes both turns.
- Remote compaction remains an exact bypass.
- API-key OpenAI Responses compression remains on the general compressor.
