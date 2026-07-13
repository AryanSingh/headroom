"""Tests for the `/v1/compress` proxy endpoint."""

from __future__ import annotations

import json
from types import SimpleNamespace
from unittest.mock import patch

import pytest

pytest.importorskip("fastapi")

from fastapi.testclient import TestClient

from cutctx.proxy.server import ProxyConfig, create_app


@pytest.fixture
def client():
    config = ProxyConfig(
        optimize=True,
        cache_enabled=False,
        rate_limit_enabled=False,
        cost_tracking_enabled=False,
    )
    app = create_app(config)
    with TestClient(app) as c:
        yield c


@pytest.fixture
def client_no_optimize():
    config = ProxyConfig(
        optimize=False,
        cache_enabled=False,
        rate_limit_enabled=False,
        cost_tracking_enabled=False,
    )
    app = create_app(config)
    with TestClient(app) as c:
        yield c


@pytest.fixture
def client_off():
    config = ProxyConfig(
        optimize=True,
        compression_mode="off",
        cache_enabled=False,
        rate_limit_enabled=False,
        cost_tracking_enabled=False,
    )
    app = create_app(config)
    with TestClient(app) as c:
        yield c


class TestCompressEndpointValidation:
    def test_missing_messages_returns_400(self, client):
        response = client.post("/v1/compress", json={"model": "gpt-4"})
        assert response.status_code == 400
        data = response.json()
        assert data["error"]["type"] == "invalid_request"
        assert "messages" in data["error"]["message"]

    def test_missing_model_returns_400(self, client):
        response = client.post(
            "/v1/compress",
            json={"messages": [{"role": "user", "content": "hello"}]},
        )
        assert response.status_code == 400
        data = response.json()
        assert data["error"]["type"] == "invalid_request"
        assert "model" in data["error"]["message"]

    def test_invalid_json_returns_400(self, client):
        response = client.post(
            "/v1/compress",
            data="{not-json",
            headers={"content-type": "application/json"},
        )
        assert response.status_code == 400
        data = response.json()
        assert data["error"]["type"] == "invalid_request"


class TestCompressEndpointBasic:
    def test_empty_messages_returns_empty(self, client):
        response = client.post(
            "/v1/compress",
            json={"messages": [], "model": "gpt-4"},
        )
        assert response.status_code == 200
        data = response.json()
        assert data["messages"] == []
        assert data["tokens_before"] == 0
        assert data["tokens_after"] == 0
        assert data["tokens_saved"] == 0
        assert data["compression_ratio"] == 1.0
        assert data["transforms_applied"] == []
        assert data["transforms_summary"] == {}
        assert data["ccr_hashes"] == []

    def test_basic_compression_response_shape(self, client):
        response = client.post(
            "/v1/compress",
            json={
                "messages": [{"role": "user", "content": "Hello, world!"}],
                "model": "gpt-4",
            },
        )
        assert response.status_code == 200
        data = response.json()
        for key in (
            "messages",
            "tokens_before",
            "tokens_after",
            "tokens_saved",
            "compression_ratio",
            "transforms_applied",
            "transforms_summary",
            "ccr_hashes",
            "image_metrics",
            "diagnostics",
        ):
            assert key in data
        assert isinstance(data["messages"], list)
        assert data["tokens_before"] >= 0
        assert data["tokens_after"] >= 0
        assert data["tokens_saved"] >= 0
        assert data["compression_ratio"] > 0

    def test_bypass_header_returns_uncompressed(self, client):
        messages = [
            {"role": "user", "content": "Hello"},
            {"role": "assistant", "content": "Hi there!"},
            {"role": "user", "content": "How are you?"},
        ]
        response = client.post(
            "/v1/compress",
            json={"messages": messages, "model": "gpt-4"},
            headers={"x-cutctx-bypass": "true"},
        )
        assert response.status_code == 200
        data = response.json()
        assert data["messages"] == messages
        assert data["tokens_before"] == 0
        assert data["tokens_after"] == 0
        assert data["tokens_saved"] == 0
        assert data["compression_ratio"] == 1.0
        assert data["transforms_applied"] == []
        assert data["ccr_hashes"] == []

    def test_bypass_header_case_insensitive(self, client):
        response = client.post(
            "/v1/compress",
            json={"messages": [{"role": "user", "content": "Hello"}], "model": "gpt-4"},
            headers={"x-cutctx-bypass": "TRUE"},
        )
        assert response.status_code == 200
        data = response.json()
        assert data["messages"] == [{"role": "user", "content": "Hello"}]

    def test_off_policy_reports_router_passthrough(self, client_off):
        messages = [
            {
                "role": "tool",
                "content": "  exact whitespace  \nCUTCTX_TIMEOUT=30\n",
            }
        ]

        response = client_off.post(
            "/v1/compress",
            json={"messages": messages, "model": "gpt-4"},
        )

        assert response.status_code == 200
        data = response.json()
        assert data["messages"] == messages
        assert "router:off" in data["transforms_applied"]


class TestCompressEndpointCompression:
    def test_large_tool_output_gets_compressed(self, client):
        large_data = json.dumps(
            [
                {
                    "id": i,
                    "name": f"Item {i}",
                    "description": (
                        f"This detailed description item number {i}. "
                        "It contains various attributes and metadata typical "
                        "of API responses. Item status is active. "
                        f"Created on 2024-01-{(i % 28) + 1:02d}. "
                        f"category=electronics price={i * 10.99:.2f} "
                        f"rating={4.0 + (i % 10) / 10:.1f} stock={i * 5}."
                    ),
                    "tags": ["electronics", "sale", "featured", "new-arrival"],
                    "metadata": {
                        "created_by": "system",
                        "updated_at": "2024-01-15T00:00:00Z",
                        "version": i,
                        "source": "api",
                    },
                }
                for i in range(200)
            ]
        )
        messages = [
            {"role": "user", "content": "What items are available?"},
            {
                "role": "assistant",
                "content": None,
                "tool_calls": [
                    {
                        "id": "call_123",
                        "type": "function",
                        "function": {"name": "list_items", "arguments": "{}"},
                    }
                ],
            },
            {"role": "tool", "tool_call_id": "call_123", "content": large_data},
            {"role": "user", "content": "Summarize the first 5 items."},
        ]

        response = client.post(
            "/v1/compress",
            json={"messages": messages, "model": "gpt-4"},
        )
        assert response.status_code == 200
        data = response.json()
        assert data["tokens_before"] > 0
        assert data["tokens_after"] > 0
        assert data["tokens_after"] <= data["tokens_before"]
        assert data["tokens_saved"] == data["tokens_before"] - data["tokens_after"]
        assert data["savings_by_source"]["total_tokens"] == data["tokens_saved"]
        assert data["savings_by_source"]["tokens"]["cutctx_compression"] >= 0

    def test_image_payload_reports_multimodal_token_savings(self, client):
        class _FakeImageCompressor:
            def __init__(self):
                self.last_result = SimpleNamespace(
                    original_tokens=1000,
                    compressed_tokens=340,
                    technique=SimpleNamespace(value="preserve"),
                    confidence=0.9,
                )

            def has_images(self, messages):
                self._messages = messages
                return True

            def compress(self, messages, provider="openai"):
                assert provider == "openai"
                return messages

            def close(self):
                return None

        messages = [
            {
                "role": "user",
                "content": [
                    {"type": "text", "text": "Describe chart."},
                    {
                        "type": "image_url",
                        "image_url": {"url": "data:image/png;base64,AAAA", "detail": "high"},
                    },
                ],
            }
        ]

        with patch(
            "cutctx.proxy.helpers._get_image_compressor",
            return_value=_FakeImageCompressor(),
        ):
            response = client.post(
                "/v1/compress",
                json={"messages": messages, "model": "gpt-4o"},
            )

        assert response.status_code == 200
        data = response.json()
        assert data["tokens_before"] >= 1000
        assert data["tokens_saved"] >= 660
        assert data["tokens_after"] == data["tokens_before"] - data["tokens_saved"]
        assert data["savings_by_source"]["tokens"]["image_optimization"] == 660
        assert "image:preserve" in data["transforms_applied"]
        assert data["image_metrics"]["tokens_saved"] == 660

    def test_inline_audio_payload_reports_audio_metrics(self, client):
        class _FakeInlineAudioMetrics:
            audio_blocks_seen = 1
            audio_blocks_optimized = 1
            bytes_before = 4096
            bytes_after = 2048
            bytes_saved = 2048

        messages = [
            {
                "role": "user",
                "content": [
                    {"type": "text", "text": "Transcribe this memo."},
                    {
                        "type": "input_audio",
                        "input_audio": {"format": "wav", "data": "UklGRg=="},
                    },
                ],
            }
        ]

        with patch(
            "cutctx.transforms.audio_messages.compress_inline_audio_messages",
            return_value=(messages, _FakeInlineAudioMetrics()),
        ):
            response = client.post(
                "/v1/compress",
                json={"messages": messages, "model": "gpt-4o"},
            )

        assert response.status_code == 200
        data = response.json()
        assert "audio:inline_wav" in data["transforms_applied"]
        assert data["audio_metrics"]["audio_blocks_seen"] == 1
        assert data["audio_metrics"]["audio_blocks_optimized"] == 1
        assert data["audio_metrics"]["bytes_saved"] == 2048

    def test_assistant_text_uses_max_savings_profile_and_reports_diagnostics(self, client):
        messages = [
            {
                "role": "assistant",
                "content": "This is a long repeated explanation. " * 120,
            }
        ]

        response = client.post(
            "/v1/compress",
            json={"messages": messages, "model": "gpt-4"},
        )

        assert response.status_code == 200
        data = response.json()
        assert data["tokens_saved"] > 0
        assert data["diagnostics"]["profile"] == "max_savings"
        assert data["diagnostics"]["content_router"]["compressed_count"] >= 1
        assert data["diagnostics"]["content_router"]["min_ratio_threshold"] == 0.99

    def test_balanced_profile_reports_why_no_savings(self, client):
        messages = [
            {
                "role": "assistant",
                "content": "This is a long repeated explanation. " * 120,
            }
        ]

        response = client.post(
            "/v1/compress",
            json={
                "messages": messages,
                "model": "gpt-4",
                "config": {"profile": "balanced"},
            },
        )

        assert response.status_code == 200
        data = response.json()
        assert data["tokens_saved"] == 0
        assert data["diagnostics"]["profile"] == "balanced"
        assert "unchanged" in data["diagnostics"]["why_no_savings"]
        assert data["diagnostics"]["content_router"]["min_ratio_threshold"] < 0.99

    def test_max_savings_retries_after_balanced_skip_cache(self, client):
        messages = [
            {
                "role": "assistant",
                "content": "This is a long repeated explanation. " * 120,
            }
        ]

        balanced = client.post(
            "/v1/compress",
            json={
                "messages": messages,
                "model": "gpt-4",
                "config": {"profile": "balanced"},
            },
        )
        assert balanced.status_code == 200
        assert balanced.json()["tokens_saved"] == 0

        max_savings = client.post(
            "/v1/compress",
            json={
                "messages": messages,
                "model": "gpt-4",
                "config": {"profile": "max_savings"},
            },
        )
        assert max_savings.status_code == 200
        assert max_savings.json()["tokens_saved"] > 0

    def test_compress_endpoint_updates_stats_summary(self, client):
        messages = [
            {"role": "user", "content": "What items are available?"},
            {
                "role": "assistant",
                "content": None,
                "tool_calls": [
                    {
                        "id": "call_stats",
                        "type": "function",
                        "function": {"name": "list_items", "arguments": "{}"},
                    }
                ],
            },
            {
                "role": "tool",
                "tool_call_id": "call_stats",
                "content": json.dumps(
                    [
                        {
                            "id": i,
                            "name": f"Item {i}",
                            "description": (
                                f"This detailed description item number {i}. "
                                "It contains metadata, retries, duplicate fields, "
                                "and large API response structure compression tests."
                            ),
                            "tags": ["electronics", "sale", "featured", "new-arrival"],
                        }
                        for i in range(200)
                    ]
                ),
            },
            {"role": "user", "content": "Summarize first 5 items."},
        ]

        response = client.post(
            "/v1/compress",
            json={"messages": messages, "model": "gpt-4"},
        )
        assert response.status_code == 200
        compressed = response.json()
        assert compressed["tokens_before"] > 0

        stats_response = client.get("/stats")
        assert stats_response.status_code == 200
        stats = stats_response.json()
        assert stats.get("requests", {}).get("total", 0) >= 1
        assert stats.get("tokens", {}).get("saved", 0) >= 0

    def test_small_content_may_not_compress(self, client):
        response = client.post(
            "/v1/compress",
            json={
                "messages": [{"role": "user", "content": "Short text."}],
                "model": "gpt-4",
            },
        )
        assert response.status_code == 200
        data = response.json()
        assert data["tokens_saved"] >= 0
        assert data["tokens_after"] <= data["tokens_before"]
