from __future__ import annotations

import pytest

from cutctx.proxy.handlers.openai.responses import (
    _get_chatgpt_responses_http_url,
    _set_test_chatgpt_responses_endpoints,
)


def test_test_upstream_override_accepts_loopback_only() -> None:
    try:
        _set_test_chatgpt_responses_endpoints(
            http_url="http://127.0.0.1:9876/backend-api/codex/responses",
            ws_url="ws://localhost:9876/backend-api/codex/responses",
        )
        assert _get_chatgpt_responses_http_url().startswith("http://127.0.0.1:9876/")
    finally:
        _set_test_chatgpt_responses_endpoints(http_url=None, ws_url=None)


def test_test_upstream_override_rejects_non_loopback() -> None:
    with pytest.raises(ValueError, match="loopback"):
        _set_test_chatgpt_responses_endpoints(
            http_url="https://attacker.example/responses",
            ws_url=None,
        )
