"""Skill preserve must not alter the payload Cutctx forwards upstream.

Preservation is a routing decision. Earlier it was implemented by tagging
``metadata.cutctx_skill_preserve`` onto the message dicts, which had two
consequences that these tests pin down:

1. The extra key travelled to the provider. Anthropic's Messages API forbids
   unknown fields on a message object, so every request carrying skill or
   instruction text 400'd.
2. An otherwise untouched body no longer matched the client's bytes, so the
   byte-faithful forwarder re-serialised it — the prefix-cache collapse that
   ``test_proxy_byte_faithful_forwarding.py`` exists to prevent.
"""

from __future__ import annotations

import json

import httpx
import pytest

pytest.importorskip("fastapi")

from fastapi.testclient import TestClient

from cutctx.providers import OpenAIProvider
from cutctx.proxy.server import ProxyConfig, create_app
from cutctx.tokenizer import Tokenizer
from cutctx.transforms.content_router import ContentRouter, ContentRouterConfig

_SKILL_TEXT = "Here is my SKILL.md file:\n---\nname: demo\ndescription: d\n---\n" + (
    "Rule: keep this.\n" * 200
)


class _CapturingTransport(httpx.AsyncBaseTransport):
    def __init__(self) -> None:
        self.captured_body: bytes | None = None

    async def handle_async_request(self, request: httpx.Request) -> httpx.Response:
        body = b""
        async for chunk in request.stream:
            body += chunk
        self.captured_body = body
        return httpx.Response(
            200,
            json={
                "id": "msg_1",
                "type": "message",
                "role": "assistant",
                "content": [{"type": "text", "text": "ok"}],
                "usage": {"input_tokens": 10, "output_tokens": 3},
            },
        )


def _optimizing_app() -> tuple[TestClient, _CapturingTransport]:
    config = ProxyConfig(
        optimize=True,
        cache_enabled=False,
        rate_limit_enabled=False,
        cost_tracking_enabled=False,
        log_requests=False,
        ccr_inject_tool=False,
        ccr_handle_responses=False,
        ccr_context_tracking=False,
        image_optimize=False,
    )
    app = create_app(config)
    transport = _CapturingTransport()
    app.state.proxy.http_client = httpx.AsyncClient(transport=transport)
    return TestClient(app), transport


def _post_anthropic(client: TestClient, content: bytes) -> httpx.Response:
    return client.post(
        "/v1/messages",
        headers={
            "x-api-key": "test",
            "anthropic-version": "2023-06-01",
            "content-type": "application/json",
        },
        content=content,
    )


def _tokenizer() -> Tokenizer:
    return Tokenizer(OpenAIProvider().get_token_counter("gpt-4o"), "gpt-4o")


def test_preserved_message_carries_no_internal_keys_upstream() -> None:
    client, transport = _optimizing_app()
    body = json.dumps(
        {
            "model": "claude-sonnet-4-6",
            "max_tokens": 64,
            "messages": [{"role": "user", "content": _SKILL_TEXT}],
        }
    ).encode()

    response = _post_anthropic(client, body)
    assert response.status_code == 200, response.text
    assert transport.captured_body is not None

    sent = json.loads(transport.captured_body)
    assert [sorted(m.keys()) for m in sent["messages"]] == [["content", "role"]]


def test_preserve_only_request_is_forwarded_byte_identical() -> None:
    """Nothing compressed → upstream bytes equal the client's bytes."""
    client, transport = _optimizing_app()
    inbound = json.dumps(
        {
            "model": "claude-sonnet-4-6",
            "max_tokens": 64,
            "messages": [{"role": "user", "content": _SKILL_TEXT}],
        },
        separators=(",", ":"),
    ).encode()

    response = _post_anthropic(client, inbound)
    assert response.status_code == 200, response.text
    assert transport.captured_body == inbound, (
        "preserved-only request was re-serialised; byte-faithful forwarding broken"
    )


def test_router_still_compresses_with_skill_preserve_disabled() -> None:
    """``skill_preserve=False`` is a supported opt-out, not a crash.

    Regression: a function-local ``import os`` shadowed the module import, so
    disabling preservation raised ``UnboundLocalError`` from the parallel
    compression pass.
    """
    messages = [
        {"role": "user", "content": "hello"},
        {"role": "tool", "tool_call_id": "a", "content": "INFO tick\n" * 300},
        {"role": "tool", "tool_call_id": "b", "content": "WARN spin\n" * 300},
    ]
    router = ContentRouter(ContentRouterConfig(skill_preserve=False, min_section_tokens=10))
    result = router.apply([dict(m) for m in messages], _tokenizer())
    assert result.tokens_after < result.tokens_before


def test_explicit_compress_system_messages_beats_preservation() -> None:
    """The ``agent_90`` / ``max_savings`` opt-in must still reach the compressor."""
    system_prompt = "You are an agent. Rules:\n" + "\n".join(
        f"- Rule {i}: always verify tool output before quoting it." for i in range(120)
    )
    messages = [
        {"role": "system", "content": system_prompt},
        {"role": "user", "content": "go"},
    ]
    router = ContentRouter(ContentRouterConfig(skill_preserve=True, min_section_tokens=10))

    default = router.apply([dict(m) for m in messages], _tokenizer())
    assert "router:protected:system_message" in default.transforms_applied

    opted_in = router.apply(
        [dict(m) for m in messages], _tokenizer(), compress_system_messages=True
    )
    assert "router:protected:system_message" not in opted_in.transforms_applied
    assert "skill_preserve:passthrough" not in opted_in.transforms_applied
    assert opted_in.diagnostics["content_router"]["route_counts"].get("system_msg", 0) == 0
