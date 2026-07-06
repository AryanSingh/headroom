import inspect
from unittest.mock import MagicMock, patch

import uvicorn

from cutctx.proxy.models import ProxyConfig
from cutctx.proxy.server import run_server


@patch("uvicorn.run")
def test_uvicorn_run_uses_graceful_shutdown(mock_uvicorn_run):
    """
    Test that the proxy server starts uvicorn with a reasonable timeout_graceful_shutdown.
    This prevents the proxy from dropping active WebSocket agent turns abruptly
    when it receives a termination signal.
    """
    config = ProxyConfig(
        host="127.0.0.1",
        port=8000,
        admin_api_key="test-key",
    )
    
    run_server(config)
    
    mock_uvicorn_run.assert_called_once()
    _, kwargs = mock_uvicorn_run.call_args
    
    # Assert that timeout_graceful_shutdown is explicitly passed and is >= 30 seconds
    assert "timeout_graceful_shutdown" in kwargs, "timeout_graceful_shutdown must be passed to uvicorn.run"
    assert kwargs["timeout_graceful_shutdown"] >= 30, "timeout_graceful_shutdown must be at least 30 seconds for long agent turns"
