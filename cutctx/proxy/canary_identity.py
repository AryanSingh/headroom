"""Privacy-safe, shared assignment identity resolution for savings canaries."""

from __future__ import annotations

import hashlib
from collections.abc import Mapping
from dataclasses import dataclass
from typing import Any


@dataclass(frozen=True)
class CanaryIdentity:
    value: str
    source: str
    sticky: bool


def _first_text(*values: Any) -> str | None:
    for value in values:
        if isinstance(value, str) and value.strip():
            return value.strip()
    return None


def _private_hash(salt: str, material: str) -> str:
    return hashlib.sha256(f"{salt}:{material}".encode()).hexdigest()


def resolve_canary_identity(
    *,
    headers: Mapping[str, str],
    body: Mapping[str, Any] | None,
    request_id: str,
    salt: str,
    existing_session_id: str | None = None,
) -> CanaryIdentity:
    """Resolve a sticky identity without retaining credentials or PII.

    Raw material is returned only for explicit opaque session identifiers. All
    user/project/conversation composites are hashed immediately, and the
    coordinator hashes every returned value again before persistence.
    """

    normalized_headers = {str(key).lower(): str(value) for key, value in headers.items()}
    explicit = _first_text(normalized_headers.get("x-cutctx-session-id"))
    if explicit:
        return CanaryIdentity(explicit, "x-cutctx-session-id", True)

    legacy_session = _first_text(
        normalized_headers.get("x-session-id"), normalized_headers.get("session-id")
    )
    if legacy_session:
        return CanaryIdentity(legacy_session, "legacy_session_header", True)

    if existing_session_id:
        return CanaryIdentity(existing_session_id, "codex_session", True)

    payload = body if isinstance(body, Mapping) else {}
    response = payload.get("response")
    if isinstance(response, Mapping):
        payload = response
    conversation = payload.get("conversation")
    conversation_id = conversation.get("id") if isinstance(conversation, Mapping) else conversation
    turn_or_conversation = _first_text(
        normalized_headers.get("x-codex-conversation-id"),
        normalized_headers.get("x-openai-conversation-id"),
        normalized_headers.get("x-conversation-id"),
        normalized_headers.get("x-codex-turn-id"),
        normalized_headers.get("x-cutctx-task-id"),
        payload.get("conversation_id"),
        conversation_id,
        payload.get("prompt_cache_key"),
        payload.get("previous_response_id"),
    )
    if turn_or_conversation:
        return CanaryIdentity(
            _private_hash(salt, f"conversation:{turn_or_conversation}"),
            "conversation_or_turn",
            True,
        )

    auth = _first_text(
        normalized_headers.get("authorization"),
        normalized_headers.get("x-api-key"),
    )
    user = _first_text(
        normalized_headers.get("x-cutctx-user-id"),
        normalized_headers.get("x-user-id"),
    )
    project = _first_text(
        normalized_headers.get("x-cutctx-project"),
        normalized_headers.get("x-project-id"),
        normalized_headers.get("openai-project"),
    )
    if auth or user or project:
        material = "|".join((auth or "anon", user or "unknown", project or "default"))
        return CanaryIdentity(
            _private_hash(salt, f"caller-project:{material}"),
            "caller_project",
            True,
        )

    return CanaryIdentity(request_id, "request_id", False)


__all__ = ["CanaryIdentity", "resolve_canary_identity"]
