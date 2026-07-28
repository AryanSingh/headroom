from __future__ import annotations

import uuid
from typing import Any

from .agent_packages import AgentPackageRegistry
from .artifact_store import ArtifactBlobStore
from .handoff_ccr import handoff_payload_from_artifacts
from .harness_adapter import HarnessAdapter, HarnessRunContext
from .workflow import TaskSpec


class HarnessRuntime:
    def __init__(
        self,
        *,
        registry: AgentPackageRegistry,
        blob_store: ArtifactBlobStore,
    ) -> None:
        self.registry = registry
        self.blob_store = blob_store
        self._adapters: dict[str, HarnessAdapter] = {}

    def register(self, adapter: HarnessAdapter) -> None:
        self._adapters[adapter.harness_id] = adapter

    def resolve(self, harness_id: str) -> HarnessAdapter:
        try:
            return self._adapters[harness_id]
        except KeyError as exc:
            raise KeyError(f"unknown harness adapter: {harness_id}") from exc

    async def run_task(self, workflow_id: str, task: TaskSpec, *, package_id: str) -> dict[str, Any]:
        package = self.registry.get(package_id)
        adapter = self.resolve(package.harness)
        ctx = HarnessRunContext(
            run_id=uuid.uuid4().hex,
            workflow_id=workflow_id,
            task_id=task.id,
            role=task.role,
            agent_package_id=package.id,
            workspace_ref=str(task.payload.get("workspace_ref", "")),
            prompt=str(task.payload.get("prompt", "")),
            env=dict(task.payload.get("env", {})),
        )
        outcome = await adapter.run(ctx)
        return {
            "harness": package.harness,
            "package_hash": package.package_hash,
            "status": outcome.status,
            "artifacts": [ref.__dict__ for ref in outcome.artifacts],
            "handoff": handoff_payload_from_artifacts(outcome.artifacts),
            "stdout_ref": outcome.stdout_ref,
            "stderr_ref": outcome.stderr_ref,
            "metadata": outcome.metadata,
        }
