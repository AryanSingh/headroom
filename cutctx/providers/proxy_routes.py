# mypy: disable-error-code=no-untyped-def
"""Provider-specific proxy route registration."""

from __future__ import annotations

import json
import logging
import os
from typing import Any, cast
from urllib.parse import quote

from fastapi import (
    APIRouter,
    Depends,
    FastAPI,
    HTTPException,
    Request,
    WebSocket,
    WebSocketException,
)
from fastapi.responses import JSONResponse, Response
from starlette.requests import HTTPConnection

from cutctx.proxy.handlers.openai import _resolve_codex_routing_headers

logger = logging.getLogger("cutctx.proxy.routes")


_POLICY_PATH_ATTR = "_context_policy_path"
_POLICY_ENGINE_ATTR = "_context_policy_engine"


def _context_policy_path() -> str:
    return os.environ.get("CUTCTX_CONTEXT_POLICY", "").strip()


def _request_session_id(request: Request, body: dict[str, Any]) -> str:
    metadata = body.get("metadata")
    metadata_session_id = metadata.get("session_id") if isinstance(metadata, dict) else None
    return str(
        request.headers.get("x-cutctx-session-id")
        or body.get("session_id")
        or metadata_session_id
        or request.headers.get("x-request-id")
        or "default"
    )


def _get_context_policy_engine(proxy: Any):
    policy_path = _context_policy_path()
    if not policy_path:
        return None

    cached_path = getattr(proxy, _POLICY_PATH_ATTR, None)
    cached_engine = getattr(proxy, _POLICY_ENGINE_ATTR, None)
    if cached_engine is not None and cached_path == policy_path:
        return cached_engine

    from cutctx.context_policy import ContextPolicyEngine, load_context_policy

    engine = ContextPolicyEngine(load_context_policy(policy_path))
    setattr(proxy, _POLICY_PATH_ATTR, policy_path)
    setattr(proxy, _POLICY_ENGINE_ATTR, engine)
    return engine


def _extract_context_policy_messages(body: dict[str, Any]) -> list[dict[str, Any]]:
    messages = body.get("messages")
    if isinstance(messages, list):
        return [message for message in messages if isinstance(message, dict)]

    # Responses API accepts either string input or an array of typed items.
    input_items = body.get("input")
    if isinstance(input_items, str):
        return [{"role": "user", "content": input_items}]
    if isinstance(input_items, list):
        extracted: list[dict[str, Any]] = []
        for item in input_items:
            if not isinstance(item, dict):
                continue
            content = item.get("content")
            if isinstance(content, str):
                extracted.append({"role": item.get("role", "user"), "content": content})
                continue
            if isinstance(content, list):
                text_parts = [
                    part.get("text")
                    for part in content
                    if isinstance(part, dict) and isinstance(part.get("text"), str)
                ]
                if text_parts:
                    extracted.append(
                        {
                            "role": item.get("role", "user"),
                            "content": "\n".join(text_parts),
                        }
                    )
        return extracted

    return []


def _apply_context_policy_messages(
    body: dict[str, Any], redacted_messages: list[dict[str, Any]]
) -> None:
    if isinstance(body.get("messages"), list):
        body["messages"] = [
            message
            for message in redacted_messages
            if isinstance(message, dict) and not message.get("_policy_dropped")
        ]
        return

    # For Responses API string/list input we can safely redact string content,
    # but avoid structural rewrites for complex multimodal payloads.
    if isinstance(body.get("input"), str) and redacted_messages:
        content = redacted_messages[0].get("content")
        if isinstance(content, str):
            body["input"] = content
        return

    input_items = body.get("input")
    if not isinstance(input_items, list):
        return

    redacted_iter = iter(redacted_messages)
    for item in input_items:
        if not isinstance(item, dict):
            continue
        try:
            redacted = next(redacted_iter)
        except StopIteration:
            break
        content = redacted.get("content")
        if not isinstance(content, str):
            continue
        original_content = item.get("content")
        if isinstance(original_content, str):
            item["content"] = content
        elif isinstance(original_content, list):
            for part in original_content:
                if isinstance(part, dict) and isinstance(part.get("text"), str):
                    part["text"] = content
                    break


async def _enforce_context_policy(
    proxy: Any, request: Request, *, surface: str
) -> JSONResponse | None:
    engine = _get_context_policy_engine(proxy)
    if engine is None:
        return None

    try:
        body = await request.json()
    except Exception:
        return None
    if not isinstance(body, dict):
        return None

    messages = _extract_context_policy_messages(body)
    if not messages:
        return None

    metadata = body.get("metadata")
    metadata_agent_id = metadata.get("agent_id") if isinstance(metadata, dict) else None
    agent_id = request.headers.get("x-cutctx-agent-id") or body.get("agent_id") or metadata_agent_id
    team_id = request.headers.get("x-cutctx-team-id") or body.get("team_id")
    result = engine.evaluate(
        messages,
        agent_id=str(agent_id) if agent_id else None,
        team_id=str(team_id) if team_id else None,
        estimate_tokens=len(json.dumps(messages, ensure_ascii=False)),
    )

    if result.blocked or not result.budget_allowed:
        from cutctx.proxy.session_replay import get_replay_store

        replay_store = get_replay_store()
        if replay_store is not None:
            replay_store.record(
                session_id=_request_session_id(request, body),
                event_type="policy_blocked",
                surface=surface,
                request_id=request.headers.get("x-request-id"),
                detail={
                    "message": result.block_reason or result.budget_reason,
                    "matched_rules": result.matched_block_rules,
                },
            )
        return JSONResponse(
            status_code=403,
            content={
                "error": {
                    "type": "context_policy_blocked",
                    "message": result.block_reason
                    or result.budget_reason
                    or "Request blocked by context policy",
                    "surface": surface,
                    "matched_rules": result.matched_block_rules,
                }
            },
        )

    if result.matched_redact_rules or result.redacted_messages != messages:
        _apply_context_policy_messages(body, result.redacted_messages)
        request._body = json.dumps(body, separators=(",", ":")).encode("utf-8")
        if hasattr(request, "_json"):
            request._json = body
        from cutctx.proxy.session_replay import get_replay_store

        replay_store = get_replay_store()
        if replay_store is not None:
            replay_store.record(
                session_id=_request_session_id(request, body),
                event_type="policy_redacted",
                surface=surface,
                request_id=request.headers.get("x-request-id"),
                detail={"matched_rules": result.matched_redact_rules},
            )

    return None


def _api_target(proxy: Any, provider_name: str) -> str:
    legacy_attrs = {
        "anthropic": "ANTHROPIC_API_URL",
        "openai": "OPENAI_API_URL",
        "gemini": "GEMINI_API_URL",
        "cloudcode": "CLOUDCODE_API_URL",
        "vertex": "VERTEX_API_URL",
    }
    legacy_attr = legacy_attrs[provider_name]
    return cast(str, getattr(proxy, legacy_attr, proxy.provider_runtime.api_target(provider_name)))


def _select_passthrough_base_url(proxy: Any, headers: dict[str, str]) -> str:
    # Codex CLI subscription mode hits a wide surface under
    # `/backend-api/*` (rate-limit polling, agent identity, JWT
    # refresh, cloud tasks). Without this branch the catchall
    # routes those to api.openai.com which 404s, and Codex
    # interprets the failure as "session invalid" and refuses
    # to use subscription auth at all. The check is a no-op
    # for non-ChatGPT-authed requests.
    _, is_chatgpt_auth = _resolve_codex_routing_headers(headers)
    if is_chatgpt_auth:
        return "https://chatgpt.com"
    if headers.get("x-goog-api-key"):
        return _api_target(proxy, "gemini")
    if headers.get("api-key"):
        azure_base = headers.get("x-cutctx-base-url", "")
        if azure_base:
            return azure_base.rstrip("/")
    provider_name = proxy.provider_runtime.model_metadata_provider(headers)
    return _api_target(proxy, provider_name)


# Codex ChatGPT-subscription auth doesn't have access to
# `chatgpt.com/backend-api/models` — that endpoint returns 403 to OAuth
# bearer tokens (issue #478). Codex polls `/v1/models` every few seconds
# to populate its model-picker UI, so the 403 storm is noisy and breaks
# refresh. The fix: when Codex hits `/v1/models` under ChatGPT auth,
# fetch the Codex-specific registry first and synthesize an
# OpenAI-compatible response from its slugs. If that registry is
# unavailable, fall back to the known-supported static set.
#
# This fallback must stay conservative, but it should not hide current Codex
# models merely because the dynamic registry is temporarily unavailable.
# The proxy request path preserves the caller's model and strips internal
# Lite headers before upstream, so exposing these slugs lets clients retry
# against the real account/server-side model availability instead of being
# forced onto an older fallback.
_CHATGPT_AUTH_CODEX_MODELS: tuple[str, ...] = (
    "gpt-5.5",
    "gpt-5.6-terra",
    "gpt-5.4",
    "gpt-5.4-mini",
    "gpt-5.3-codex-spark",
    "gpt-5.3",
    "gpt-5.2",
    "gpt-5.1",
    "gpt-5",
    "codex-mini-latest",
)


def _codex_client_version(requested_client_version: str | None = None) -> str:
    """Return the Codex client version to use for model-registry requests."""
    if requested_client_version:
        return requested_client_version
    return "0.130.0"


def _models_list_response(models_raw: tuple[dict[str, Any], ...]) -> Response:
    """Build an OpenAI-compatible model-list response for Codex metadata callers."""
    for m in models_raw:
        m["id"] = m.get("slug", "unknown")
        m["object"] = "model"

    payload = {
        "object": "list",
        "data": list(models_raw),
        "models": list(models_raw),
    }
    return Response(
        content=json.dumps(payload),
        status_code=200,
        headers={"content-type": "application/json"},
    )


def _synthetic_models_list_response() -> Response:
    """OpenAI-compatible `/v1/models` payload for Codex ChatGPT auth."""
    synthetic_models = tuple({"slug": m} for m in _CHATGPT_AUTH_CODEX_MODELS)
    return _models_list_response(synthetic_models)


def _synthetic_model_get_response(model_id: str) -> Response:
    """OpenAI-compatible `/v1/models/{id}` payload."""
    if model_id not in _CHATGPT_AUTH_CODEX_MODELS:
        return Response(
            content=json.dumps(
                {
                    "error": {
                        "message": f"Model {model_id!r} not available under ChatGPT auth",
                        "type": "invalid_request_error",
                        "code": "model_not_found",
                    }
                }
            ),
            status_code=404,
            headers={"content-type": "application/json"},
        )
    return Response(
        content=json.dumps(
            {
                "id": model_id,
                "object": "model",
                "created": 0,
                "owned_by": "openai",
            }
        ),
        status_code=200,
        headers={"content-type": "application/json"},
    )


def _normalize_codex_registry_headers(headers: dict[str, str]) -> dict[str, str]:
    """Prepare inbound ChatGPT auth headers for the Codex model registry."""
    from cutctx.proxy.handlers.openai.utils import _strip_openai_internal_headers

    upstream_headers = dict(headers)
    upstream_headers.pop("host", None)
    upstream_headers = _strip_openai_internal_headers(upstream_headers)
    account_id = (
        upstream_headers.get("chatgpt-account-id")
        or upstream_headers.get("ChatGPT-Account-ID")
        or ""
    )
    if account_id:
        upstream_headers["chatgpt-account-id"] = account_id
        upstream_headers.pop("ChatGPT-Account-ID", None)
    upstream_headers["accept"] = "application/json"
    upstream_headers.pop("Accept", None)
    return upstream_headers


async def _fetch_chatgpt_codex_models_raw(
    proxy: Any,
    headers: dict[str, str],
    requested_client_version: str | None,
) -> tuple[dict[str, Any], ...] | None:
    """Fetch Codex model objects from ChatGPT."""
    client_version = _codex_client_version(requested_client_version)
    upstream_headers = _normalize_codex_registry_headers(headers)
    url = (
        "https://chatgpt.com/backend-api/codex/models"
        f"?client_version={quote(client_version, safe='')}"
    )
    try:
        assert proxy.http_client is not None
        resp = await proxy.http_client.get(
            url,
            headers=upstream_headers,
            timeout=15.0,
        )
        if resp.status_code >= 400:
            logger.warning(
                "Codex model registry fetch failed: HTTP %s: %s",
                resp.status_code,
                resp.text[:300],
            )
            return None

        data = resp.json()
        models_raw = data.get("models") if isinstance(data, dict) else None
        if not isinstance(models_raw, list):
            logger.warning("Codex model registry response did not contain models[]")
            return None

        models_list = tuple(
            entry for entry in models_raw if isinstance(entry, dict) and entry.get("slug")
        )
        if not models_list:
            logger.warning("Codex model registry returned no model slugs")
            return None

        logger.info("Fetched %d Codex models from upstream model registry", len(models_list))
        return models_list
    except Exception:
        logger.exception("Codex model registry fetch failed")
        return None


async def _fetch_chatgpt_codex_models_response(
    proxy: Any,
    headers: dict[str, str],
    requested_client_version: str | None,
) -> Response | None:
    """Build a dynamic `/v1/models` response from the Codex registry when available."""
    models_raw = await _fetch_chatgpt_codex_models_raw(proxy, headers, requested_client_version)
    if models_raw is None:
        return None
    return _models_list_response(models_raw)


async def _fetch_chatgpt_codex_model_get_response(
    proxy: Any,
    headers: dict[str, str],
    model_id: str,
    requested_client_version: str | None,
) -> Response | None:
    """Build a dynamic `/v1/models/{id}` response from the Codex registry when available."""
    models_raw = await _fetch_chatgpt_codex_models_raw(proxy, headers, requested_client_version)
    if models_raw is None:
        return None

    found_model = next((m for m in models_raw if m.get("slug") == model_id), None)
    if found_model is not None:
        return Response(
            content=json.dumps(found_model),
            status_code=200,
            headers={"content-type": "application/json"},
        )
    return Response(
        content=json.dumps(
            {
                "error": {
                    "message": f"Model {model_id!r} not available under ChatGPT auth",
                    "type": "invalid_request_error",
                    "code": "model_not_found",
                }
            }
        ),
        status_code=404,
        headers={"content-type": "application/json"},
    )


async def _handle_chatgpt_model_metadata(
    proxy: Any,
    request: Request,
    upstream_path: str,
) -> Response | None:
    headers = dict(request.headers.items())
    headers.pop("host", None)
    headers, is_chatgpt_auth = _resolve_codex_routing_headers(headers)
    if not is_chatgpt_auth:
        return None

    # Avoid generic `/backend-api/models[/{id}]`, which returns 403 for
    # OAuth tokens, but prefer the Codex-specific registry when available.
    requested_client_version = request.query_params.get("client_version")
    if upstream_path == "/backend-api/models":
        upstream_response = await _fetch_chatgpt_codex_models_response(
            proxy,
            headers,
            requested_client_version,
        )
        if upstream_response is not None:
            return upstream_response
        return _synthetic_models_list_response()
    if upstream_path.startswith("/backend-api/models/"):
        model_id = upstream_path[len("/backend-api/models/") :]
        upstream_response = await _fetch_chatgpt_codex_model_get_response(
            proxy,
            headers,
            model_id,
            requested_client_version,
        )
        if upstream_response is not None:
            return upstream_response
        return _synthetic_model_get_response(model_id)

    url = f"https://chatgpt.com{upstream_path}"
    if request.url.query:
        url = f"{url}?{request.url.query}"

    body = await request.body()
    try:
        assert proxy.http_client is not None
        resp = await proxy.http_client.request(
            request.method,
            url,
            headers=headers,
            content=body,
            timeout=120.0,
        )
        response_headers = dict(resp.headers)
        response_headers.pop("content-encoding", None)
        response_headers.pop("content-length", None)
        return Response(
            content=resp.content,
            status_code=resp.status_code,
            headers=response_headers,
        )
    except Exception as exc:
        logger.error("Passthrough %s failed: %s", upstream_path, exc)
        return Response(content=str(exc), status_code=502)


def register_provider_routes(app: FastAPI, proxy: Any) -> None:
    """Register provider-specific proxy endpoints."""

    from cutctx.proxy.client_auth import (
        ProxyClientAuthError,
        require_http_proxy_client,
        require_websocket_proxy_client,
    )

    async def _require_proxy_client(connection: HTTPConnection) -> None:
        try:
            if connection.scope.get("type") == "websocket":
                require_websocket_proxy_client(connection, proxy.config)
            else:
                require_http_proxy_client(connection, proxy.config)
        except ProxyClientAuthError as exc:
            if connection.scope.get("type") == "websocket":
                raise WebSocketException(code=1008, reason=str(exc)) from exc
            raise HTTPException(
                status_code=401,
                detail={
                    "message": str(exc),
                    "remediation": "Pass X-Cutctx-Proxy-Key with the configured proxy client key.",
                },
            ) from exc

    parent_app = app
    provider_router = APIRouter(dependencies=[Depends(_require_proxy_client)])
    app = cast(Any, provider_router)

    async def vertex_publisher_passthrough(request: Request, publisher: str, action: str):
        return await proxy.handle_passthrough(
            request,
            _api_target(proxy, "vertex"),
            action,
            f"vertex:{publisher}",
        )

    @app.post("/v1/messages")
    async def anthropic_messages(request: Request):
        policy_response = await _enforce_context_policy(
            proxy, request, surface="anthropic_messages"
        )
        if policy_response is not None:
            return policy_response
        return await proxy.handle_anthropic_messages(request)

    @app.post("/v1/messages/count_tokens")
    async def anthropic_count_tokens(request: Request):
        return await proxy.handle_passthrough(
            request,
            _api_target(proxy, "anthropic"),
            "count_tokens",
            "anthropic",
        )

    @app.post("/v1/messages/batches")
    async def anthropic_batch_create(request: Request):
        return await proxy.handle_anthropic_batch_create(request)

    @app.get("/v1/messages/batches")
    async def anthropic_batch_list(request: Request):
        return await proxy.handle_anthropic_batch_passthrough(request)

    @app.get("/v1/messages/batches/{batch_id}")
    async def anthropic_batch_get(request: Request, batch_id: str):
        return await proxy.handle_anthropic_batch_passthrough(request, batch_id)

    @app.get("/v1/messages/batches/{batch_id}/results")
    async def anthropic_batch_results(request: Request, batch_id: str):
        return await proxy.handle_anthropic_batch_results(request, batch_id)

    @app.post("/v1/messages/batches/{batch_id}/cancel")
    async def anthropic_batch_cancel(request: Request, batch_id: str):
        return await proxy.handle_anthropic_batch_passthrough(request, batch_id)

    @app.post("/v1/chat/completions")
    async def openai_chat(request: Request):
        policy_response = await _enforce_context_policy(
            proxy, request, surface="openai_chat_completions"
        )
        if policy_response is not None:
            return policy_response
        return await proxy.handle_openai_chat(request)

    @app.post("/v1/responses")
    async def openai_responses(request: Request):
        policy_response = await _enforce_context_policy(proxy, request, surface="openai_responses")
        if policy_response is not None:
            return policy_response
        return await proxy.handle_openai_responses(request)

    @app.post("/v1/codex/responses")
    async def openai_v1_codex_responses(request: Request):
        return await proxy.handle_openai_responses(request)

    @app.post("/backend-api/responses")
    async def openai_codex_responses(request: Request):
        return await proxy.handle_openai_responses(request)

    @app.post("/backend-api/codex/responses")
    async def openai_codex_nested_responses(request: Request):
        return await proxy.handle_openai_responses(request)

    @app.websocket("/v1/responses")
    async def openai_responses_ws(websocket: WebSocket):
        await proxy.handle_openai_responses_ws(websocket)

    @app.websocket("/v1/codex/responses")
    async def openai_v1_codex_responses_ws(websocket: WebSocket):
        await proxy.handle_openai_responses_ws(websocket)

    @app.get("/v1/responses/{sub_path:path}", name="openai_responses_sub_get")
    @app.post("/v1/responses/{sub_path:path}", name="openai_responses_sub_post")
    @app.delete("/v1/responses/{sub_path:path}", name="openai_responses_sub_delete")
    async def openai_responses_sub(request: Request, sub_path: str):
        headers = dict(request.headers.items())
        headers.pop("host", None)
        from cutctx.proxy.handlers.openai.utils import _strip_openai_internal_headers
        from cutctx.proxy.helpers import _strip_internal_headers

        headers = _strip_internal_headers(headers)
        headers = _strip_openai_internal_headers(headers)
        headers, is_chatgpt_auth = _resolve_codex_routing_headers(headers)

        if is_chatgpt_auth:
            url = f"https://chatgpt.com/backend-api/codex/responses/{sub_path}"
        else:
            url = f"{_api_target(proxy, 'openai')}/v1/responses/{sub_path}"

        if request.url.query:
            url = f"{url}?{request.url.query}"

        body = await request.body()
        try:
            assert proxy.http_client is not None
            resp = await proxy.http_client.request(
                request.method,
                url,
                headers=headers,
                content=body,
                timeout=120.0,
            )
            response_headers = dict(resp.headers)
            response_headers.pop("content-encoding", None)
            response_headers.pop("content-length", None)
            return Response(
                content=resp.content,
                status_code=resp.status_code,
                headers=response_headers,
            )
        except Exception as exc:
            logger.error("Passthrough /v1/responses/%s failed: %s", sub_path, exc)
            return Response(content=str(exc), status_code=502)

    @app.get("/v1/codex/responses/{sub_path:path}", name="openai_v1_codex_responses_sub_get")
    @app.post("/v1/codex/responses/{sub_path:path}", name="openai_v1_codex_responses_sub_post")
    @app.delete("/v1/codex/responses/{sub_path:path}", name="openai_v1_codex_responses_sub_delete")
    async def openai_v1_codex_responses_sub(request: Request, sub_path: str):
        return await openai_responses_sub(request, sub_path)

    @app.websocket("/backend-api/responses")
    async def openai_codex_responses_ws(websocket: WebSocket):
        await proxy.handle_openai_responses_ws(websocket)

    @app.websocket("/backend-api/codex/responses")
    async def openai_codex_nested_responses_ws(websocket: WebSocket):
        await proxy.handle_openai_responses_ws(websocket)

    @app.get("/backend-api/responses/{sub_path:path}", name="openai_codex_responses_sub_get")
    @app.post("/backend-api/responses/{sub_path:path}", name="openai_codex_responses_sub_post")
    @app.delete("/backend-api/responses/{sub_path:path}", name="openai_codex_responses_sub_delete")
    async def openai_codex_responses_sub(request: Request, sub_path: str):
        return await openai_responses_sub(request, sub_path)

    @app.get(
        "/backend-api/codex/responses/{sub_path:path}", name="openai_codex_nested_responses_sub_get"
    )
    @app.post(
        "/backend-api/codex/responses/{sub_path:path}",
        name="openai_codex_nested_responses_sub_post",
    )
    @app.delete(
        "/backend-api/codex/responses/{sub_path:path}",
        name="openai_codex_nested_responses_sub_delete",
    )
    async def openai_codex_nested_responses_sub(request: Request, sub_path: str):
        return await openai_responses_sub(request, sub_path)

    @app.post("/v1/batches")
    async def create_batch(request: Request):
        return await proxy.handle_batch_create(request)

    @app.get("/v1/batches")
    async def list_batches(request: Request):
        return await proxy.handle_batch_list(request)

    @app.get("/v1/batches/{batch_id}")
    async def get_batch(request: Request, batch_id: str):
        return await proxy.handle_batch_get(request, batch_id)

    @app.post("/v1/batches/{batch_id}/cancel")
    async def cancel_batch(request: Request, batch_id: str):
        return await proxy.handle_batch_cancel(request, batch_id)

    @app.post("/v1beta/models/{model}:generateContent")
    async def gemini_generate_content(request: Request, model: str):
        return await proxy.handle_gemini_generate_content(request, model)

    @app.post("/v1beta/models/{model}:streamGenerateContent")
    async def gemini_stream_generate_content(request: Request, model: str):
        return await proxy.handle_gemini_stream_generate_content(request, model)

    @app.post("/v1beta/models/{model}:countTokens")
    async def gemini_count_tokens(request: Request, model: str):
        return await proxy.handle_gemini_count_tokens(request, model)

    @app.post("/v1internal:streamGenerateContent")
    async def google_cloudcode_stream_generate_content(request: Request):
        return await proxy.handle_google_cloudcode_stream(request)

    @app.post("/v1/v1internal:streamGenerateContent")
    async def google_cloudcode_stream_generate_content_v1(request: Request):
        return await proxy.handle_google_cloudcode_stream(request)

    @app.post("/v1internal:generateContent")
    async def google_cloudcode_generate_content(request: Request):
        return await proxy.handle_gemini_generate_content(
            request,
            model="cloudcode-assist",
            provider_name="gemini",
        )

    @app.post("/v1/v1internal:generateContent")
    async def google_cloudcode_generate_content_v1(request: Request):
        return await proxy.handle_gemini_generate_content(
            request,
            model="cloudcode-assist",
            provider_name="gemini",
        )

    async def _cloudcode_internal_passthrough(request: Request, action: str) -> Response:
        """Forward Cloud Code Assist setup/metadata calls (not generation).

        loadCodeAssist/onboardUser/countTokens are non-generative calls the
        Gemini CLI and Antigravity make before/alongside generateContent; they
        carry no compressible message content, so they're passed straight
        through to the resolved Cloud Code Assist upstream rather than routed
        through the optimization pipeline.
        """
        headers = dict(request.headers.items())
        headers.pop("host", None)
        is_antigravity = headers.get("user-agent", "").lower().startswith("antigravity/")
        base_url = proxy._resolve_cloudcode_base_url(is_antigravity)
        url = f"{base_url}/v1internal:{action}"
        if request.url.query:
            url = f"{url}?{request.url.query}"
        body = await request.body()
        try:
            assert proxy.http_client is not None
            resp = await proxy.http_client.request(
                request.method,
                url,
                headers=headers,
                content=body,
                timeout=120.0,
            )
            response_headers = dict(resp.headers)
            response_headers.pop("content-encoding", None)
            response_headers.pop("content-length", None)
            return Response(
                content=resp.content,
                status_code=resp.status_code,
                headers=response_headers,
            )
        except Exception as exc:
            logger.error("Cloud Code Assist passthrough %s failed: %s", action, exc)
            return Response(content=str(exc), status_code=502)

    @app.post("/v1internal:loadCodeAssist")
    async def google_cloudcode_load_code_assist(request: Request):
        return await _cloudcode_internal_passthrough(request, "loadCodeAssist")

    @app.post("/v1/v1internal:loadCodeAssist")
    async def google_cloudcode_load_code_assist_v1(request: Request):
        return await _cloudcode_internal_passthrough(request, "loadCodeAssist")

    @app.post("/v1internal:onboardUser")
    async def google_cloudcode_onboard_user(request: Request):
        return await _cloudcode_internal_passthrough(request, "onboardUser")

    @app.post("/v1/v1internal:onboardUser")
    async def google_cloudcode_onboard_user_v1(request: Request):
        return await _cloudcode_internal_passthrough(request, "onboardUser")

    @app.post("/v1internal:countTokens")
    async def google_cloudcode_count_tokens(request: Request):
        return await _cloudcode_internal_passthrough(request, "countTokens")

    @app.post("/v1/v1internal:countTokens")
    async def google_cloudcode_count_tokens_v1(request: Request):
        return await _cloudcode_internal_passthrough(request, "countTokens")

    @app.post(
        "/{api_version}/projects/{project}/locations/{location}/publishers/{publisher}/models/{model}:generateContent"
    )
    async def vertex_generate_content(
        request: Request,
        api_version: str,
        project: str,
        location: str,
        publisher: str,
        model: str,
    ):
        del api_version, project, location
        if publisher == "google":
            return await proxy.handle_gemini_generate_content(
                request,
                model,
                _api_target(proxy, "vertex"),
                "vertex:google",
            )
        return await vertex_publisher_passthrough(request, publisher, "generateContent")

    @app.post(
        "/{api_version}/projects/{project}/locations/{location}/publishers/{publisher}/models/{model}:streamGenerateContent"
    )
    async def vertex_stream_generate_content(
        request: Request,
        api_version: str,
        project: str,
        location: str,
        publisher: str,
        model: str,
    ):
        del api_version, project, location
        if publisher == "google":
            return await proxy.handle_gemini_generate_content(
                request,
                model,
                _api_target(proxy, "vertex"),
                "vertex:google",
            )
        return await vertex_publisher_passthrough(request, publisher, "streamGenerateContent")

    @app.post(
        "/{api_version}/projects/{project}/locations/{location}/publishers/{publisher}/models/{model}:countTokens"
    )
    async def vertex_count_tokens(
        request: Request,
        api_version: str,
        project: str,
        location: str,
        publisher: str,
        model: str,
    ):
        del api_version, project, location
        if publisher == "google":
            return await proxy.handle_gemini_count_tokens(
                request,
                model,
                _api_target(proxy, "vertex"),
                "vertex:google",
            )
        return await vertex_publisher_passthrough(request, publisher, "countTokens")

    @app.post(
        "/{api_version}/projects/{project}/locations/{location}/publishers/{publisher}/models/{model}:rawPredict"
    )
    async def vertex_raw_predict(
        request: Request,
        api_version: str,
        project: str,
        location: str,
        publisher: str,
        model: str,
    ):
        del api_version, project, location
        if publisher == "anthropic":
            return await proxy.handle_anthropic_messages(
                request,
                _api_target(proxy, "vertex"),
                "vertex:anthropic",
                model,
            )
        return await vertex_publisher_passthrough(request, publisher, "rawPredict")

    @app.post(
        "/{api_version}/projects/{project}/locations/{location}/publishers/{publisher}/models/{model}:streamRawPredict"
    )
    async def vertex_stream_raw_predict(
        request: Request,
        api_version: str,
        project: str,
        location: str,
        publisher: str,
        model: str,
    ):
        del api_version, project, location
        if publisher == "anthropic":
            return await proxy.handle_anthropic_messages(
                request,
                _api_target(proxy, "vertex"),
                "vertex:anthropic",
                model,
                True,
            )
        return await vertex_publisher_passthrough(request, publisher, "streamRawPredict")

    @app.get("/v1/models")
    async def list_models(request: Request):
        chatgpt_response = await _handle_chatgpt_model_metadata(
            proxy,
            request,
            "/backend-api/models",
        )
        if chatgpt_response is not None:
            return chatgpt_response

        provider_name = proxy.provider_runtime.model_metadata_provider(dict(request.headers))
        return await proxy.handle_passthrough(
            request,
            _api_target(proxy, provider_name),
            "models",
            provider_name,
        )

    @app.get("/v1/models/{model_id}")
    async def get_model(request: Request, model_id: str):
        chatgpt_response = await _handle_chatgpt_model_metadata(
            proxy,
            request,
            f"/backend-api/models/{model_id}",
        )
        if chatgpt_response is not None:
            return chatgpt_response

        provider_name = proxy.provider_runtime.model_metadata_provider(dict(request.headers))
        return await proxy.handle_passthrough(
            request,
            _api_target(proxy, provider_name),
            "models",
            provider_name,
        )

    @app.post("/v1/embeddings")
    async def openai_embeddings(request: Request):
        return await proxy.handle_passthrough(
            request,
            _api_target(proxy, "openai"),
            "embeddings",
            "openai",
        )

    @app.post("/v1/moderations")
    async def openai_moderations(request: Request):
        return await proxy.handle_passthrough(
            request,
            _api_target(proxy, "openai"),
            "moderations",
            "openai",
        )

    @app.post("/v1/images/generations")
    async def openai_images_generations(request: Request):
        return await proxy.handle_passthrough(
            request,
            _api_target(proxy, "openai"),
            "images/generations",
            "openai",
        )

    @app.post("/v1/audio/transcriptions")
    async def openai_audio_transcriptions(request: Request):
        return await proxy.handle_passthrough(
            request,
            _api_target(proxy, "openai"),
            "audio/transcriptions",
            "openai",
        )

    @app.post("/v1/audio/speech")
    async def openai_audio_speech(request: Request):
        return await proxy.handle_passthrough(
            request,
            _api_target(proxy, "openai"),
            "audio/speech",
            "openai",
        )

    @app.get("/v1beta/models")
    async def gemini_list_models(request: Request):
        return await proxy.handle_passthrough(
            request,
            _api_target(proxy, "gemini"),
            "models",
            "gemini",
        )

    @app.get("/v1beta/models/{model_name}")
    async def gemini_get_model(request: Request, model_name: str):
        return await proxy.handle_passthrough(
            request,
            _api_target(proxy, "gemini"),
            "models",
            "gemini",
        )

    @app.post("/v1beta/models/{model}:embedContent")
    async def gemini_embed_content(request: Request, model: str):
        return await proxy.handle_passthrough(
            request,
            _api_target(proxy, "gemini"),
            "embedContent",
            "gemini",
        )

    @app.post("/v1beta/models/{model}:batchEmbedContents")
    async def gemini_batch_embed_contents(request: Request, model: str):
        return await proxy.handle_passthrough(
            request,
            _api_target(proxy, "gemini"),
            "batchEmbedContents",
            "gemini",
        )

    @app.post("/v1beta/models/{model}:batchGenerateContent")
    async def gemini_batch_create(request: Request, model: str):
        return await proxy.handle_google_batch_create(request, model)

    @app.get("/v1beta/batches/{batch_name}")
    async def gemini_batch_get(request: Request, batch_name: str):
        return await proxy.handle_google_batch_results(request, batch_name)

    @app.post("/v1beta/batches/{batch_name}:cancel")
    async def gemini_batch_cancel(request: Request, batch_name: str):
        return await proxy.handle_google_batch_passthrough(request, batch_name)

    @app.delete("/v1beta/batches/{batch_name}")
    async def gemini_batch_delete(request: Request, batch_name: str):
        return await proxy.handle_google_batch_passthrough(request, batch_name)

    @app.post("/v1beta/cachedContents")
    async def gemini_create_cached_content(request: Request):
        return await proxy.handle_passthrough(
            request,
            _api_target(proxy, "gemini"),
            "cachedContents",
            "gemini",
        )

    @app.get("/v1beta/cachedContents")
    async def gemini_list_cached_contents(request: Request):
        return await proxy.handle_passthrough(
            request,
            _api_target(proxy, "gemini"),
            "cachedContents",
            "gemini",
        )

    @app.get("/v1beta/cachedContents/{cache_id}")
    async def gemini_get_cached_content(request: Request, cache_id: str):
        return await proxy.handle_passthrough(
            request,
            _api_target(proxy, "gemini"),
            "cachedContents",
            "gemini",
        )

    @app.delete("/v1beta/cachedContents/{cache_id}")
    async def gemini_delete_cached_content(request: Request, cache_id: str):
        return await proxy.handle_passthrough(
            request,
            _api_target(proxy, "gemini"),
            "cachedContents",
            "gemini",
        )

    @app.get("/{path:path}", name="passthrough_get")
    @app.post("/{path:path}", name="passthrough_post")
    @app.put("/{path:path}", name="passthrough_put")
    @app.delete("/{path:path}", name="passthrough_delete")
    async def passthrough(request: Request, path: str):
        custom_base = request.headers.get("x-cutctx-base-url")
        if custom_base:
            return await proxy.handle_passthrough(request, custom_base.rstrip("/"))
        return await proxy.handle_passthrough(
            request,
            _select_passthrough_base_url(proxy, dict(request.headers)),
        )

    parent_app.include_router(provider_router)
