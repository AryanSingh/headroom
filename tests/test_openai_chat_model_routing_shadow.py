from __future__ import annotations

import anyio

from cutctx.proxy.handlers.openai.chat import OpenAIChatMixin
from cutctx.proxy.model_routing_evals import ModelRoutingEvalStore


class _Response:
    status_code = 200

    def json(self):  # type: ignore[no-untyped-def]
        return {
            "choices": [{"message": {"role": "assistant", "content": "same answer"}}],
            "usage": {
                "prompt_tokens": 100,
                "prompt_tokens_details": {"cached_tokens": 20},
            },
        }


def test_chat_shadow_replays_final_body_with_requested_model(monkeypatch, tmp_path) -> None:
    path = tmp_path / "routing.jsonl"
    monkeypatch.setenv("CUTCTX_MODEL_ROUTING_SHADOW_MODE", "true")
    monkeypatch.setenv("CUTCTX_MODEL_ROUTING_SHADOW_SAMPLE_RATE", "1")
    monkeypatch.setenv("CUTCTX_MODEL_ROUTING_EVAL_PATH", str(path))

    class Handler(OpenAIChatMixin):
        def __init__(self) -> None:
            self.calls = []

        async def _retry_request(self, *args, **kwargs):  # type: ignore[no-untyped-def]
            self.calls.append((args, kwargs))
            return _Response()

    handler = Handler()
    candidate_body = {
        "model": "gpt-5.4-mini",
        "messages": [{"role": "user", "content": "hello"}],
        "stream": False,
    }

    anyio.run(
        lambda: handler._maybe_model_routing_chat_shadow(
            request_id="req-chat-shadow",
            source_model="gpt-5.4",
            candidate_model="gpt-5.4-mini",
            url="https://api.openai.test/v1/chat/completions",
            headers={"authorization": "Bearer secret"},
            candidate_body=candidate_body,
            routing_metadata={
                "target_model": "gpt-5.4-mini",
                "confidence": 0.9,
                "scorer": "heuristic",
            },
            messages=candidate_body["messages"],
            candidate_json=_Response().json(),
        )
    )

    assert len(handler.calls) == 1
    args, _kwargs = handler.calls[0]
    assert args[3]["model"] == "gpt-5.4"
    assert candidate_body["model"] == "gpt-5.4-mini"
    records = ModelRoutingEvalStore(path).load()
    assert len(records) == 1
    assert records[0].source_model == "gpt-5.4"
    assert records[0].candidate_model == "gpt-5.4-mini"
    assert records[0].quality_score == 1.0


def test_chat_shadow_skips_unrouted_and_disabled_requests(monkeypatch) -> None:
    monkeypatch.delenv("CUTCTX_MODEL_ROUTING_SHADOW_MODE", raising=False)

    class Handler(OpenAIChatMixin):
        async def _retry_request(self, *args, **kwargs):  # type: ignore[no-untyped-def]
            raise AssertionError("shadow replay should not run")

    handler = Handler()
    common = {
        "request_id": "req-chat-off",
        "source_model": "gpt-5.4",
        "candidate_model": "gpt-5.4-mini",
        "url": "https://api.openai.test/v1/chat/completions",
        "headers": {},
        "candidate_body": {"model": "gpt-5.4-mini", "messages": []},
        "messages": [],
        "candidate_json": _Response().json(),
    }

    anyio.run(
        lambda: handler._maybe_model_routing_chat_shadow(
            **common,
            routing_metadata={"target_model": "gpt-5.4-mini"},
        )
    )
    anyio.run(
        lambda: handler._maybe_model_routing_chat_shadow(
            **common,
            routing_metadata=None,
        )
    )
