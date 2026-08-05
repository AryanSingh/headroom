from __future__ import annotations

from pathlib import Path

import tomllib

ROOT = Path(__file__).resolve().parents[1]


def test_mcp_dependency_excludes_breaking_v2_api() -> None:
    project = tomllib.loads((ROOT / "pyproject.toml").read_text(encoding="utf-8"))["project"]
    runtime_spec = next(
        dependency for dependency in project["dependencies"] if dependency.startswith("mcp")
    )
    extra_spec = next(
        dependency
        for dependency in project["optional-dependencies"]["mcp"]
        if dependency.startswith("mcp")
    )

    assert ">=1.27.2" in runtime_spec
    assert "<2.0.0" in runtime_spec
    assert extra_spec == runtime_spec
