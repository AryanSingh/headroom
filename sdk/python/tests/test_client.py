"""Tests for Cutctx SDK client."""

from __future__ import annotations

from unittest.mock import MagicMock, patch

from cutctx_sdk.client import CutctxClient


class TestCutctxClient:
    def test_init_defaults(self):
        c = CutctxClient()
        assert c._proxy_url == "http://localhost:8787"
        assert c._api_key is None
        assert c._model == "claude-sonnet-4-5"

    def test_init_custom(self):
        c = CutctxClient(proxy_url="https://proxy.example.com", api_key="key-123", model="gpt-4")
        assert c._proxy_url == "https://proxy.example.com"
        assert c._api_key == "key-123"
        assert c._model == "gpt-4"

    def test_headers_with_key(self):
        c = CutctxClient(api_key="test-key")
        h = c._headers()
        assert h["X-Cutctx-Key"] == "test-key"
        assert h["Content-Type"] == "application/json"

    def test_headers_without_key(self):
        c = CutctxClient()
        h = c._headers()
        assert "X-Cutctx-Key" not in h

    @patch("cutctx_sdk.client._requests")
    def test_compress_success(self, mock_req):
        mock_resp = MagicMock()
        mock_resp.json.return_value = {"messages": [{"role": "user", "content": "compressed"}]}
        mock_resp.raise_for_status = MagicMock()
        mock_req.post.return_value = mock_resp

        c = CutctxClient()
        result = c.compress([{"role": "user", "content": "hello"}])

        assert result == [{"role": "user", "content": "compressed"}]
        mock_req.post.assert_called_once()

    @patch("cutctx_sdk.client._requests")
    def test_retrieve_success(self, mock_req):
        mock_resp = MagicMock()
        mock_resp.json.return_value = {"content": "original text"}
        mock_resp.raise_for_status = MagicMock()
        mock_req.get.return_value = mock_resp

        c = CutctxClient()
        result = c.retrieve("<<ccr:abc123>>")
        assert result == "original text"

    @patch("cutctx_sdk.client._requests")
    def test_health_success(self, mock_req):
        mock_resp = MagicMock()
        mock_resp.json.return_value = {"status": "ok"}
        mock_req.get.return_value = mock_resp

        c = CutctxClient()
        result = c.health()
        assert result["status"] == "ok"
