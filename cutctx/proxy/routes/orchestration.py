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
from cutctx.orchestration.models import RoutingRequest, to_dict
from cutctx.orchestration.service import OrchestrationService
from cutctx.orchestration.workflow import (
    TaskSpec,
    WorkflowConflictError,
    WorkflowSpec,
    WorkflowValidationError,
)


class RoutingPayload(BaseModel):
    model_config = ConfigDict(extra="forbid")

    role: str | None = None
    model: str | None = None
    requested_model: str | None = None
    provider: str | None = None
    requested_provider: str | None = None
    required_capabilities: list[str] = Field(default_factory=list)
    selectors: dict[str, str] = Field(default_factory=dict)
    mode: str | None = None
    policy: str | None = None
    request_id: str = ""


class ExecutionPayload(RoutingPayload):
    messages: list[dict[str, Any]] = Field(default_factory=list)
    parameters: dict[str, Any] = Field(default_factory=dict)
    stream: bool = False


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


class WorkflowPayload(BaseModel):
    model_config = ConfigDict(extra="forbid")

    id: str = Field(min_length=1)
    idempotency_key: str = Field(default="", max_length=256)
    tasks: list[WorkflowTaskPayload] = Field(min_length=1, max_length=128)


def _workflow_spec(payload: WorkflowPayload) -> WorkflowSpec:
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
            )
            for task in payload.tasks
        ],
    )


def _request(payload: RoutingPayload) -> RoutingRequest:
    return RoutingRequest(
        role=payload.role,
        requested_model=payload.model or payload.requested_model,
        requested_provider=payload.provider or payload.requested_provider,
        required_capabilities=set(payload.required_capabilities),
        selectors=dict(payload.selectors),
        mode=payload.mode,
        policy=payload.policy,
        request_id=payload.request_id,
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
        except RoutingUnavailableError as exc:
            raise HTTPException(
                status_code=409,
                detail={
                    "message": str(exc),
                    "assigned_model": exc.assigned_model,
                    "reason": exc.reason,
                },
            ) from exc

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

    return router


__all__ = ["create_orchestration_router"]
