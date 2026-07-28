from __future__ import annotations

import stat
from pathlib import Path

import pytest

from cutctx.orchestration.adapters.codex_cli import CodexCliAdapter
from cutctx.orchestration.artifact_store import ArtifactBlobStore
from cutctx.orchestration.harness_adapter import HarnessRunContext


@pytest.mark.asyncio
async def test_codex_adapter_emits_patch_artifact(tmp_path) -> None:
    fake = tmp_path / "fake_codex"
    fake.write_text(
        Path("tests/fixtures/fake_codex_cli.py").read_text(encoding="utf-8"), encoding="utf-8"
    )
    fake.chmod(fake.stat().st_mode | stat.S_IXUSR)
    blobs = ArtifactBlobStore(tmp_path / "artifacts")
    adapter = CodexCliAdapter(blob_store=blobs, binary=str(fake))
    ctx = HarnessRunContext(
        run_id="run-1",
        workflow_id="wf-1",
        task_id="implement",
        role="implementer",
        agent_package_id="implementer-codex",
        workspace_ref=str(tmp_path),
        prompt="make a patch",
    )
    result = await adapter.run(ctx)
    assert result.status == "completed"
    assert result.artifacts
    patch = blobs.get(result.artifacts[0].blob_id).decode("utf-8")
    assert patch.startswith("diff --git")
