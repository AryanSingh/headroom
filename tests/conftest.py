"""Shared pytest fixtures for Cutctx tests."""

# CRITICAL: Must be set before ANY imports that could trigger sentence_transformers
# The Rust tokenizers use parallelism that deadlocks with pytest-asyncio
import os

os.environ["TOKENIZERS_PARALLELISM"] = "false"
os.environ["CUTCTX_CCR_BACKEND"] = "memory"
# Secure-by-default: tests need a known admin key for admin endpoints.
# The test mode bypass (CUTCTX_TEST_MODE) has been REMOVED as a security
# hardening measure. Tests authenticate via this key instead.
os.environ.setdefault("CUTCTX_ADMIN_API_KEY", "test-admin-key-for-ci")


import json
import tempfile
from datetime import datetime
from pathlib import Path
from unittest.mock import Mock

import pytest

# Import httpx for timeout handling (will be available since it's a dependency)
try:
    import httpx

    HTTPX_AVAILABLE = True
except ImportError:
    HTTPX_AVAILABLE = False


# =============================================================================
# Global test hooks
# =============================================================================


@pytest.hookimpl(hookwrapper=True)
def pytest_runtest_call(item):
    """Wrap test execution to catch httpx.ReadTimeout and skip instead of fail.

    This handles flaky network timeouts that occur when:
    - HuggingFace Hub is slow during model downloads (sentence-transformers)
    - External embedding APIs timeout
    - Network connectivity issues in CI
    """
    outcome = yield

    if HTTPX_AVAILABLE and outcome.excinfo is not None:
        exc_type, exc_value, exc_tb = outcome.excinfo
        if isinstance(exc_value, httpx.ReadTimeout):
            pytest.skip("Skipped due to network timeout (flaky CI)")


@pytest.fixture(autouse=True)
def _auto_admin_auth_header(request):
    """Auto-inject admin auth header into all httpx requests during tests.

    Since we removed CUTCTX_TEST_MODE bypass for security, tests now need
    to authenticate with the admin key. Rather than modifying hundreds of
    individual test files, this fixture patches httpx to automatically include
    the Authorization header when none is provided.

    Tests that deliberately test unauthenticated access can mark themselves
    with ``@pytest.mark.no_auto_admin`` to skip this injection.
    """
    import httpx

    # Allow individual tests to opt out (e.g., tests that verify 401 behavior)
    if request.node.get_closest_marker("no_auto_admin"):
        yield
        return

    _admin_key = os.environ.get("CUTCTX_ADMIN_API_KEY", "")
    if not _admin_key:
        yield
        return

    _auth_header = f"Bearer {_admin_key}"

    # Patch AsyncClient to auto-inject admin header
    _orig_async_init = httpx.AsyncClient.__init__

    def _patched_async_init(self, *args, **kwargs):
        headers = kwargs.get("headers")
        if headers is None:
            kwargs["headers"] = {"Authorization": _auth_header}
        elif isinstance(headers, dict):
            headers.setdefault("Authorization", _auth_header)
        elif isinstance(headers, list):
            has_auth = any(k.lower() == "authorization" for k, _ in headers)
            if not has_auth:
                headers.append(("Authorization", _auth_header))
        return _orig_async_init(self, *args, **kwargs)

    # Patch sync Client (used by TestClient) to auto-inject admin header
    _orig_sync_init = httpx.Client.__init__

    def _patched_sync_init(self, *args, **kwargs):
        headers = kwargs.get("headers")
        if headers is None:
            kwargs["headers"] = {"Authorization": _auth_header}
        elif isinstance(headers, dict):
            headers.setdefault("Authorization", _auth_header)
        elif isinstance(headers, list):
            has_auth = any(k.lower() == "authorization" for k, _ in headers)
            if not has_auth:
                headers.append(("Authorization", _auth_header))
        return _orig_sync_init(self, *args, **kwargs)

    httpx.AsyncClient.__init__ = _patched_async_init
    httpx.Client.__init__ = _patched_sync_init
    yield
    httpx.AsyncClient.__init__ = _orig_async_init
    httpx.Client.__init__ = _orig_sync_init


@pytest.fixture(autouse=True)
def _reset_cutctx_logger_propagation():
    """Keep `cutctx.*` log records flowing to pytest's caplog handler.

    `cutctx.proxy.helpers._setup_file_logging` sets
    ``logging.getLogger("cutctx").propagate = False`` once any test
    triggers a proxy startup with `--log-file`. After that, every
    subsequent test's `caplog` fixture stops capturing `cutctx.*`
    log records (caplog attaches to root, propagation is now blocked
    at the cutctx-logger boundary). Reset before every test so the
    capture is deterministic regardless of run order.
    """
    import logging as _logging

    _logging.getLogger("cutctx").propagate = True
    yield


@pytest.fixture(autouse=True)
def _isolated_ccr_db(tmp_path):
    """Isolate the CCR database to a temporary directory for each test."""
    db_path = tmp_path / "ccr.db"
    os.environ["CUTCTX_CCR_DB_PATH"] = str(db_path)
    yield


# =============================================================================
# Sample messages fixtures
# =============================================================================


# Sample messages fixtures
@pytest.fixture
def sample_messages():
    """Basic conversation messages."""
    return [
        {"role": "system", "content": "You are a helpful assistant."},
        {"role": "user", "content": "Hello, how are you?"},
        {"role": "assistant", "content": "I'm doing well, thank you!"},
    ]


@pytest.fixture
def sample_messages_with_tools():
    """Conversation with tool calls and responses."""
    return [
        {"role": "system", "content": "You are a helpful assistant with tools."},
        {"role": "user", "content": "Search for user 12345"},
        {
            "role": "assistant",
            "content": None,
            "tool_calls": [
                {
                    "id": "call_123",
                    "type": "function",
                    "function": {"name": "search_user", "arguments": '{"user_id": "12345"}'},
                }
            ],
        },
        {
            "role": "tool",
            "tool_call_id": "call_123",
            "content": '{"id": "12345", "name": "Alice", "email": "alice@example.com"}',
        },
        {"role": "assistant", "content": "I found user Alice with ID 12345."},
    ]


@pytest.fixture
def sample_tool_output_large():
    """Large tool output for compression testing (100 items)."""
    return json.dumps(
        [
            {
                "id": i,
                "name": f"Item {i}",
                "score": i * 0.1,
                "status": "active" if i % 2 == 0 else "inactive",
            }
            for i in range(100)
        ]
    )


@pytest.fixture
def sample_tool_output_with_errors():
    """Tool output containing error items."""
    items = [{"id": i, "status": "success"} for i in range(20)]
    items[5] = {"id": 5, "status": "error", "message": "Connection refused"}
    items[15] = {"id": 15, "status": "failed", "exception": "TimeoutError"}
    return json.dumps(items)


@pytest.fixture
def sample_system_prompt_with_date():
    """System prompt containing dynamic date."""
    return "You are a helpful assistant. Current date: 2025-01-06. Help the user with their tasks."


@pytest.fixture
def sample_anthropic_messages():
    """Anthropic-style messages with content blocks."""
    return [
        {
            "role": "user",
            "content": [
                {"type": "text", "text": "Analyze this image"},
                {
                    "type": "image",
                    "source": {"type": "base64", "media_type": "image/png", "data": "..."},
                },
            ],
        }
    ]


# Mock client fixtures
@pytest.fixture
def mock_openai_response():
    """Mock OpenAI API response."""
    mock = Mock()
    mock.id = "chatcmpl-123"
    mock.model = "gpt-4o"
    mock.usage = Mock()
    mock.usage.prompt_tokens = 100
    mock.usage.completion_tokens = 50
    mock.usage.total_tokens = 150
    mock.choices = [Mock()]
    mock.choices[0].message = Mock()
    mock.choices[0].message.content = "This is a response."
    mock.choices[0].message.role = "assistant"
    mock.choices[0].finish_reason = "stop"
    return mock


@pytest.fixture
def mock_openai_client(mock_openai_response):
    """Mock OpenAI client."""
    client = Mock()
    client.chat = Mock()
    client.chat.completions = Mock()
    client.chat.completions.create = Mock(return_value=mock_openai_response)
    return client


# Storage fixtures
@pytest.fixture
def temp_sqlite_db():
    """Temporary SQLite database path."""
    with tempfile.NamedTemporaryFile(suffix=".db", delete=False) as f:
        yield f.name
    Path(f.name).unlink(missing_ok=True)


@pytest.fixture
def temp_jsonl_file():
    """Temporary JSONL file path."""
    with tempfile.NamedTemporaryFile(suffix=".jsonl", delete=False) as f:
        yield f.name
    Path(f.name).unlink(missing_ok=True)


# Provider fixtures
@pytest.fixture
def openai_provider():
    """OpenAI provider instance."""
    from cutctx.providers.openai import OpenAIProvider

    return OpenAIProvider()


@pytest.fixture
def openai_tokenizer():
    """OpenAI token counter for gpt-4o."""
    from cutctx.providers.openai import OpenAITokenCounter

    return OpenAITokenCounter("gpt-4o")


# Config fixtures
@pytest.fixture
def default_config():
    """Default CutctxConfig."""
    from cutctx.config import CutctxConfig

    return CutctxConfig()


@pytest.fixture
def smart_crusher_config():
    """SmartCrusher config for testing."""
    from cutctx.config import SmartCrusherConfig

    return SmartCrusherConfig(
        enabled=True,
        min_items_to_analyze=3,
        min_tokens_to_crush=0,  # Always crush for tests
        max_items_after_crush=10,
    )


# Helper for creating RequestMetrics
@pytest.fixture
def sample_request_metrics():
    """Sample RequestMetrics for storage tests."""
    from cutctx.config import RequestMetrics

    return RequestMetrics(
        request_id="test-123",
        timestamp=datetime(2025, 1, 6, 12, 0, 0),
        model="gpt-4o",
        stream=False,
        mode="audit",
        tokens_input_before=1000,
        tokens_input_after=800,
        tokens_output=200,
        block_breakdown={"system": 100, "user": 200, "assistant": 500},
        waste_signals={"json_bloat": 50},
        stable_prefix_hash="abc123",
        cache_alignment_score=85.0,
        cached_tokens=100,
        transforms_applied=["CacheAligner", "SmartCrusher"],
        tool_units_dropped=1,
        turns_dropped=0,
        messages_hash="def456",
    )
