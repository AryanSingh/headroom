import json
from unittest.mock import AsyncMock, MagicMock, patch

from fastapi.testclient import TestClient

from cutctx.backends.base import BackendResponse
from cutctx.proxy.models import ProxyConfig
from cutctx.proxy.server import create_app


def test_live_toggle_dedup_compression() -> None:
    config = ProxyConfig(
        backend="anyllm",
        anyllm_provider="openai",
        cache_enabled=False,
        rate_limit_enabled=False,
        optimize=True,
        admin_api_key="admin_12345",
    )

    mock_backend = MagicMock()
    mock_backend.name = "anyllm-openai"
    mock_backend.send_openai_message = AsyncMock(
        return_value=BackendResponse(
            body={
                "id": "chatcmpl-123",
                "object": "chat.completion",
                "model": "gpt-4o",
                "choices": [
                    {
                        "index": 0,
                        "message": {"role": "assistant", "content": "mocked response"},
                        "finish_reason": "stop",
                    }
                ],
                "usage": {"prompt_tokens": 10, "completion_tokens": 5, "total_tokens": 15},
            },
            status_code=200,
            headers={"content-type": "application/json"},
        )
    )

    with patch("cutctx.proxy.server.AnyLLMBackend", return_value=mock_backend):
        app = create_app(config)
        with TestClient(app) as client:
            admin_headers = {"x-cutctx-admin-key": "admin_12345"}

            res = client.post(
                "/config/flags",
                json={"dedup_enabled": False},
                headers=admin_headers,
            )
            assert res.status_code == 200

            payload = {
                "model": "gpt-4o",
                "messages": [
                    {
                        "role": "system",
                        "content": "Repeated line.\nRepeated line.\nRepeated line.\nRepeated line.\nRepeated line.\nRepeated line.\nRepeated line.\nRepeated line.\n",
                    },
                    {"role": "user", "content": "Run cargo build."},
                ],
            }

            headers = {"Authorization": "Bearer mock-key"}

            client.app.state.raise_server_exceptions = True  # Try to force error
            response1 = client.post("/v1/chat/completions", json=payload, headers=headers)
            print("RESPONSE BODY:", response1.text)
            assert response1.status_code == 200

            stats1 = client.get("/stats", headers=admin_headers).json()
            saved_before = stats1.get("metrics", {}).get("total_tokens_saved", 0)

            res2 = client.post(
                "/config/flags",
                json={"dedup_enabled": True},
                headers=admin_headers,
            )
            assert res2.status_code == 200

            response2 = client.post("/v1/chat/completions", json=payload, headers=headers)
            assert response2.status_code == 200

            stats2 = client.get("/stats", headers=admin_headers).json()
            saved_after = stats2.get("metrics", {}).get("total_tokens_saved", 0)

            applied_live = res2.json().get("applied_live", {})
            is_enabled = applied_live.get("dedup_enabled", {}).get("enabled") is True
            assert is_enabled, f"dedup_enabled was not applied live! res={res2.json()}"
