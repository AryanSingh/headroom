"""Tests for Cursor subscription upstream routing helpers."""

from __future__ import annotations

import os

from cutctx.providers.cursor.upstream import (
    DEFAULT_CURSOR_API_URL,
    is_cursor_client,
    resolve_cursor_target_api_url,
    strip_cursor_ide_model_prefix,
)


def test_resolve_cursor_target_api_url_defaults_to_api2() -> None:
    assert resolve_cursor_target_api_url({}) == DEFAULT_CURSOR_API_URL


def test_resolve_cursor_target_api_url_honors_override() -> None:
    url = resolve_cursor_target_api_url({"CURSOR_TARGET_API_URL": "https://cursor.mock/"})
    assert url == "https://cursor.mock"


def test_is_cursor_client_detects_explicit_header() -> None:
    assert is_cursor_client({"x-client": "cursor"}) is True
    assert is_cursor_client({"user-agent": "curl/8.0"}) is False


def test_strip_cursor_ide_model_prefix() -> None:
    model, stripped = strip_cursor_ide_model_prefix("cutctx-gpt-4o")
    assert stripped is True
    assert model == "gpt-4o"

    unchanged, stripped = strip_cursor_ide_model_prefix("gpt-4o")
    assert stripped is False
    assert unchanged == "gpt-4o"


def test_proxy_routes_cursor_passthrough_to_cursor_upstream(monkeypatch) -> None:
    import importlib

    proxy_routes = importlib.import_module("cutctx.providers.proxy_routes")
    proxy = type(
        "Proxy",
        (),
        {
            "ANTHROPIC_API_URL": "https://legacy.anthropic.test",
            "OPENAI_API_URL": "https://legacy.openai.test",
            "provider_runtime": type(
                "Runtime",
                (),
                {
                    "api_target": staticmethod(lambda provider: f"https://runtime.{provider}.test"),
                    "model_metadata_provider": staticmethod(lambda headers: "openai"),
                },
            )(),
        },
    )()

    monkeypatch.delenv("CURSOR_TARGET_API_URL", raising=False)
    assert (
        proxy_routes._select_passthrough_base_url(
            proxy,
            {"x-client": "cursor"},
        )
        == DEFAULT_CURSOR_API_URL
    )

    monkeypatch.setenv("CURSOR_TARGET_API_URL", "https://cursor.mock")
    assert (
        proxy_routes._select_passthrough_base_url(
            proxy,
            {"user-agent": "cursor/1.2.3"},
        )
        == "https://cursor.mock"
    )
