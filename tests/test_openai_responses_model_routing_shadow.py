from __future__ import annotations

import anyio

from cutctx.proxy.handlers.openai.responses import (
    _MISSING_ROUTING_FIELD,
    OpenAIResponsesMixin,
)
from cutctx.proxy.model_routing_evals import ModelRoutingEvalStore


class _Response:
    status_code = 200

    def json(self):  # type: ignore[no-untyped-def]
        return {
            "output": [
                {
                    "type": "message",
                    "content": [{"type": "output_text", "text": "same answer"}],
                }
            ],
            "usage": {
                "input_tokens": 100,
                "input_tokens_details": {"cached_tokens": 20},
            },
        }


def test_responses_shadow_restores_requested_model_and_original_reasoning(
    monkeypatch, tmp_path
) -> None:
    path = tmp_path / "routing.jsonl"
    monkeypatch.setenv("CUTCTX_MODEL_ROUTING_SHADOW_MODE", "true")
    monkeypatch.setenv("CUTCTX_MODEL_ROUTING_SHADOW_SAMPLE_RATE", "1")
    monkeypatch.setenv("CUTCTX_MODEL_ROUTING_EVAL_PATH", str(path))

    class Handler(OpenAIResponsesMixin):
        def __init__(self) -> None:
            self.calls = []

        async def _retry_request(self, *args, **kwargs):  # type: ignore[no-untyped-def]
            self.calls.append((args, kwargs))
            return _Response()

    handler = Handler()
    candidate_body = {
        "model": "gpt-5.4-mini",
        "input": "hello",
        "reasoning": {"effort": "high"},
    }

    anyio.run(
        lambda: handler._maybe_model_routing_responses_shadow(
            request_id="req-responses-shadow",
            source_model="gpt-5.4",
            candidate_model="gpt-5.4-mini",
            url="https://api.openai.test/v1/responses",
            headers={"authorization": "Bearer secret"},
            candidate_body=candidate_body,
            routing_metadata={
                "target_model": "gpt-5.4-mini",
                "confidence": 0.9,
                "scorer": "heuristic",
            },
            messages=[{"role": "user", "content": "hello"}],
            candidate_json=_Response().json(),
            original_reasoning={"effort": "medium"},
        )
    )

    assert len(handler.calls) == 1
    args, _kwargs = handler.calls[0]
    assert args[3]["model"] == "gpt-5.4"
    assert args[3]["reasoning"] == {"effort": "medium"}
    assert candidate_body["reasoning"] == {"effort": "high"}
    records = ModelRoutingEvalStore(path).load()
    assert len(records) == 1
    assert records[0].quality_score == 1.0


def test_responses_shadow_removes_router_injected_reasoning_when_original_missing(
    monkeypatch, tmp_path
) -> None:
    monkeypatch.setenv("CUTCTX_MODEL_ROUTING_SHADOW_MODE", "true")
    monkeypatch.setenv("CUTCTX_MODEL_ROUTING_SHADOW_SAMPLE_RATE", "1")
    monkeypatch.setenv("CUTCTX_MODEL_ROUTING_EVAL_PATH", str(tmp_path / "routing.jsonl"))

    class Handler(OpenAIResponsesMixin):
        def __init__(self) -> None:
            self.baseline_body = None

        async def _retry_request(self, _method, _url, _headers, body):  # type: ignore[no-untyped-def]
            self.baseline_body = body
            return _Response()

    handler = Handler()
    anyio.run(
        lambda: handler._maybe_model_routing_responses_shadow(
            request_id="req-no-reasoning",
            source_model="gpt-5.4",
            candidate_model="gpt-5.4-mini",
            url="https://api.openai.test/v1/responses",
            headers={},
            candidate_body={
                "model": "gpt-5.4-mini",
                "input": "hello",
                "reasoning": {"effort": "high"},
            },
            routing_metadata={"target_model": "gpt-5.4-mini"},
            messages=[{"role": "user", "content": "hello"}],
            candidate_json=_Response().json(),
            original_reasoning=_MISSING_ROUTING_FIELD,
        )
    )

    assert handler.baseline_body is not None
    assert "reasoning" not in handler.baseline_body
