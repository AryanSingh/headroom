from __future__ import annotations

import tomllib
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]


def test_enterprise_memory_service_declares_sqlalchemy_runtime_dependency() -> None:
    package = tomllib.loads(
        (ROOT / "packaging" / "cutctx-ee" / "pyproject.toml").read_text(
            encoding="utf-8"
        )
    )
    dependencies = package["project"]["dependencies"]

    assert any(dependency.lower().startswith("sqlalchemy") for dependency in dependencies)
