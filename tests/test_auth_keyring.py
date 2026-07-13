import os
from unittest.mock import MagicMock, patch

import pytest

from cutctx.proxy.auth_keyring import get_api_key, inject_provider_authorization


def test_get_api_key_env_var():
    with patch.dict(os.environ, {"OPENAI_API_KEY": "sk-env-key"}):
        assert get_api_key("openai") == "sk-env-key"


def test_get_api_key_supports_documented_upstream_env_var():
    """The sample env file uses CUTCTX_UPSTREAM_OPENAI_API_KEY."""
    with patch.dict(
        os.environ,
        {"CUTCTX_UPSTREAM_OPENAI_API_KEY": "sk-upstream-key"},
        clear=True,
    ):
        assert get_api_key("openai") == "sk-upstream-key"


def test_standard_provider_env_var_takes_precedence_over_compatibility_alias():
    with patch.dict(
        os.environ,
        {
            "OPENAI_API_KEY": "sk-standard-key",
            "CUTCTX_UPSTREAM_OPENAI_API_KEY": "sk-upstream-key",
        },
        clear=True,
    ):
        assert get_api_key("openai") == "sk-standard-key"


def test_get_api_key_supports_documented_google_alias_for_gemini():
    with patch.dict(
        os.environ,
        {"CUTCTX_UPSTREAM_GOOGLE_API_KEY": "google-upstream-key"},
        clear=True,
    ):
        assert get_api_key("gemini") == "google-upstream-key"


def test_inject_provider_authorization_uses_documented_upstream_key():
    with patch.dict(
        os.environ,
        {"CUTCTX_UPSTREAM_OPENAI_API_KEY": "sk-upstream-key"},
        clear=True,
    ):
        headers: dict[str, str] = {}
        assert inject_provider_authorization(headers, "openai") is True
        assert headers == {"Authorization": "Bearer sk-upstream-key"}


def test_inject_provider_authorization_preserves_client_credential():
    with patch.dict(
        os.environ,
        {"CUTCTX_UPSTREAM_OPENAI_API_KEY": "sk-upstream-key"},
        clear=True,
    ):
        headers = {"authorization": "Bearer client-key"}
        assert inject_provider_authorization(headers, "openai") is False
        assert headers == {"authorization": "Bearer client-key"}

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
