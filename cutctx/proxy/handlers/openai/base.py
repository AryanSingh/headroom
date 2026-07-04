"""OpenAI handler mixin for CutctxProxy.

Contains all OpenAI Chat Completions, Responses API, and passthrough handlers.
"""

from __future__ import annotations

import logging
import threading
from concurrent.futures import ThreadPoolExecutor
from typing import TYPE_CHECKING, Any

from cutctx.proxy.helpers import (
    _cutctx_bypass_enabled,
)

if TYPE_CHECKING:
    pass


logger = logging.getLogger("cutctx.proxy")

_OPENAI_RESPONSES_UNIT_CACHE_MAX_ENTRIES = 10_000
_OPENAI_RESPONSES_UNIT_CACHE_VERSION = "openai_responses_unit_v1"
_OPENAI_RESPONSES_UNIT_PARALLELISM_ENV = "CUTCTX_TOOL_OUTPUT_COMPRESSION_PARALLELISM"
_OPENAI_RESPONSES_UNIT_PARALLELISM_DEFAULT = 4
_OPENAI_RESPONSES_UNIT_PARALLELISM_MAX = 16
_OPENAI_RESPONSES_UNIT_CACHE_INIT_LOCK = threading.RLock()
_OPENAI_RESPONSES_UNIT_EXECUTOR_LOCK = threading.RLock()
_OPENAI_RESPONSES_UNIT_EXECUTOR: ThreadPoolExecutor | None = None

from cutctx.proxy.handlers.openai.utils import *  # noqa: E402, F403


class OpenAIBaseMixin:
    OPENAI_RESPONSES_ROUTER_MIN_BYTES = 512

    OPENAI_RESPONSES_OUTPUT_TYPES = {
        "custom_tool_call_output",
        "function_call_output",
        "local_shell_call_output",
        "apply_patch_call_output",
    }

    @staticmethod
    def _cutctx_bypass_enabled(headers: Any) -> bool:
        """Return True when inbound headers request full passthrough."""
        return _cutctx_bypass_enabled(headers)

    @staticmethod
    def _strict_previous_turn_frozen_count(
        messages: list[dict[str, Any]],
        base_frozen_count: int,
    ) -> int:
        """Freeze all prior turns in cache mode; only final user turn is mutable."""
        if not messages:
            return base_frozen_count
        final_idx = len(messages) - 1
        if messages[final_idx].get("role") == "user":
            return max(base_frozen_count, final_idx)
        return len(messages)

    @staticmethod
    def _restore_frozen_prefix(
        original_messages: list[dict[str, Any]],
        candidate_messages: list[dict[str, Any]],
        *,
        frozen_message_count: int,
    ) -> tuple[list[dict[str, Any]], int]:
        """Force frozen prefix bytes to match original request exactly."""
        if frozen_message_count <= 0 or not original_messages:
            return candidate_messages, 0

        frozen = min(frozen_message_count, len(original_messages))
        restored = list(candidate_messages)

        if len(restored) < frozen:
            return list(original_messages[:frozen]) + restored, frozen

        changed = 0
        for idx in range(frozen):
            if restored[idx] != original_messages[idx]:
                restored[idx] = original_messages[idx]
                changed += 1
        return restored, changed
