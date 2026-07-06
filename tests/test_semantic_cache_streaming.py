import pytest
from httpx import AsyncClient

from cutctx.proxy.server import create_app, ProxyConfig

@pytest.fixture
def app():
    return create_app(ProxyConfig(cache_enabled=True))

@pytest.mark.asyncio
async def test_semantic_cache_streaming(app):
    """Test that streaming requests populate the semantic cache and return valid SSE replays."""
    # Ensure cache is enabled and clean
    proxy_cache = app.state.proxy.cache
    await proxy_cache.clear()

    request_body = {
        "model": "claude-3-5-sonnet-20241022",
        "messages": [{"role": "user", "content": "Hello"}],
        "stream": True,
        "max_tokens": 100,
        "metadata": {"user_id": "user_123"},
    }

    headers = {
        "x-cutctx-admin-key": "test_admin",
        "authorization": "Bearer sk-mock",
    }
    
    import json
    from unittest.mock import patch
    from httpx import Response
    from fastapi.testclient import TestClient
    
    def mock_stream():
        yield b'event: message_start\ndata: {"type":"message_start","message":{"id":"msg_123","type":"message","role":"assistant","content":[],"model":"claude-3-5-sonnet-20241022","stop_reason":null,"stop_sequence":null,"usage":{"input_tokens":10,"output_tokens":1}}}\n\n'
        yield b'event: content_block_start\ndata: {"type":"content_block_start","index":0,"content_block":{"type":"text","text":""}}\n\n'
        yield b'event: content_block_delta\ndata: {"type":"content_block_delta","index":0,"delta":{"type":"text_delta","text":"Hello World"}}\n\n'
        yield b'event: content_block_stop\ndata: {"type":"content_block_stop","index":0}\n\n'
        yield b'event: message_delta\ndata: {"type":"message_delta","delta":{"stop_reason":"end_turn","stop_sequence":null},"usage":{"output_tokens":10}}\n\n'
        yield b'event: message_stop\ndata: {"type":"message_stop"}\n\n'

    mock_response = Response(200, headers={"content-type": "text/event-stream"})
    
    async def mock_send(*args, **kwargs):
        async def mock_aiter_bytes():
            for chunk in mock_stream():
                yield chunk
        mock_response.aiter_bytes = mock_aiter_bytes
        mock_response.status_code = 200
        return mock_response
    
    with patch("httpx.AsyncClient.send", side_effect=mock_send):
        with TestClient(app) as client:
            response1 = client.post("/v1/messages", json=request_body, headers=headers)
            print("RESPONSE 1 STATUS:", response1.status_code)
            print("RESPONSE 1 TEXT:", response1.text)
            assert response1.status_code == 200
            
            import time
            time.sleep(0.1)

            stats = await proxy_cache.stats()
            print(f"CACHE STATS: {stats}")
            assert stats["entries"] == 1, "Streaming response was not cached"

            request_body["metadata"]["user_id"] = "user_456"
            response2 = client.post("/v1/messages", json=request_body, headers=headers)
            assert response2.status_code == 200
            
            content1_chunks = response1.text.split("\n\n")
            content2_chunks = response2.text.split("\n\n")
            assert len(content2_chunks) > 1, "Cache hit did not return multiple SSE chunks"
            assert content1_chunks == content2_chunks
