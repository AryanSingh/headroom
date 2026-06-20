from __future__ import annotations

import json
from collections.abc import AsyncIterator
from unittest.mock import MagicMock, patch

import pytest

from headroom.proxy.savings_metadata import extract_savings_metadata, merge_savings_metadata
from headroom.proxy.semantic_cache import SemanticCache
from headroom.proxy.savings_tracker import HEADROOM_SAVINGS_PATH_ENV_VAR
from headroom.savings import SavingsSource


def test_extract_savings_metadata_from_structured_header() -> None:
    payload = {
        "provider_prompt_cache": {"tokens": 100, "usd": 0.01},
        "semantic_cache": {"tokens": 200},
        "prefix_cache_self_hosted": {"tokens": 300},
        "model_routing": {"tokens": 400, "usd": 0.05},
    }

    metadata = extract_savings_metadata(
        request_headers={"x-headroom-savings-metadata": json.dumps(payload)}
    )

    assert metadata is not None
    assert metadata[SavingsSource.PROVIDER_PROMPT_CACHE.value]["tokens"] == 100
    assert metadata[SavingsSource.SEMANTIC_CACHE.value]["tokens"] == 200
    assert metadata[SavingsSource.PREFIX_CACHE_SELF_HOSTED.value]["tokens"] == 300
    assert metadata[SavingsSource.MODEL_ROUTING.value]["tokens"] == 400
    assert metadata[SavingsSource.MODEL_ROUTING.value]["usd"] == 0.05


def test_extract_savings_metadata_from_integration_aliases() -> None:
    metadata = extract_savings_metadata(
        body={
            "headroom_savings_metadata": {
                "litellm": {"cache_hit_tokens": 50},
                "gptcache": {"saved_prompt_tokens": 60},
                "vllm_apc": {"prefix_cache_hits": 70},
                "model_routing": {"tokens_routed": 80, "usd_saved": 0.09},
            }
        }
    )

    assert metadata is not None
    assert metadata[SavingsSource.PROVIDER_PROMPT_CACHE.value]["tokens"] == 50
    assert metadata[SavingsSource.SEMANTIC_CACHE.value]["tokens"] == 60
    assert metadata[SavingsSource.PREFIX_CACHE_SELF_HOSTED.value]["tokens"] == 70
    assert metadata[SavingsSource.MODEL_ROUTING.value]["tokens"] == 80
    assert metadata[SavingsSource.MODEL_ROUTING.value]["usd"] == 0.09


def test_extract_savings_metadata_from_dedicated_headers() -> None:
    metadata = extract_savings_metadata(
        response_headers={
            "x-headroom-provider-cache-tokens": "10",
            "x-headroom-semantic-cache-avoided-tokens": "20",
            "x-headroom-prefix-cache-hits": "30",
            "x-headroom-model-routing-tokens": "40",
            "x-headroom-model-routing-usd": "0.12",
        }
    )

    assert metadata is not None
    assert metadata[SavingsSource.PROVIDER_PROMPT_CACHE.value]["tokens"] == 10
    assert metadata[SavingsSource.SEMANTIC_CACHE.value]["tokens"] == 20
    assert metadata[SavingsSource.PREFIX_CACHE_SELF_HOSTED.value]["tokens"] == 30
    assert metadata[SavingsSource.MODEL_ROUTING.value]["tokens"] == 40
    assert metadata[SavingsSource.MODEL_ROUTING.value]["usd"] == 0.12


def test_merge_savings_metadata_adds_duplicate_sources() -> None:
    metadata = merge_savings_metadata(
        {SavingsSource.SEMANTIC_CACHE.value: {"tokens": 10, "usd": 0.01}},
        {SavingsSource.SEMANTIC_CACHE.value: {"tokens": 15, "usd": 0.02}},
    )

    assert metadata is not None
    assert metadata[SavingsSource.SEMANTIC_CACHE.value]["tokens"] == 25
    assert metadata[SavingsSource.SEMANTIC_CACHE.value]["usd"] == 0.03


async def test_semantic_cache_preserves_tokens_saved_per_hit() -> None:
    cache = SemanticCache()
    messages = [{"role": "user", "content": "hello"}]

    await cache.set(
        messages,
        "gpt-4o",
        b"{}",
        {},
        tokens_saved=123,
    )
    cached = await cache.get(messages, "gpt-4o")

    assert cached is not None
    assert cached.tokens_saved_per_hit == 123


def test_live_proxy_persists_header_savings_metadata(tmp_path, monkeypatch) -> None:
    fastapi = pytest.importorskip("fastapi")
    assert fastapi is not None
    from fastapi.testclient import TestClient

    from headroom.proxy.server import ProxyConfig, create_app

    state_path = tmp_path / "proxy_savings.json"
    monkeypatch.setenv(HEADROOM_SAVINGS_PATH_ENV_VAR, str(state_path))

    async def fake_stream(body: dict, headers: dict) -> AsyncIterator[str]:
        yield (
            'data: {"id":"c1","object":"chat.completion.chunk",'
            '"choices":[{"index":0,"delta":{"role":"assistant","content":"ok"}}]}\n\n'
        )
        yield (
            'data: {"id":"c1","object":"chat.completion.chunk","choices":[],'
            '"usage":{"prompt_tokens":100,"completion_tokens":5,"total_tokens":105}}\n\n'
        )
        yield "data: [DONE]\n\n"

    backend = MagicMock()
    backend.name = "anyllm-openai"
    backend.stream_openai_message = fake_stream

    telemetry = {
        "semantic_cache": {"tokens": 60},
        "vllm_apc": {"prefix_cache_hits": 40},
        "model_routing": {"tokens_routed": 25, "usd_saved": 0.03},
    }

    config = ProxyConfig(
        optimize=False,
        cache_enabled=False,
        rate_limit_enabled=False,
        backend="anyllm",
        anyllm_provider="openai",
    )
    with patch("headroom.proxy.server.AnyLLMBackend", return_value=backend):
        app = create_app(config)
        with TestClient(app) as client:
            resp = client.post(
                "/v1/chat/completions",
                headers={
                    "Authorization": "Bearer test-key",
                    "x-headroom-savings-metadata": json.dumps(telemetry),
                },
                json={
                    "model": "gpt-4o-mini",
                    "messages": [{"role": "user", "content": "hello"}],
                    "stream": True,
                    "stream_options": {"include_usage": True},
                },
            )

    assert resp.status_code == 200, resp.text[:300]
    assert "[DONE]" in resp.text

    persisted = json.loads(state_path.read_text())
    row = persisted["history"][-1]
    by_source = row["savings_by_source_tokens"]
    assert by_source[SavingsSource.SEMANTIC_CACHE.value] == 60
    assert by_source[SavingsSource.PREFIX_CACHE_SELF_HOSTED.value] == 40
    assert by_source[SavingsSource.MODEL_ROUTING.value] == 25
    assert row["savings_by_source_usd"][SavingsSource.MODEL_ROUTING.value] == 0.03
