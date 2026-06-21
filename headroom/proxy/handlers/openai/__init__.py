"""OpenAI handler mixin for CutctxProxy.

Contains all OpenAI Chat Completions, Responses API, and passthrough handlers.
"""

from __future__ import annotations

import asyncio
import base64
import contextlib
import copy
import hashlib
import json
import logging
import os
import threading
import time
import uuid
from collections import OrderedDict
from concurrent.futures import ThreadPoolExecutor, as_completed
from dataclasses import replace
from datetime import datetime
from typing import TYPE_CHECKING, Any

from headroom.proxy.helpers import (
    COMPRESSION_TIMEOUT_SECONDS,
    _headroom_bypass_enabled,
    extract_tags,
    jitter_delay_ms,
)
from headroom.proxy.stage_timer import StageTimer, emit_stage_timings_log
from headroom.proxy.ws_session_registry import (
    TerminationCause,
    WebSocketSessionRegistry,
    WSSessionHandle,
)

if TYPE_CHECKING:
    from fastapi import Request, WebSocket
    from fastapi.responses import JSONResponse, Response, StreamingResponse

import httpx

from headroom.copilot_auth import apply_copilot_api_auth, build_copilot_upstream_url
from headroom.pipeline import PipelineStage, summarize_routing_markers
from headroom.proxy.auth_mode import classify_auth_mode, classify_client
from headroom.proxy.compression_decision import CompressionDecision
from headroom.proxy.cost import _summarize_transforms, header_safe_transforms
from headroom.proxy.outcome import RequestOutcome
from headroom.proxy.project_context import classify_project, set_current_project

logger = logging.getLogger("headroom.proxy")

_OPENAI_RESPONSES_UNIT_CACHE_MAX_ENTRIES = 10_000
_OPENAI_RESPONSES_UNIT_CACHE_VERSION = "openai_responses_unit_v1"
_OPENAI_RESPONSES_UNIT_PARALLELISM_ENV = "HEADROOM_TOOL_OUTPUT_COMPRESSION_PARALLELISM"
_OPENAI_RESPONSES_UNIT_PARALLELISM_DEFAULT = 4
_OPENAI_RESPONSES_UNIT_PARALLELISM_MAX = 16
_OPENAI_RESPONSES_UNIT_CACHE_INIT_LOCK = threading.RLock()
_OPENAI_RESPONSES_UNIT_EXECUTOR_LOCK = threading.RLock()
_OPENAI_RESPONSES_UNIT_EXECUTOR: ThreadPoolExecutor | None = None

from headroom.proxy.handlers.openai.base import OpenAIBaseMixin
from headroom.proxy.handlers.openai.chat import OpenAIChatMixin
from headroom.proxy.handlers.openai.compress import OpenAICompressMixin
from headroom.proxy.handlers.openai.passthrough import OpenAIPassthroughMixin
from headroom.proxy.handlers.openai.responses import OpenAIResponsesMixin
from headroom.proxy.handlers.openai.utils import (
    _CODEX_COMPRESSION_DEBUG_NOOP,
    _OPENAI_RESPONSES_UNIT_CACHE_INIT_LOCK,
    _OPENAI_RESPONSES_UNIT_CACHE_MAX_ENTRIES,
    _OPENAI_RESPONSES_UNIT_CACHE_VERSION,
    _OPENAI_RESPONSES_UNIT_EXECUTOR_LOCK,
    _OPENAI_RESPONSES_UNIT_PARALLELISM_DEFAULT,
    _OPENAI_RESPONSES_UNIT_PARALLELISM_ENV,
    _OPENAI_RESPONSES_UNIT_PARALLELISM_MAX,
    _OPENAI_TOOL_SCHEMA_DROP_KEYS,
    RESPONSES_CONTEXT_SEARCH_TIMEOUT_SECONDS,
    WS_FIRST_FRAME_TIMEOUT_SECONDS,
    _codex_compression_debug_enabled,
    _codex_ws_text_shape,
    _compact_openai_responses_tools,
    _compact_openai_tool_schema_value,
    _decode_openai_bearer_payload,
    _extract_codex_handshake_headers,
    _extract_responses_usage,
    _infer_openai_cache_write_tokens,
    _json_byte_len,
    _json_debug_dumps,
    _json_shape,
    _log_codex_compression_debug,
    _openai_responses_context_budget,
    _openai_responses_result_with_cache_hit,
    _openai_responses_unit_cache_key,
    _openai_responses_unit_executor,
    _openai_responses_unit_parallelism,
    _passthrough_model_from_path,
    _passthrough_usage_from_json,
    _resolve_codex_routing_headers,
    _responses_input_item_text_bytes,
    _routing_log_debug,
    _usage_int,
    logger,
)


class OpenAIHandlerMixin(
    OpenAIChatMixin,
    OpenAIResponsesMixin,
    OpenAIPassthroughMixin,
    OpenAICompressMixin,
    OpenAIBaseMixin
):
    pass
