from __future__ import annotations

from cutctx.proxy.handlers.anthropic import AnthropicHandlerMixin
from cutctx.proxy.model_router import ModelRouter, ModelRouterConfig, prepare_model_routing


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
