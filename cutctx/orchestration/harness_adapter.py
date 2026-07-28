from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Protocol


@dataclass(frozen=True)
class ArtifactRef:
    blob_id: str
    media_type: str = "application/octet-stream"
    byte_size: int = 0
    ccr_hash: str = ""
    provenance: dict[str, str] = field(default_factory=dict)


@dataclass(frozen=True)
class HarnessCapabilities:
    stream: bool = False
    cancel: bool = True
    resume: bool = False
    artifact_emit: bool = True


@dataclass
class HarnessRunContext:
    run_id: str
    workflow_id: str
    task_id: str
    role: str
    agent_package_id: str
    workspace_ref: str
    input_artifacts: list[ArtifactRef] = field(default_factory=list)
    prompt: str = ""
    env: dict[str, str] = field(default_factory=dict)


@dataclass
class HarnessRunResult:
    status: str
    artifacts: list[ArtifactRef] = field(default_factory=list)
    stdout_ref: str = ""
    stderr_ref: str = ""
    metadata: dict[str, str] = field(default_factory=dict)


class HarnessAdapter(Protocol):
    harness_id: str

    def capabilities(self) -> HarnessCapabilities: ...

    async def health(self) -> dict[str, Any]: ...

    async def run(self, ctx: HarnessRunContext) -> HarnessRunResult: ...

    async def cancel(self, run_id: str) -> None: ...
