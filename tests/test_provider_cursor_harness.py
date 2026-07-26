"""Tests for Cursor harness configuration helpers."""

from __future__ import annotations

import json
from pathlib import Path

from cutctx.providers.cursor.config import (
    apply_proxy_config,
    project_config_path,
    revert_proxy_config,
)
from cutctx.providers.cursor.hooks import ensure_project_hooks, project_hooks_path


def test_apply_proxy_config_writes_project_config(tmp_path: Path, monkeypatch) -> None:
    monkeypatch.chdir(tmp_path)
    result = apply_proxy_config(port=8787, project="demo")

    config_path = project_config_path(tmp_path)
    assert config_path.exists()
    payload = json.loads(config_path.read_text(encoding="utf-8"))
    assert payload["openai"]["baseUrl"] == "http://127.0.0.1:8787/p/demo/v1"
    assert payload["anthropic"]["baseUrl"] == "http://127.0.0.1:8787/p/demo"
    assert result.project_config == config_path


def test_ensure_project_hooks_writes_hooks_json(tmp_path: Path, monkeypatch) -> None:
    monkeypatch.chdir(tmp_path)
    path = ensure_project_hooks()

    assert path == project_hooks_path(tmp_path)
    payload = json.loads(path.read_text(encoding="utf-8"))
    assert payload["version"] == 1
    assert "init hook ensure" in payload["hooks"]["sessionStart"][0]["command"]


def test_revert_proxy_config_removes_cutctx_managed_values(tmp_path: Path, monkeypatch) -> None:
    monkeypatch.chdir(tmp_path)
    apply_proxy_config(port=8787, project="demo")

    assert revert_proxy_config() is True
    assert not project_config_path(tmp_path).exists()
