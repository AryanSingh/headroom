"""Contract checks for the operator upgrade and rollback runbook."""

from __future__ import annotations

from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
RUNBOOK = ROOT / "docs" / "spec" / "017-operations.md"


def test_rollback_uses_canonical_registry_and_immutable_release_reference() -> None:
    content = RUNBOOK.read_text(encoding="utf-8")

    assert "ghcr.io/cutctx/cutctx:${PREVIOUS_VERSION}" in content
    assert "cutctx-ai/cutctx:latest" not in content
    assert "docker tag" not in content


def test_runbook_covers_native_rollback_and_post_rollback_verification() -> None:
    content = RUNBOOK.read_text(encoding="utf-8")

    assert 'cutctx-ai[proxy]==${PREVIOUS_VERSION}' in content
    assert "curl --fail" in content
    assert "Do not delete the pre-upgrade backup" in content
