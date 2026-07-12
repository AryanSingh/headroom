from __future__ import annotations

import sys
from types import SimpleNamespace

import pytest

from cutctx.client import CutctxClient


def test_from_env_rejects_ambiguous_provider_keys(monkeypatch) -> None:
    monkeypatch.setenv("OPENAI_API_KEY", "openai-key")
    monkeypatch.setenv("ANTHROPIC_API_KEY", "anthropic-key")
    monkeypatch.delenv("CUTCTX_PROVIDER", raising=False)

    with pytest.raises(ValueError, match="Both OPENAI_API_KEY"):
        CutctxClient.from_env()


def test_from_env_requires_selected_provider_key(monkeypatch) -> None:
    monkeypatch.delenv("OPENAI_API_KEY", raising=False)

    with pytest.raises(ValueError, match="OPENAI_API_KEY is required"):
        CutctxClient.from_env(provider="openai")


def test_from_env_constructs_openai_client(monkeypatch, tmp_path) -> None:
    captured: dict[str, str] = {}

    class FakeOpenAI:
        def __init__(self, *, api_key: str) -> None:
            captured["api_key"] = api_key

    monkeypatch.setenv("OPENAI_API_KEY", "openai-key")
    monkeypatch.setitem(sys.modules, "openai", SimpleNamespace(OpenAI=FakeOpenAI))
    client = CutctxClient.from_env(store_url=f"sqlite:///{tmp_path / 'client.db'}")

    assert captured["api_key"] == "openai-key"
    assert client._provider.name == "openai"
