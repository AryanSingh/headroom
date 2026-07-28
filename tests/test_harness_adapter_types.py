from __future__ import annotations

import pytest

from cutctx.orchestration.harness_adapter import (
    ArtifactRef,
    HarnessCapabilities,
    HarnessRunContext,
    HarnessRunResult,
)


def test_artifact_ref_defaults() -> None:
    ref = ArtifactRef(blob_id="abc123")
    assert ref.media_type == "application/octet-stream"
    assert ref.byte_size == 0
    assert ref.ccr_hash == ""
    assert ref.provenance == {}


def test_harness_capabilities_defaults() -> None:
    caps = HarnessCapabilities()
    assert caps.stream is False
    assert caps.cancel is True
    assert caps.resume is False
    assert caps.artifact_emit is True


def test_harness_run_context_carries_explicit_artifacts() -> None:
    parent = ArtifactRef(blob_id="plan_blob", media_type="text/plain", byte_size=12)
    ctx = HarnessRunContext(
        run_id="run-1",
        workflow_id="wf-1",
        task_id="implement",
        role="implementer",
        agent_package_id="implementer-codex",
        workspace_ref="/tmp/repo",
        input_artifacts=[parent],
        prompt="Apply the plan as a patch.",
        env={"CUTCTX_PROXY_URL": "http://127.0.0.1:8787"},
    )
    assert ctx.input_artifacts[0].blob_id == "plan_blob"


def test_harness_run_result_requires_terminal_status() -> None:
    result = HarnessRunResult(status="completed", artifacts=[])
    assert result.status == "completed"
    assert result.stdout_ref == ""
