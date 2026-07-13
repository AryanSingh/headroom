import os
from unittest.mock import patch

import keyring
import pytest

from cutctx.proxy.auth_keyring import get_api_key


def test_adversarial_keyring_locked():
    """Verify that if the OS keyring throws an exception (e.g. locked or missing backend),
    the proxy does not crash and gracefully falls back to empty string."""

    with patch.dict(os.environ, clear=True):
        with patch("cutctx.proxy.auth_keyring.keyring.get_password") as mock_get_password:
            # Simulate a locked keyring exception
            mock_get_password.side_effect = Exception("Keyring is locked")

            # The function should catch the exception and return "" safely
            key = get_api_key("openai")
            assert key == ""
            mock_get_password.assert_called_once()


def test_adversarial_keyring_success():
    """Verify end-to-end setting and getting from the actual keyring API."""
    # Note: in CI, keyring might fallback to a dummy backend, which is fine for testing.
    # We set a dummy key, retrieve it, then clean it up.

    test_key = "sk-adversarial-test-key-12345"

    try:
        keyring.set_password("cutctx", "GEMINI_API_KEY", test_key)
    except Exception:
        pytest.skip("No working keyring backend available in this test environment")

    with patch.dict(os.environ, clear=True):
        key = get_api_key("gemini")
        assert key == test_key

    # Cleanup
    try:
        keyring.delete_password("cutctx", "GEMINI_API_KEY")
    except Exception:
        pass
