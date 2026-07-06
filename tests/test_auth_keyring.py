import os
from unittest.mock import MagicMock, patch

import pytest

from cutctx.proxy.auth_keyring import get_api_key


def test_get_api_key_env_var():
    with patch.dict(os.environ, {"OPENAI_API_KEY": "sk-env-key"}):
        assert get_api_key("openai") == "sk-env-key"

@patch("cutctx.proxy.auth_keyring.keyring")
def test_get_api_key_keyring_fallback(mock_keyring):
    # Ensure no env var
    with patch.dict(os.environ, clear=True):
        mock_keyring.get_password.return_value = "sk-keyring-key"
        
        key = get_api_key("anthropic")
        
        assert key == "sk-keyring-key"
        mock_keyring.get_password.assert_called_once_with("cutctx", "ANTHROPIC_API_KEY")

@patch("cutctx.proxy.auth_keyring.keyring")
def test_get_api_key_empty(mock_keyring):
    with patch.dict(os.environ, clear=True):
        mock_keyring.get_password.return_value = None
        assert get_api_key("gemini") == ""
