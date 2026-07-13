"""Authenticated orchestration configuration, discovery, routing, and execution APIs."""

from __future__ import annotations

import os
from collections.abc import AsyncIterator, Callable
from dataclasses import asdict
from typing import Any

from fastapi import APIRouter, Depends, HTTPException, Response
from fastapi.responses import JSONResponse, StreamingResponse
from pydantic import BaseModel, ConfigDict, Field

from cutctx.orchestration.engine import RoutingUnavailableError
from cutctx.orchestration.harnesses import compatibility_manifest
from cutctx.orchestration.models import RoutingRequest, to_dict
from cutctx.orchestration.scheduler import (
    SchedulerGuardrails,
    detect_quality_drift,
    recommend_schedule,
)
from cutctx.orchestration.service import OrchestrationService
from cutctx.orchestration.workflow import (
    TaskArtifact,
    TaskSpec,
    WorkflowConflictError,
    WorkflowSpec,
    WorkflowValidationError,
)


class RoutingPayload(BaseModel):
    model_config = ConfigDict(extra="forbid")

    role: str | None = None
    profile: str | None = None
    task_type: str | None = None
    model: str | None = None
    requested_model: str | None = None
    provider: str | None = None
    requested_provider: str | None = None
    required_capabilities: list[str] = Field(default_factory=list)
    selectors: dict[str, str] = Field(default_factory=dict)
    mode: str | None = None
    policy: str | None = None
    request_id: str = ""
    allowed_providers: list[str] = Field(default_factory=list)
    allowed_regions: list[str] = Field(default_factory=list)
    allowed_data_classifications: list[str] = Field(default_factory=list)
    data_classification: str | None = None
    estimated_input_tokens: int | None = Field(default=None, ge=0)
    estimated_output_tokens: int | None = Field(default=None, ge=0)
    max_cost_usd: float | None = Field(default=None, ge=0)


class ExecutionPayload(RoutingPayload):
    messages: list[dict[str, Any]] = Field(default_factory=list)
    parameters: dict[str, Any] = Field(default_factory=dict)
    stream: bool = False


class ShadowRoutingPayload(RoutingPayload):
    """A no-call route comparison with one optional candidate override."""

    candidate_profile: str | None = None
    candidate_policy: str | None = None
    candidate_model: str | None = None


class SchedulerRecommendationPayload(RoutingPayload):
    min_observations: int = Field(default=5, ge=1, le=10_000)
    min_quality_score: float = Field(default=0.8, ge=0, le=1)
    canary_sample_rate: float = Field(default=0, ge=0, le=1)


class DriftDetectionPayload(BaseModel):
    model_config = ConfigDict(extra="forbid")

    task_type: str = Field(min_length=1)
    window_size: int = Field(default=10, ge=1, le=500)
    max_quality_drop: float = Field(default=0.15, ge=0, le=1)


class WorkflowTaskPayload(BaseModel):
    model_config = ConfigDict(extra="forbid")

    id: str = Field(min_length=1)
    role: str = Field(min_length=1)
    depends_on: list[str] = Field(default_factory=list)
    messages: list[dict[str, Any]] = Field(default_factory=list)
    parameters: dict[str, Any] = Field(default_factory=dict)
    max_attempts: int = Field(default=3, ge=1, le=10)
    retry_delay_seconds: float = Field(default=0.25, ge=0, le=60)
    timeout_seconds: float | None = Field(default=None, gt=0, le=3600)
    artifact: dict[str, Any] = Field(default_factory=dict)
    requires_approval: bool = False
    requires_verification: bool = False


class WorkflowPayload(BaseModel):
    model_config = ConfigDict(extra="forbid")

    id: str = Field(min_length=1)
    idempotency_key: str = Field(default="", max_length=256)
    tasks: list[WorkflowTaskPayload] = Field(min_length=1, max_length=128)


def _workflow_spec(payload: WorkflowPayload) -> WorkflowSpec:
    def artifact_for(task: WorkflowTaskPayload) -> TaskArtifact:
        try:
            return TaskArtifact(**task.artifact)
        except TypeError as exc:
            raise WorkflowValidationError(f"Invalid task artifact for {task.id!r}: {exc}") from exc

    return WorkflowSpec(
        id=payload.id,
        idempotency_key=payload.idempotency_key,
        tasks=[
            TaskSpec(
                id=task.id,
                role=task.role,
                depends_on=task.depends_on,
                payload={"messages": task.messages, "parameters": task.parameters},
                max_attempts=task.max_attempts,
                retry_delay_seconds=task.retry_delay_seconds,
                timeout_seconds=task.timeout_seconds,
                artifact=artifact_for(task),
                requires_approval=task.requires_approval,
                requires_verification=task.requires_verification,
            )
            for task in payload.tasks
        ],
    )


def _request(payload: RoutingPayload) -> RoutingRequest:
    return RoutingRequest(
        profile=payload.profile,
        task_type=payload.task_type,
        role=payload.role,
        requested_model=payload.model or payload.requested_model,
        requested_provider=payload.provider or payload.requested_provider,
        required_capabilities=set(payload.required_capabilities),
        selectors=dict(payload.selectors),
        mode=payload.mode,
        policy=payload.policy,
        request_id=payload.request_id,
        allowed_providers=set(payload.allowed_providers),
        allowed_regions=set(payload.allowed_regions),
        allowed_data_classifications=set(payload.allowed_data_classifications),
        data_classification=payload.data_classification,
        estimated_input_tokens=payload.estimated_input_tokens,
        estimated_output_tokens=payload.estimated_output_tokens,
        max_cost_usd=payload.max_cost_usd,
    )


def create_orchestration_router(
    service: OrchestrationService,
    require_admin_auth: Callable[..., Any] | None = None,
    require_rbac_permission: Callable[..., Any] | None = None,
    enable_direct_execution: bool | None = None,
) -> APIRouter:
    router = APIRouter(prefix="/v1/orchestration", tags=["orchestration"])
    read_deps: list[Any] = []
    write_deps: list[Any] = []
    if require_admin_auth is not None:
        read_deps.append(Depends(require_admin_auth))
        write_deps.append(Depends(require_admin_auth))
    if require_rbac_permission is not None:
        read_deps.append(Depends(require_rbac_permission("providers.read")))
        write_deps.append(Depends(require_rbac_permission("providers.write")))
    direct_execution_enabled = (
        enable_direct_execution
        if enable_direct_execution is not None
        else os.environ.get("CUTCTX_ORCHESTRATION_DIRECT_EXECUTION", "").strip().lower()
        in {"1", "true", "yes", "on"}
    )

    @router.get("/config", dependencies=read_deps)
    async def get_config() -> dict[str, Any]:
        return service.public_config()

    @router.put("/config", dependencies=write_deps)
    async def put_config(payload: dict[str, Any]) -> dict[str, Any]:
        layer = str(payload.pop("layer", "project"))
        try:
            service.replace_config(payload, layer=layer)
            return service.public_config()
        except (TypeError, ValueError) as exc:
            raise HTTPException(status_code=400, detail=str(exc)) from exc

    @router.get("/providers", dependencies=read_deps)
    async def providers() -> dict[str, Any]:
        return {"catalog": service.provider_specs(), "accounts": service.accounts()}

    @router.put("/providers/{account_id}", dependencies=write_deps)
    async def put_provider(account_id: str, payload: dict[str, Any]) -> dict[str, Any]:
        layer = str(payload.pop("layer", "user"))
        try:
            return service.put_account(account_id, payload, layer=layer)
        except KeyError as exc:
            raise HTTPException(status_code=404, detail=str(exc)) from exc
        except (TypeError, ValueError) as exc:
            raise HTTPException(status_code=400, detail=str(exc)) from exc

    @router.put("/providers/{account_id}/credential", dependencies=write_deps)
    async def put_credential(account_id: str, payload: dict[str, Any]) -> dict[str, Any]:
        layer = str(payload.pop("layer", "user"))
        try:
            reference = service.put_credential(account_id, payload, layer=layer)
        except KeyError as exc:
            raise HTTPException(status_code=404, detail=str(exc)) from exc
        except (TypeError, ValueError) as exc:
            raise HTTPException(status_code=400, detail=str(exc)) from exc
        return {"account_id": account_id, "credential_ref": reference, "stored": True}

    @router.delete("/providers/{account_id}/credential", dependencies=write_deps)
    async def delete_credential(account_id: str) -> dict[str, Any]:
        try:
            deleted = service.delete_credential(account_id)
        except KeyError as exc:
            raise HTTPException(status_code=404, detail=str(exc)) from exc
        return {"account_id": account_id, "deleted": deleted}

    @router.post("/providers/{account_id}/test", dependencies=write_deps)
    async def test_provider(account_id: str) -> dict[str, Any]:
        try:
            return await service.test_account(account_id)
        except KeyError as exc:
            raise HTTPException(status_code=404, detail=str(exc)) from exc

    @router.get("/models", dependencies=read_deps)
    async def list_models(
        provider: str | None = None,
        capability: str | None = None,
        available_only: bool = False,
    ) -> dict[str, Any]:
        required = {capability} if capability else set()
        models = service.model_registry.list(
            provider=provider,
            required_capabilities=required,
            available_only=available_only,
        )
        enabled_accounts = {
            (account.provider, account.id)
            for account in service.config.providers
            if account.enabled
        }

        def executable(model: Any) -> bool:
            if model.account_id:
                return (model.provider, model.account_id) in enabled_accounts
            return any(provider == model.provider for provider, _ in enabled_accounts)

        return {
            "models": [
                to_dict(model)
                | {
                    "key": model.key,
                    "deployment_key": model.deployment_key,
                    "executable": executable(model),
                }
                for model in models
            ]
        }

    @router.get("/capability-manifest", dependencies=read_deps)
    async def capability_manifest() -> dict[str, Any]:
        return service.capability_manifest()

    @router.get("/profiles", dependencies=read_deps)
    async def profiles() -> dict[str, Any]:
        return {"profiles": service.routing_profiles()}

    @router.get("/harness-compatibility", dependencies=read_deps)
    async def harness_compatibility() -> dict[str, Any]:
        return compatibility_manifest()

    @router.get("/policy-bundle", dependencies=read_deps)
    async def policy_bundle() -> dict[str, Any]:
        return service.policy_bundle()

    @router.get("/receipt-audit/verify", dependencies=read_deps)
    async def verify_receipt_audit() -> dict[str, Any]:
        if service.receipt_audit is None:
            raise HTTPException(status_code=501, detail="Receipt audit is not configured")
        return {"valid": service.receipt_audit.verify()}

    @router.get("/receipt-audit/export", dependencies=read_deps)
    async def export_receipt_audit() -> Response:
        if service.receipt_audit is None:
            raise HTTPException(status_code=501, detail="Receipt audit is not configured")
        return Response(
            content=service.receipt_audit.export_jsonl(),
            media_type="application/x-ndjson",
            headers={"content-disposition": "attachment; filename=receipt-audit.jsonl"},
        )

    @router.post("/models/refresh/{account_id}", dependencies=write_deps)
    async def refresh_models(account_id: str) -> dict[str, Any]:
        try:
            models = await service.refresh_models(account_id)
        except KeyError as exc:
            raise HTTPException(status_code=404, detail=str(exc)) from exc
        except Exception as exc:
            raise HTTPException(status_code=502, detail=f"Model refresh failed: {exc}") from exc
        return {"account_id": account_id, "models": models, "count": len(models)}

    @router.post("/route", dependencies=read_deps)
    async def preview_route(payload: RoutingPayload) -> dict[str, Any]:
        try:
            return to_dict(service.route(_request(payload), allow_overrides=True))
        except ValueError as exc:
            raise HTTPException(status_code=400, detail=str(exc)) from exc
        except RoutingUnavailableError as exc:
            raise HTTPException(
                status_code=409,
                detail={
                    "message": str(exc),
                    "assigned_model": exc.assigned_model,
                    "reason": exc.reason,
                },
            ) from exc

    @router.post("/route/shadow", dependencies=read_deps)
    async def shadow_route(payload: ShadowRoutingPayload) -> dict[str, Any]:
        if not any((payload.candidate_profile, payload.candidate_policy, payload.candidate_model)):
            raise HTTPException(status_code=400, detail="A candidate route override is required")
        try:
            return service.shadow_route(
                _request(payload),
                candidate_profile=payload.candidate_profile,
                candidate_policy=payload.candidate_policy,
                candidate_model=payload.candidate_model,
            )
        except ValueError as exc:
            raise HTTPException(status_code=400, detail=str(exc)) from exc
        except RoutingUnavailableError as exc:
            raise HTTPException(
                status_code=409,
                detail={
                    "message": str(exc),
                    "assigned_model": exc.assigned_model,
                    "reason": exc.reason,
                },
            ) from exc

    @router.post("/scheduler/recommend", dependencies=read_deps)
    async def scheduler_recommendation(payload: SchedulerRecommendationPayload) -> dict[str, Any]:
        try:
            return recommend_schedule(
                service,
                _request(payload),
                guardrails=SchedulerGuardrails(
                    min_observations=payload.min_observations,
                    min_quality_score=payload.min_quality_score,
                    canary_sample_rate=payload.canary_sample_rate,
                ),
            )
        except ValueError as exc:
            raise HTTPException(status_code=400, detail=str(exc)) from exc
        except RoutingUnavailableError as exc:
            raise HTTPException(status_code=409, detail=str(exc)) from exc

    @router.post("/scheduler/drift", dependencies=read_deps)
    async def scheduler_drift(payload: DriftDetectionPayload) -> dict[str, Any]:
        try:
            return detect_quality_drift(
                service,
                task_type=payload.task_type,
                window_size=payload.window_size,
                max_quality_drop=payload.max_quality_drop,
            )
        except ValueError as exc:
            raise HTTPException(status_code=400, detail=str(exc)) from exc

    @router.post("/workflows", dependencies=write_deps, status_code=201)
    async def submit_workflow(payload: WorkflowPayload) -> dict[str, Any]:
        try:
            state = service.workflow_store.submit(_workflow_spec(payload))
        except WorkflowConflictError as exc:
            raise HTTPException(status_code=409, detail=str(exc)) from exc
        except WorkflowValidationError as exc:
            raise HTTPException(status_code=400, detail=str(exc)) from exc
        return {"workflow": asdict(state)}

    @router.get("/workflows/{workflow_id}", dependencies=read_deps)
    async def get_workflow(workflow_id: str) -> dict[str, Any]:
        state = service.workflow_store.get(workflow_id)
        if state is None:
            raise HTTPException(status_code=404, detail="unknown workflow")
        return {"workflow": asdict(state)}

    @router.post("/workflows/{workflow_id}/cancel", dependencies=write_deps)
    async def cancel_workflow(workflow_id: str) -> dict[str, Any]:
        try:
            state = service.workflow_store.cancel(workflow_id)
        except WorkflowValidationError as exc:
            raise HTTPException(status_code=404, detail=str(exc)) from exc
        return {"workflow": asdict(state)}

    @router.post("/workflows/{workflow_id}/tasks/{task_id}/approve", dependencies=write_deps)
    async def approve_workflow_task(workflow_id: str, task_id: str) -> dict[str, Any]:
        try:
            state = service.workflow_store.approve_task(workflow_id, task_id)
        except WorkflowValidationError as exc:
            raise HTTPException(status_code=409, detail=str(exc)) from exc
        return {"workflow": asdict(state)}

    @router.post("/workflows/{workflow_id}/tasks/{task_id}/verify", dependencies=write_deps)
    async def verify_workflow_task(workflow_id: str, task_id: str) -> dict[str, Any]:
        try:
            state = service.workflow_store.verify_task(workflow_id, task_id)
        except WorkflowValidationError as exc:
            raise HTTPException(status_code=409, detail=str(exc)) from exc
        return {"workflow": asdict(state)}

    async def execute(payload: ExecutionPayload) -> Response:
        request = _request(payload)
        messages = payload.messages
        parameters = dict(payload.parameters)
        try:
            parameters = service._execution_parameters(parameters)
        except ValueError as exc:
            raise HTTPException(status_code=400, detail=str(exc)) from exc
        if payload.stream:

            async def chunks() -> AsyncIterator[bytes]:
                async for _, chunk in service.stream(
                    request, messages=messages, parameters=parameters
                ):
                    yield chunk

            return StreamingResponse(chunks(), media_type="text/event-stream")
        try:
            decision, response = await service.execute(
                request, messages=messages, parameters=parameters
            )
        except RoutingUnavailableError as exc:
            raise HTTPException(
                status_code=409,
                detail={
                    "message": str(exc),
                    "assigned_model": exc.assigned_model,
                    "reason": exc.reason,
                },
            ) from exc
        except ValueError as exc:
            raise HTTPException(status_code=400, detail=str(exc)) from exc
        except RuntimeError as exc:
            raise HTTPException(status_code=502, detail=str(exc)) from exc
        return JSONResponse(content={"routing": to_dict(decision), "response": response})

    if direct_execution_enabled:
        router.add_api_route(
            "/execute",
            execute,
            methods=["POST"],
            dependencies=write_deps,
        )

        @router.post("/workflows/{workflow_id}/run", dependencies=write_deps)
        async def run_workflow(workflow_id: str) -> dict[str, Any]:
            try:
                state = await service.run_workflow(
                    service.workflow_store,
                    workflow_id,
                )
            except WorkflowValidationError as exc:
                raise HTTPException(status_code=400, detail=str(exc)) from exc
            except (RoutingUnavailableError, RuntimeError, ValueError) as exc:
                raise HTTPException(status_code=502, detail=str(exc)) from exc
            return {"workflow": asdict(state)}

    @router.get("/executions", dependencies=read_deps)
    async def executions(limit: int = 100) -> dict[str, Any]:
        return {"executions": service.telemetry.list(limit=min(max(limit, 1), 1000))}

    @router.get("/outcomes", dependencies=read_deps)
    async def outcomes(limit: int = 100) -> dict[str, Any]:
        return {"outcomes": service.outcome_telemetry.list(limit=min(max(limit, 1), 1000))}

    @router.post("/outcomes", dependencies=write_deps, status_code=201)
    async def record_outcome(payload: dict[str, Any]) -> dict[str, Any]:
        try:
            return {"outcome": service.record_outcome(payload)}
        except (TypeError, ValueError) as exc:
            raise HTTPException(status_code=400, detail=str(exc)) from exc

    return router


__all__ = ["create_orchestration_router"]
