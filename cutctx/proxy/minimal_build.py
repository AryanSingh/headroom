"""Ponytail-inspired minimal-build guidance for proxy requests.

This module injects a small, opt-in instruction block that nudges coding
models toward reusing existing solutions, preferring native primitives, and
stopping once the first sufficient fix is reached.
"""

from __future__ import annotations

import os
from collections.abc import Mapping
from typing import Any

_ENABLE_ENV = "CUTCTX_MINIMAL_BUILD"
_MODE_ENV = "CUTCTX_MINIMAL_BUILD_MODE"
_HEADER = "x-cutctx-minimal-build"
_VALID_MODES = {"lite", "full", "ultra"}
_INSTRUCTION_MARKER = "Cutctx minimal-build mode"


def resolve_minimal_build_mode(headers: Mapping[str, str] | None = None) -> str | None:
    """Return the resolved minimal-build mode, or ``None`` when disabled."""
    header_value = ""
    if headers is not None:
        header_value = str(headers.get(_HEADER, "")).strip().lower()
    if header_value in _VALID_MODES:
        return header_value
    if header_value in {"0", "false", "off", "disabled"}:
        return None
    if header_value in {"1", "true", "on", "enabled", "yes"}:
        return _normalize_mode(os.environ.get(_MODE_ENV))

    env_enabled = str(os.environ.get(_ENABLE_ENV, "")).strip().lower()
    if env_enabled not in {"1", "true", "on", "enabled", "yes"}:
        return None
    return _normalize_mode(os.environ.get(_MODE_ENV))


def apply_minimal_build_to_openai_body(body: dict[str, Any], mode: str) -> bool:
    """Inject minimal-build guidance into an OpenAI-compatible request body."""
    instruction = build_minimal_build_instruction(mode)
    system = body.get("system")
    if _append_instruction_to_prompt_container(system, instruction):
        return True

    messages = body.get("messages")
    if isinstance(messages, list):
        for message in messages:
            if not isinstance(message, dict):
                continue
            if message.get("role") not in {"system", "developer"}:
                continue
            if _append_instruction_to_message(message, instruction):
                return True
        messages.insert(0, {"role": "system", "content": instruction})
        return True

    body["system"] = instruction
    return True


def apply_minimal_build_to_anthropic_body(body: dict[str, Any], mode: str) -> bool:
    """Inject minimal-build guidance into an Anthropic-compatible request body."""
    instruction = build_minimal_build_instruction(mode)
    system = body.get("system")
    if system is None:
        body["system"] = instruction
        return True
    if _append_instruction_to_prompt_container(system, instruction):
        return True
    body["system"] = f"{system}\n\n{instruction}"
    return True


def build_minimal_build_instruction(mode: str) -> str:
    """Return the instruction block for the resolved mode."""
    normalized = _normalize_mode(mode)
    intensity = {
        "lite": "Bias toward smaller solutions when they fully solve the task.",
        "full": "Prefer the smallest sufficient implementation unless requirements clearly need more.",
        "ultra": "Act like an aggressively minimal senior engineer: ship the smallest correct solution and stop there.",
    }[normalized]
    extra = {
        "lite": "Avoid introducing new libraries or abstractions unless they remove clear repeated pain.",
        "full": "Reuse existing codepaths, platform features, and standard library tools before creating new layers.",
        "ultra": "Default to editing the nearest existing codepath, avoid speculative architecture, and reject gold-plating.",
    }[normalized]
    return (
        f"{_INSTRUCTION_MARKER} ({normalized}).\n"
        f"{intensity}\n"
        "Before building something new, check whether the repository already has a working pattern to extend.\n"
        "Prefer native platform capabilities, existing utilities, and one-file changes over new frameworks or helpers.\n"
        f"{extra}\n"
        "Stop once the first correct, maintainable solution is in place; do not add optional extras unless the task explicitly asks for them."
    )


def _normalize_mode(value: str | None) -> str:
    if value:
        lowered = value.strip().lower()
        if lowered in _VALID_MODES:
            return lowered
    return "full"


def _append_instruction_to_message(message: dict[str, Any], instruction: str) -> bool:
    content = message.get("content")
    if isinstance(content, str):
        if _INSTRUCTION_MARKER in content:
            return False
        message["content"] = f"{content}\n\n{instruction}" if content else instruction
        return True
    return _append_instruction_to_prompt_container(content, instruction)


def _append_instruction_to_prompt_container(container: Any, instruction: str) -> bool:
    if isinstance(container, str):
        if _INSTRUCTION_MARKER in container:
            return False
        return False
    if not isinstance(container, list):
        return False
    for block in container:
        if not isinstance(block, dict):
            continue
        if block.get("type") == "text" and isinstance(block.get("text"), str):
            if _INSTRUCTION_MARKER in block["text"]:
                return False
            block["text"] = f"{block['text']}\n\n{instruction}" if block["text"] else instruction
            return True
    container.append({"type": "text", "text": instruction})
    return True
