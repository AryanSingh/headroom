from __future__ import annotations

import pytest

from cutctx.orchestration.agent_packages import AgentPackageRegistry
from cutctx.orchestration.artifact_store import ArtifactBlobStore
from cutctx.orchestration.harness_runtime import HarnessRuntime


@pytest.mark.asyncio
async def test_runtime_resolves_package_and_runs_adapter(tmp_path, monkeypatch) -> None:
    from cutctx.orchestration.adapters.codex_cli import CodexCliAdapter
    from tests.fixtures import fake_codex_cli  # noqa: F401 — ensures fixture exists

    fake = tmp_path / "fake_codex"
    fake.write_text(
        open("tests/fixtures/fake_codex_cli.py", encoding="utf-8").read(), encoding="utf-8"
    )
    fake.chmod(0o755)
    registry = AgentPackageRegistry(tmp_path / "agents")
    registry.put(open(".cutctx/agents/example-implementer.yaml", encoding="utf-8").read())
    blobs = ArtifactBlobStore(tmp_path / "artifacts")
    runtime = HarnessRuntime(registry=registry, blob_store=blobs)
    runtime.register(CodexCliAdapter(blob_store=blobs, binary=str(fake)))
    from cutctx.orchestration.workflow import TaskSpec

    task = TaskSpec(
        id="implement",
        role="implementer",
        payload={
            "harness": "codex_cli",
            "agent_package_id": "implementer-codex",
            "prompt": "patch",
        },
    )
    result = await runtime.run_task("wf-1", task, package_id="implementer-codex")
    assert result["status"] == "completed"
    assert result["artifacts"]
