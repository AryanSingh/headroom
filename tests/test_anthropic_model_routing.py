from __future__ import annotations

import json

import anyio

from cutctx.proxy.handlers.anthropic import AnthropicHandlerMixin
from cutctx.proxy.model_router import ModelRouter, ModelRouterConfig, prepare_model_routing
from cutctx.proxy.model_routing_evals import ModelRoutingEvalStore


def test_anthropic_messages_to_routing_messages_extracts_text_only_blocks() -> None:
    messages = AnthropicHandlerMixin._anthropic_messages_to_routing_messages(
        [
            {
                "role": "user",
                "content": [
                    {"type": "text", "text": "hi"},
                    {"type": "tool_result", "tool_use_id": "toolu_1", "content": "ignored"},
                ],
            }
        ]
    )

    assert messages == [{"role": "user", "content": "hi"}]


def test_anthropic_low_complexity_routing_uses_normalized_messages() -> None:
    cfg = ModelRouterConfig.codex_gpt54mini_high_preset()

    class DummyHandler(AnthropicHandlerMixin):
        def __init__(self) -> None:
            self._model_router = ModelRouter(cfg)

    handler = DummyHandler()
    routing_messages = handler._anthropic_messages_to_routing_messages(
        [
            {
                "role": "user",
                "content": [{"type": "text", "text": "hi"}],
            }
        ]
    )

    model, metadata = prepare_model_routing(
        handler,
        "claude-sonnet-4-5",
        messages=routing_messages,
        request_savings_metadata={},
    )

    assert model == "claude-haiku-4-5"
    assert metadata is not None
    assert metadata["model_routing"]["target_model"] == "claude-haiku-4-5"


class _Response:
    status_code = 200

    def json(self):  # type: ignore[no-untyped-def]
        return {
            "role": "assistant",
            "content": [{"type": "text", "text": "same answer"}],
            "usage": {"input_tokens": 100},
        }


def test_anthropic_model_routing_shadow_replays_requested_model_and_records(
    monkeypatch, tmp_path
) -> None:
    path = tmp_path / "routing.jsonl"
    monkeypatch.setenv("CUTCTX_MODEL_ROUTING_SHADOW_MODE", "true")
    monkeypatch.setenv("CUTCTX_MODEL_ROUTING_SHADOW_SAMPLE_RATE", "1")
    monkeypatch.setenv("CUTCTX_MODEL_ROUTING_EVAL_PATH", str(path))

    class Handler(AnthropicHandlerMixin):
        def __init__(self) -> None:
            self.calls = []

        async def _retry_request(self, *args, **kwargs):  # type: ignore[no-untyped-def]
            self.calls.append((args, kwargs))
            return _Response()

    handler = Handler()
    original = json.dumps(
        {
            "model": "claude-sonnet-4-5",
            "messages": [{"role": "user", "content": "hello"}],
        }
    ).encode()

    anyio.run(
        lambda: handler._maybe_model_routing_shadow(
            request_id="req-claude-shadow",
            source_model="claude-sonnet-4-5",
            candidate_model="claude-haiku-4-5",
            provider_name="anthropic",
            url="https://api.anthropic.test/v1/messages",
            headers={"x-api-key": "secret"},
            original_body_bytes=original,
            routing_metadata={
                "target_model": "claude-haiku-4-5",
                "confidence": 0.9,
                "scorer": "heuristic",
            },
            messages=[{"role": "user", "content": "hello"}],
            candidate_json=_Response().json(),
        )
    )

    assert len(handler.calls) == 1
    _, kwargs = handler.calls[0]
    assert kwargs["original_body_bytes"] == original
    assert kwargs["body_mutated"] is False
    records = ModelRoutingEvalStore(path).load()
    assert len(records) == 1
    assert records[0].source_model == "claude-sonnet-4-5"
    assert records[0].candidate_model == "claude-haiku-4-5"
    assert records[0].quality_score == 1.0


def test_anthropic_model_routing_shadow_disabled_makes_no_replay(monkeypatch) -> None:
    monkeypatch.delenv("CUTCTX_MODEL_ROUTING_SHADOW_MODE", raising=False)

    class Handler(AnthropicHandlerMixin):
        async def _retry_request(self, *args, **kwargs):  # type: ignore[no-untyped-def]
            raise AssertionError("disabled shadow must not call upstream")

    anyio.run(
        lambda: Handler()._maybe_model_routing_shadow(
            request_id="req-off",
            source_model="claude-sonnet-4-5",
            candidate_model="claude-haiku-4-5",
            provider_name="anthropic",
            url="https://api.anthropic.test/v1/messages",
            headers={},
            original_body_bytes=b"{}",
            routing_metadata={"target_model": "claude-haiku-4-5"},
            messages=[],
            candidate_json=_Response().json(),
        )
    )
