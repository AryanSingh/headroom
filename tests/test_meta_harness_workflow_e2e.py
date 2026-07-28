from __future__ import annotations

import json
from collections.abc import AsyncIterator
from pathlib import Path
from typing import Any

import pytest

from cutctx.orchestration.agent_packages import AgentPackageRegistry
from cutctx.orchestration.config import LayeredConfigStore
from cutctx.orchestration.credentials import EncryptedCredentialStore
from cutctx.orchestration.models import (
    Capability,
    ModelRecord,
    OrchestrationConfig,
    ProviderAccount,
    Role,
    RouteBinding,
    RoutingSettings,
)
from cutctx.orchestration.providers import ProviderAdapterRegistry, ProviderHealth, ProviderSpec
from cutctx.orchestration.registry import DynamicModelRegistry
from cutctx.orchestration.service import OrchestrationService
from cutctx.orchestration.telemetry import ExecutionTelemetryStore
from cutctx.orchestration.workflow import TaskSpec, WorkflowSpec, WorkflowStateStore


class _FakeAdapter:
    def __init__(
        self,
        spec: ProviderSpec,
        account: ProviderAccount,
        credential: dict[str, Any] | None,
        behavior: dict[str, Any],
    ) -> None:
        self.spec = spec
        self.account = account
        self.credential = credential
        self.behavior = behavior

    async def authenticate(self) -> ProviderHealth:
        return ProviderHealth(True, "healthy", 1.0)

    async def health(self) -> ProviderHealth:
        return await self.authenticate()

    async def list_models(self) -> list[ModelRecord]:
        return await self.refresh_models()

    async def refresh_models(self) -> list[ModelRecord]:
        return [
            ModelRecord(
                provider=self.account.provider,
                id="gpt-5.4-mini",
                account_id=self.account.id,
                capabilities={Capability.STREAMING.value, Capability.TOOL_CALLING.value},
            )
        ]

    async def invoke(self, request: dict[str, Any]) -> dict[str, Any]:
        return self.behavior[self.account.provider]

    async def stream(self, request: dict[str, Any]) -> AsyncIterator[bytes]:
        yield b"ok"


def _service(tmp_path: Path) -> OrchestrationService:
    providers = ProviderAdapterRegistry()
    behavior = {"openai": {"content": [{"text": "planned"}], "usage": {"input_tokens": 1}}}
    for provider in behavior:
        spec = ProviderSpec(provider, provider.title())
        providers.register(
            spec,
            lambda spec, account, credential, behavior=behavior: _FakeAdapter(
                spec, account, credential, behavior
            ),
        )
    config_path = tmp_path / "orchestration.json"
    service = OrchestrationService(
        config_store=LayeredConfigStore({"project": config_path}),
        credential_store=EncryptedCredentialStore(tmp_path / "state" / "credentials.enc"),
        model_registry=DynamicModelRegistry(tmp_path / "state" / "models.json"),
        provider_registry=providers,
        telemetry=ExecutionTelemetryStore(),
        workflow_store=WorkflowStateStore(tmp_path / "state" / "workflows.json"),
    )
    service.model_registry.register(
        ModelRecord(
            provider="openai",
            id="gpt-5.4-mini",
            account_id="openai-main",
            capabilities={Capability.STREAMING.value, Capability.TOOL_CALLING.value},
        )
    )
    service.replace_config(
        OrchestrationConfig(
            providers=[ProviderAccount(id="openai-main", provider="openai")],
            roles=[
                Role(id="planner", name="Planner"),
                Role(id="reviewer", name="Reviewer"),
            ],
            bindings=[
                RouteBinding(id="planner-mini", role="planner", model="openai:gpt-5.4-mini"),
                RouteBinding(id="reviewer-mini", role="reviewer", model="openai:gpt-5.4-mini"),
            ],
            settings=RoutingSettings(mode="relaxed", retries=0),
        )
    )
    return service


@pytest.mark.asyncio
async def test_planner_codex_implementer_reviewer_handoff(tmp_path, monkeypatch) -> None:
    orch_dir = tmp_path / "state"
    monkeypatch.setenv("CUTCTX_ORCHESTRATION_DIR", str(orch_dir))
    monkeypatch.setenv("CUTCTX_AGENT_PACKAGES_DIR", str(tmp_path / "agents"))
    AgentPackageRegistry(tmp_path / "agents").put(
        Path(".cutctx/agents/example-implementer.yaml").read_text(encoding="utf-8")
    )
    fake = tmp_path / "fake_codex"
    fake.write_text(Path("tests/fixtures/fake_codex_cli.py").read_text(encoding="utf-8"), encoding="utf-8")
    fake.chmod(0o755)
    monkeypatch.setenv("CUTCTX_CODEX_CLI_BIN", str(fake))

    service = _service(tmp_path)
    store = WorkflowStateStore(orch_dir / "workflows.json")
    spec = WorkflowSpec(
        id="sdlc",
        tasks=[
            TaskSpec(
                id="plan",
                role="planner",
                payload={
                    "messages": [{"role": "user", "content": "plan"}],
                    "parameters": {},
                },
            ),
            TaskSpec(
                id="implement",
                role="implementer",
                depends_on=["plan"],
                payload={
                    "harness": "codex_cli",
                    "agent_package_id": "implementer-codex",
                    "prompt": "patch",
                    "workspace_ref": str(tmp_path),
                },
            ),
            TaskSpec(
                id="review",
                role="reviewer",
                depends_on=["implement"],
                payload={
                    "messages": [{"role": "user", "content": "review patch refs only"}],
                    "parameters": {},
                    "artifact_refs": [],
                },
            ),
        ],
    )
    workflow = store.submit(spec)

    state = await service.run_workflow(store, workflow.id, spec)

    assert state.status == "completed"
    implement = state.tasks["implement"].result
    assert implement is not None
    assert implement["artifacts"]
    assert implement["handoff"]["artifact_refs"]
    assert implement["handoff"]["artifact_refs"][0]["ccr_hash"]
    review = state.tasks["review"].result
    assert review is not None
