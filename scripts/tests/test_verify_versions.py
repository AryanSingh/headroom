"""Tests for the release version verification gate."""

from __future__ import annotations

import importlib.util
import json
from pathlib import Path

import pytest


def _load_module():
    script = Path(__file__).parent.parent / "verify-versions.py"
    spec = importlib.util.spec_from_file_location("verify_versions", script)
    assert spec and spec.loader
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def _write_json(path: Path, payload: dict) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload), encoding="utf-8")


def _version_tree(root: Path, version: str) -> None:
    (root / "pyproject.toml").write_text(f'[project]\nversion = "{version}"\n', encoding="utf-8")
    cargo = root / "crates" / "cutctx-py" / "Cargo.toml"
    cargo.parent.mkdir(parents=True)
    cargo.write_text(f'[package]\nname = "cutctx-py"\nversion = "{version}"\n', encoding="utf-8")
    (root / "Cargo.lock").write_text(
        f'version = 4\n\n[[package]]\nname = "cutctx-py"\nversion = "{version}"\n',
        encoding="utf-8",
    )
    _write_json(
        root / "plugins" / "openclaw" / "package.json",
        {"version": version, "dependencies": {"cutctx-ai": f"^{version}"}},
    )
    _write_json(root / "sdk" / "typescript" / "package.json", {"version": version})
    for path in (
        root / "plugins" / "cutctx-agent-hooks" / ".claude-plugin" / "plugin.json",
        root / "plugins" / "cutctx-agent-hooks" / ".github" / "plugin" / "plugin.json",
    ):
        _write_json(path, {"version": version})
    for path in (
        root / ".claude-plugin" / "marketplace.json",
        root / ".github" / "plugin" / "marketplace.json",
    ):
        _write_json(
            path,
            {"metadata": {"version": version}, "plugins": [{"version": version}]},
        )
    chart = root / "helm" / "cutctx" / "Chart.yaml"
    chart.parent.mkdir(parents=True)
    chart.write_text(
        f'apiVersion: v2\nversion: {version}\nappVersion: "{version}"\n', encoding="utf-8"
    )
    (chart.parent / "values.yaml").write_text(f'image:\n  tag: "{version}"\n', encoding="utf-8")
    deployment = root / "k8s" / "deployment.yaml"
    deployment.parent.mkdir(parents=True)
    deployment.write_text(f"image: ghcr.io/cutctx/cutctx:v{version}\n", encoding="utf-8")


def test_deployment_manifest_drift_fails_version_gate(tmp_path: Path, monkeypatch) -> None:
    root = tmp_path / "project"
    root.mkdir()
    _version_tree(root, "1.2.3")
    module = _load_module()
    monkeypatch.setattr(module, "ROOT", root)

    module.main()
    (root / "helm" / "cutctx" / "values.yaml").write_text(
        'image:\n  tag: "1.2.2"\n', encoding="utf-8"
    )

    with pytest.raises(SystemExit):
        module.main()

    (root / "helm" / "cutctx" / "values.yaml").write_text(
        'image:\n  tag: "1.2.3"\n', encoding="utf-8"
    )
    (root / "Cargo.lock").write_text(
        'version = 4\n\n[[package]]\nname = "cutctx-py"\nversion = "1.2.2"\n',
        encoding="utf-8",
    )

    with pytest.raises(SystemExit):
        module.main()
