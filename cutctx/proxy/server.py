"""Cutctx Proxy Server - Production Ready.

A full-featured LLM proxy with optimization, caching, rate limiting,
and observability.

Features:
- Context optimization (SmartCrusher, CacheAligner — live-zone-only after Phase B)
- Semantic caching (save costs on repeated queries)
- Rate limiting (token bucket)
- Retry with exponential backoff
- Cost tracking and budgets
- Request tagging and metadata
- Provider fallback
- Prometheus metrics
- Full request/response logging

Usage:
    python -m cutctx.proxy.server --port 8787

    # With Claude Code:
    ANTHROPIC_BASE_URL=http://localhost:8787 claude
    """

from __future__ import annotations

import argparse
import asyncio
import concurrent.futures
import contextlib
import importlib.util
import json
import logging
import os
import sys
import threading
import time
from dataclasses import fields, is_dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import TYPE_CHECKING, Any, Literal, cast

if TYPE_CHECKING:
    from ..backends.base import Backend
    from ..cache.compression_cache import CompressionCache
    from ..memory.tracker import MemoryTracker
    from .outcome import RequestOutcome


import socket

import httpx

try:
    import uvicorn
    from fastapi import Depends, FastAPI, HTTPException, Request, Response
    from fastapi.middleware.cors import CORSMiddleware
    from fastapi.responses import (
        FileResponse,
        HTMLResponse,
        JSONResponse,
        PlainTextResponse,
        StreamingResponse,
    )
    from fastapi.staticfiles import StaticFiles

    FASTAPI_AVAILABLE = True
except ImportError:
    FASTAPI_AVAILABLE = False

# Add parent to path for imports
sys.path.insert(0, str(Path(__file__).parent.parent.parent))

from cutctx._version import __version__
from cutctx.agent_savings import proxy_pipeline_kwargs
from cutctx.cache.compression_feedback import get_compression_feedback
from cutctx.cache.compression_store import get_compression_store
from cutctx.ccr import (
    CCRResponseHandler,
    CCRToolInjector,
    ContextTracker,
    ContextTrackerConfig,
    ResponseHandlerConfig,
)
from cutctx.checkout import checkout_url, upgrade_url
from cutctx.config import (
    DEFAULT_EXCLUDE_TOOLS,
    CacheAlignerConfig,
    ReadLifecycleConfig,
)
from cutctx.dashboard import get_dashboard_html
from cutctx.graph.resolver import StackGraphResolver, stack_graph_available
from cutctx.observability import (
    LangfuseTracingConfig,
    OTelMetricsConfig,
    configure_langfuse_tracing,
    configure_otel_metrics,
    get_langfuse_tracing_status,
    get_otel_metrics_status,
    shutdown_cutctx_tracing,
    shutdown_otel_metrics,
)
from cutctx.pipeline import PipelineExtensionManager, PipelineStage
from cutctx.providers.proxy_routes import register_provider_routes
from cutctx.providers.registry import (
    DEFAULT_ANTHROPIC_API_URL,
    DEFAULT_CLOUDCODE_API_URL,
    DEFAULT_GEMINI_API_URL,
    DEFAULT_OPENAI_API_URL,
    DEFAULT_VERTEX_API_URL,
    build_proxy_provider_runtime,
    create_proxy_backend,
    format_backend_status,
    resolve_api_targets,
)

# =============================================================================
# Extracted modules (re-exported for backward compatibility)
# =============================================================================
from cutctx.proxy.cost import (
    _CACHE_ECONOMICS,  # noqa: F401
    CostTracker,  # noqa: F401
    _summarize_transforms,  # noqa: F401
    build_prefix_cache_stats,  # noqa: F401
    build_session_summary,  # noqa: F401
    merge_cost_stats,  # noqa: F401
)
from cutctx.proxy.helpers import (
    COMPRESSION_TIMEOUT_SECONDS,  # noqa: F401
    MAX_COMPRESSION_CACHE_SESSIONS,  # noqa: F401
    MAX_MESSAGE_ARRAY_LENGTH,  # noqa: F401
    MAX_REQUEST_BODY_SIZE,  # noqa: F401
    MAX_SSE_BUFFER_SIZE,  # noqa: F401
    _get_context_tool_stats,
    _get_image_compressor,  # noqa: F401
    _get_rtk_stats,  # noqa: F401
    _read_request_json,  # noqa: F401
    _setup_file_logging,  # noqa: F401
    initialize_context_tool_session_baseline,
    is_anthropic_auth,  # noqa: F401
    jitter_delay_ms,
)
from cutctx.proxy.memory_handler import MemoryConfig, MemoryHandler
from cutctx.proxy.minimal_build import (
    apply_minimal_build_to_anthropic_body,
    apply_minimal_build_to_openai_body,
    resolve_minimal_build_mode,
)

# Data models (extracted to cutctx/proxy/models.py for maintainability)
from cutctx.proxy.models import CacheEntry, ProxyConfig, RateLimitState, RequestLog  # noqa: F401
from cutctx.proxy.modes import (
    PROXY_MODE_CACHE,
    PROXY_MODE_TOKEN,
    is_token_mode,
    normalize_proxy_mode,
)
from cutctx.proxy.probe_recorder import probe_recorder_from_env
from cutctx.proxy.project_context import (
    classify_project,
    set_current_project,
    strip_project_path_prefix,
)
from cutctx.proxy.prometheus_metrics import PrometheusMetrics  # noqa: F401
from cutctx.proxy.rate_limiter import TokenBucketRateLimiter  # noqa: F401
from cutctx.proxy.request_logger import RequestLogger  # noqa: F401
from cutctx.proxy.semantic_cache import SemanticCache  # noqa: F401
from cutctx.proxy.ssl_context import find_ca_bundle
from cutctx.proxy.warmup import WarmupRegistry
from cutctx.proxy.ws_session_registry import WebSocketSessionRegistry
from cutctx.savings import SavingsSource
from cutctx.subscription.base import get_quota_registry, reset_quota_registry
from cutctx.subscription.codex_rate_limits import get_codex_rate_limit_state
from cutctx.subscription.copilot_quota import get_copilot_quota_tracker
from cutctx.subscription.tracker import (
    configure_subscription_tracker,
)
from cutctx.telemetry import get_telemetry_collector
from cutctx.telemetry.beacon import is_telemetry_enabled
from cutctx.telemetry.toin import get_toin
from cutctx.transforms import (
    CacheAligner,
    CodeAwareCompressor,
    CodeCompressorConfig,
    CompressionStrategy,
    ContentRouter,
    ContentRouterConfig,
    TransformPipeline,
    is_tree_sitter_available,
)

AnyLLMBackend: Any = None
LiteLLMBackend: Any = None

fcntl: Any = None
try:
    import fcntl as _fcntl

    fcntl = _fcntl
    HAS_FCNTL = True
except ImportError:
    HAS_FCNTL = False

_build_prefix_cache_stats = build_prefix_cache_stats
_build_session_summary = build_session_summary
_merge_cost_stats = merge_cost_stats


logging.basicConfig(
    level=logging.INFO, format="%(asctime)s - %(name)s - %(levelname)s - %(message)s"
)
logger = logging.getLogger("cutctx.proxy")

_MULTI_WORKER_CONFIG_ENV = "CUTCTX_PROXY_CONFIG_JSON"

_INTERCEPT_BYPASS_IPS_FILE = Path.home() / ".cutctx" / "intercept_bypass_ips.json"
_original_getaddrinfo = socket.getaddrinfo
_intercept_bypass_applied = False

# Loopback-only auth bypass: restricted to specific read-only endpoints
# that legitimately need no auth from localhost dashboard access.
_LOOPBACK_OPEN_PATHS = frozenset({"/livez", "/readyz", "/metrics"})


def _patch_getaddrinfo_for_intercept() -> None:
    """Patch socket.getaddrinfo so the proxy's own outbound connections bypass /etc/hosts.

    When `cutctx intercept install` is active, /etc/hosts redirects AI API
    domains (api.anthropic.com, api.openai.com) to 127.0.0.1, and pfctl
    forwards port 443 → 8787. Without this patch the proxy's own upstream
    httpx calls loop back to itself.

    The fix: read the real IPs that were resolved *before* /etc/hosts was
    modified (saved by `cutctx intercept install`), and substitute them so
    the proxy connects directly to the real servers while clients (Claude
    Desktop, Node.js) still go through the redirect.
    """
    global _intercept_bypass_applied
    if _intercept_bypass_applied:
        return
    if not _INTERCEPT_BYPASS_IPS_FILE.exists():
        return

    try:
        bypass_ips: dict[str, str] = json.loads(_INTERCEPT_BYPASS_IPS_FILE.read_text())
    except Exception:
        return
    if not bypass_ips:
        return

    def _patched_getaddrinfo(host, port, family=0, type=0, proto=0, flags=0):  # noqa: A002
        real_ip = bypass_ips.get(host) if isinstance(host, str) else None
        if real_ip:
            return _original_getaddrinfo(real_ip, port, family, type, proto, flags)
        return _original_getaddrinfo(host, port, family, type, proto, flags)

    socket.getaddrinfo = _patched_getaddrinfo
    _intercept_bypass_applied = True
    logger.info(
        "Intercept bypass active: %d domain(s) routed directly (%s)",
        len(bypass_ips),
        ", ".join(bypass_ips),
    )

# Env var that opts out of the Rust core deployment smoke test (Hotfix-A0).
# Default behavior: hard-fail at startup if `cutctx._core` is unimportable
# (Finding #2 in CUTCTX_PROXY_LOG_FINDINGS_2026_05_03.md — production
# deployment was silently running without the Rust extension and degrading
# every compressed request to a Python-only path or a no-op).
#
# Set to the literal string "false" to start the proxy in degraded
# Python-only mode. Any other value (including unset) keeps the
# fail-loud behavior.
_RUST_CORE_REQUIRED_ENV = "CUTCTX_REQUIRE_RUST_CORE"

# sysexits.h(3) — EX_CONFIG. Process supervisors (systemd, k8s, docker)
# treat this as a deliberate configuration failure rather than a crash, so
# they won't restart-loop on a broken deployment.
_EXIT_CONFIG = 78


def _check_rust_core() -> tuple[str, str | None]:
    """Verify the Rust extension `cutctx._core` is loadable at startup.

    Returns a `(status, error)` tuple:
      - ``("loaded", None)``     — `cutctx._core.hello()` returned the
        expected sentinel.
      - ``("disabled", reason)`` — opt-out env var was set; proxy starts
        in Python-only degraded mode. `reason` carries the underlying
        import error (or ``None`` if the import actually succeeded).
      - ``("missing", reason)``  — never returned: this branch calls
        ``sys.exit(78)`` so the proxy refuses to start. The branch exists
        only as a typed sentinel for callers that want to reason about
        all three states (e.g. health endpoints).

    Behavior is gated by the ``CUTCTX_REQUIRE_RUST_CORE`` env var:
    any value other than ``"false"`` (case-insensitive) keeps the
    fail-loud default.
    """
    require = os.environ.get(_RUST_CORE_REQUIRED_ENV, "true").strip().lower() != "false"
    try:
        from cutctx._core import hello as _rust_hello

        marker = _rust_hello()
    except Exception as exc:  # ImportError, but also any init-time PyO3 failure
        reason = f"{type(exc).__name__}: {exc}"
        if not require:
            logger.warning(
                "event=rust_core_disabled reason=%r opt_out_env=%s=false mode=python_only_degraded",
                reason,
                _RUST_CORE_REQUIRED_ENV,
            )
            return ("disabled", reason)
        # Fail loud. Print to stderr in addition to logging so operators
        # see it even if the logging handler is mis-configured.
        msg = (
            f"FATAL: Rust extension `cutctx._core` not loadable.\n"
            f"    error: {reason}\n"
            f"    fix:   `make build-wheel && pip install --force-reinstall "
            f"target/wheels/cutctx_*.whl`\n"
            f"    opt-out: set {_RUST_CORE_REQUIRED_ENV}=false to start in "
            f"degraded Python-only mode\n"
        )
        logger.error("event=rust_core_missing reason=%r action=exit_78", reason)
        print(msg, file=sys.stderr, flush=True)
        sys.exit(_EXIT_CONFIG)

    # Import succeeded; sanity-check the marker so we catch a stale or
    # mis-linked .so where the symbol name resolves but returns garbage.
    if marker != "cutctx-core":
        reason = f"unexpected marker {marker!r}"
        if not require:
            logger.warning(
                "event=rust_core_disabled reason=%r opt_out_env=%s=false",
                reason,
                _RUST_CORE_REQUIRED_ENV,
            )
            return ("disabled", reason)
        msg = (
            f"FATAL: Rust extension `cutctx._core` is loaded but the "
            f"marker function returned {marker!r}; expected 'cutctx-core'.\n"
            f"    fix:   rebuild: `make build-wheel && pip install "
            f"--force-reinstall target/wheels/cutctx_*.whl`\n"
        )
        logger.error("event=rust_core_marker_mismatch marker=%r action=exit_78", marker)
        print(msg, file=sys.stderr, flush=True)
        sys.exit(_EXIT_CONFIG)

    logger.info("event=rust_core_loaded marker=%r", marker)
    return ("loaded", None)


# Compression pipeline timeout in seconds


from cutctx.proxy.handlers import (  # noqa: E402
    AnthropicHandlerMixin,
    BatchHandlerMixin,
    GeminiHandlerMixin,
    OpenAIHandlerMixin,
    StreamingMixin,
)


class CutctxProxy(
    StreamingMixin,
    AnthropicHandlerMixin,
    OpenAIHandlerMixin,
    GeminiHandlerMixin,
    BatchHandlerMixin,
):
    """Production-ready Cutctx optimization proxy."""

    ANTHROPIC_API_URL = DEFAULT_ANTHROPIC_API_URL
    OPENAI_API_URL = DEFAULT_OPENAI_API_URL
    GEMINI_API_URL = DEFAULT_GEMINI_API_URL
    CLOUDCODE_API_URL = DEFAULT_CLOUDCODE_API_URL
    VERTEX_API_URL = DEFAULT_VERTEX_API_URL

    def __init__(self, config: ProxyConfig):
        self.config = config
        self.config.mode = normalize_proxy_mode(self.config.mode)
        pipeline_extensions = list(config.pipeline_extensions or [])
        probe_recorder = probe_recorder_from_env()
        if probe_recorder is not None:
            pipeline_extensions.append(probe_recorder)
        self.pipeline_extensions = PipelineExtensionManager(
            hooks=config.hooks,
            extensions=pipeline_extensions,
            discover=config.discover_pipeline_extensions,
        )

        from cutctx.proxy.intelligence_pipeline import IntelligencePipeline

        # Keep intelligence features stateful across requests so feedback-driven
        # controls can adapt without restarting the proxy.
        self.intelligence_pipeline = IntelligencePipeline.from_config(config)
        self.provider_runtime = build_proxy_provider_runtime(config)
        api_targets = self.provider_runtime.api_targets

        # Preserve the long-standing proxy compatibility surface while keeping
        # provider_runtime as the source of truth for resolved upstream targets.
        CutctxProxy.ANTHROPIC_API_URL = api_targets.anthropic
        CutctxProxy.OPENAI_API_URL = api_targets.openai
        CutctxProxy.GEMINI_API_URL = api_targets.gemini
        CutctxProxy.CLOUDCODE_API_URL = api_targets.cloudcode
        CutctxProxy.VERTEX_API_URL = api_targets.vertex
        self.anthropic_provider = self.provider_runtime.pipeline_provider("anthropic")
        self.openai_provider = self.provider_runtime.pipeline_provider("openai")

        # `metrics` is hoisted ahead of transform construction so the
        # transforms can receive `self.metrics` as their compression
        # observer at __init__ time. The forcing function for catching
        # silent strategy regressions: per-strategy counters increment
        # only when wired up here, so the wiring is mandatory, not
        # something we patch in later. (See `RUST_DEV.md` audit notes.)
        self.cost_tracker = (
            CostTracker(
                budget_limit_usd=config.budget_limit_usd,
                budget_period=config.budget_period,
            )
            if config.cost_tracking_enabled
            else None
        )
        self.metrics = PrometheusMetrics(cost_tracker=self.cost_tracker)

        # Initialize transforms based on routing mode.
        #
        # Phase B PR-B1 retired the IntelligentContextManager / RollingWindow
        # message-dropping branch. Live-zone-only compression (PR-B2..B7) does
        # not drop messages — it operates on content blocks within messages —
        # so the proxy no longer needs a "context manager" transform stage.
        # Reported via metrics as `_context_manager_status = "passthrough"`.
        self._context_manager_status = "passthrough"

        # ContentRouter is the single proxy routing surface. Provider handlers
        # normalize their request shapes into messages or CompressionUnits, and
        # the router chooses SmartCrusher, log/search/diff/code, or Kompress.
        profile_kwargs = proxy_pipeline_kwargs(config)
        router_config = ContentRouterConfig(
            enable_code_aware=config.code_aware_enabled,
            tool_profiles=config.tool_profiles,
            read_lifecycle=ReadLifecycleConfig(enabled=config.read_lifecycle),
            ccr_inject_marker=config.ccr_inject_marker,
            smart_crusher_max_items_after_crush=cast(
                int | None,
                profile_kwargs.get("max_items_after_crush"),
            ),
            smart_crusher_with_compaction=cast(
                bool,
                profile_kwargs.get("smart_crusher_with_compaction", True),
            ),
            query_aware_compression=config.query_aware_compression,
        )
        if config.disable_kompress:
            router_config.enable_kompress = False
            router_config.fallback_strategy = CompressionStrategy.PASSTHROUGH
        # Selective filter: forward ProxyConfig toggle + threshold to ContentRouterConfig
        if getattr(config, "selective_filter", False):
            router_config.selective_filter = True
            router_config.selective_filter_min_score = getattr(
                config, "selective_filter_threshold", 0.15
            )
        # Drain3: forward ProxyConfig toggle + config to ContentRouterConfig
        if getattr(config, "drain3_enabled", False):
            router_config.use_drain3 = True
            router_config.drain3_max_clusters = getattr(config, "drain3_max_clusters", 1000)
            router_config.drain3_sim_threshold = getattr(config, "drain3_sim_threshold", 0.4)
        # A non-None exclude_tools replaces DEFAULT_EXCLUDE_TOOLS in
        # ContentRouter, so merge rather than assign.
        if config.exclude_tools:
            router_config.exclude_tools = set(DEFAULT_EXCLUDE_TOOLS) | config.exclude_tools
        # Token mode: allow compression of older excluded-tool results.
        if is_token_mode(config.mode):
            router_config.protect_recent_reads_fraction = 0.3
        # `--compress-user-messages` flips the router's default skip rule.
        # Off by default for prefix-cache safety; enabled for workloads where
        # user-message content dominates input (OpenAI/Azure chat with pasted
        # code/RAG context — see issue #454).
        if profile_kwargs.get("compress_user_messages"):
            router_config.skip_user_messages = False
        # Wire the intelligence pipeline's profile recommendations into the
        # router config so ContentRouter can consume them via per_type_overrides.
        # Best-effort: if the profile is not yet available, no overrides are set
        # and existing behaviour is unchanged.
        try:
            from cutctx.profiles import CompressionProfile

            _profile = CompressionProfile.load()
            if _profile and _profile.stats:
                _content_type_overrides: dict[str, dict[str, Any]] = {}
                for _ct, _stats in _profile.stats.items():
                    _content_type_overrides[_ct] = {
                        "recommended_ratio": _stats.recommended_ratio,
                    }
                router_config.per_type_overrides = _content_type_overrides
                logger.debug(
                    "Wired %d content type overrides from profile into router config",
                    len(_content_type_overrides),
                )
        except Exception:
            pass  # Profile not available — no overrides, existing behaviour unchanged
        content_router = ContentRouter(router_config, observer=self.metrics)
        # Wire difftastic runtime flags so the router's _get_diff_compressor
        # can branch to DifftasticBackend when enabled.
        content_router._runtime_difftastic_enabled = config.difftastic_enabled
        content_router._runtime_difftastic_binary = config.difftastic_binary
        content_router._runtime_difftastic_context_lines = config.difftastic_context_lines
        self._content_router = content_router
        from cutctx.proxy.interceptors import ToolResultInterceptorTransform

        transforms = [
            CacheAligner(CacheAlignerConfig(enabled=config.cache_aligner_enabled)),
            ToolResultInterceptorTransform(),
            content_router,
        ]
        self._code_aware_status = "lazy" if config.code_aware_enabled else "disabled"

        self.anthropic_pipeline = TransformPipeline(
            transforms=transforms,
            provider=self.anthropic_provider,
        )
        self.openai_pipeline = TransformPipeline(
            transforms=transforms,
            provider=self.openai_provider,
        )

        # Initialize components
        self.cache = (
            SemanticCache(
                max_entries=config.cache_max_entries,
                ttl_seconds=config.cache_ttl_seconds,
            )
            if config.cache_enabled
            else None
        )

        self.rate_limiter = (
            TokenBucketRateLimiter(
                requests_per_minute=config.rate_limit_requests_per_minute,
                tokens_per_minute=config.rate_limit_tokens_per_minute,
            )
            if config.rate_limit_enabled
            else None
        )

        # `cost_tracker` and `metrics` were hoisted to before transforms so
        # ContentRouter / SmartCrusher could take `self.metrics` as their
        # compression observer at __init__ time.

        # Prefix cache tracking: freeze already-cached messages to avoid
        # invalidating the provider's prefix cache with our transforms
        from cutctx.cache.prefix_tracker import PrefixFreezeConfig, SessionTrackerStore

        self.session_tracker_store = SessionTrackerStore(
            default_config=PrefixFreezeConfig(
                enabled=config.prefix_freeze_enabled,
                session_ttl_seconds=config.prefix_freeze_session_ttl,
            )
        )

        # Compression cache store for token mode (session-scoped). The dict
        # itself is mutated under `_compression_caches_lock`; the per-session
        # `CompressionCache` instances have their own internal lock guarding
        # `_cache`/`_stable_hashes`/`_first_seen` against concurrent
        # async-dispatched requests for the same session.
        self._compression_caches: dict[str, CompressionCache] = {}
        self._compression_caches_lock = threading.RLock()

        self.logger = (
            RequestLogger(
                log_file=config.log_file,
                log_full_messages=config.log_full_messages,
            )
            if config.log_requests
            else None
        )

        # Enterprise security plugin (loaded dynamically if available + licensed)
        self.security = None

        # HTTP client
        self.http_client: httpx.AsyncClient | None = None

        # Shared cold-start warmup registry (populated by startup()).
        # Holds typed slots with loaded / loading / null / error status for
        # each preloaded heavy asset. Exposed as ``proxy.warmup`` and
        # serialized by the /debug/warmup route (Unit 5).
        self.warmup: WarmupRegistry = WarmupRegistry()
        # Unit 3: live registry of Codex WS sessions. Populated by
        # ``handle_openai_responses_ws`` on accept; drained in its
        # outermost ``finally``. Consumed by ``/debug/ws-sessions``.
        self.ws_sessions: WebSocketSessionRegistry = WebSocketSessionRegistry()

        # Unit 4: bounded pre-upstream concurrency for the Anthropic HTTP
        # path. Caps how many ``handle_anthropic_messages`` calls may be
        # running deep-copy / first-stage compression / memory-context
        # lookup / upstream connect concurrently. ``/livez``, ``/readyz``,
        # ``/health``, ``/metrics``, ``/stats``, and the Codex WS path are
        # intentionally NOT gated by this semaphore.
        #
        # A value of ``0`` or negative disables the semaphore (unbounded
        # mode); this is useful for the Unit 6 counter-factual where we
        # deliberately reproduce the original starvation. The default is
        # ``max(2, min(8, os.cpu_count() or 4))``.
        _pre_upstream_cfg = config.anthropic_pre_upstream_concurrency
        if _pre_upstream_cfg is None:
            _pre_upstream_resolved = max(2, min(8, os.cpu_count() or 4))
        else:
            _pre_upstream_resolved = _pre_upstream_cfg
        self.anthropic_pre_upstream_concurrency: int = _pre_upstream_resolved
        self.anthropic_pre_upstream_acquire_timeout_seconds = float(
            config.anthropic_pre_upstream_acquire_timeout_seconds
        )
        self.anthropic_pre_upstream_memory_context_timeout_seconds = float(
            config.anthropic_pre_upstream_memory_context_timeout_seconds
        )
        if _pre_upstream_resolved > 0:
            self.anthropic_pre_upstream_sem: asyncio.Semaphore | None = asyncio.Semaphore(
                _pre_upstream_resolved
            )
        else:
            self.anthropic_pre_upstream_sem = None

        # Dedicated compression executor — see C3 in the audit followup.
        # Replaces ``asyncio.to_thread(...)`` for ``pipeline.apply()`` calls
        # so that:
        #   1. Compression work is bounded — CPU-bound Rust runs here, and
        #      bursts cannot starve other ``asyncio.to_thread`` callers
        #      sharing the loop's default executor (file IO, etc.).
        #   2. Tasks that exceed ``COMPRESSION_TIMEOUT_SECONDS`` and complete
        #      *after* the asyncio future was cancelled are counted in the
        #      ``compression_leaked_threads`` gauge — Python cannot preempt
        #      the worker, so this is the only signal that some pool slots
        #      are sitting on stuck work.
        _compression_max_cfg = config.compression_max_workers
        if _compression_max_cfg is None:
            _compression_max = min(32, (os.cpu_count() or 1) * 4)
        else:
            _compression_max = max(1, _compression_max_cfg)
        self.compression_max_workers: int = _compression_max
        self._compression_executor = concurrent.futures.ThreadPoolExecutor(
            max_workers=_compression_max,
            thread_name_prefix="cutctx-compress",
        )
        # Gauge: currently-running compression tasks. Mutated under
        # ``_compression_metrics_lock`` from worker threads + the asyncio
        # event loop.
        self._compression_queued: int = 0
        self._compression_queued_max: int = 0
        self._compression_queue_timeouts: int = 0
        self._compression_queue_wait_seconds_total: float = 0.0
        self._compression_queue_wait_seconds_max: float = 0.0
        self._compression_in_flight: int = 0
        # High-water mark for in-flight count.
        self._compression_in_flight_max: int = 0
        self._compression_run_seconds_total: float = 0.0
        self._compression_run_seconds_max: float = 0.0
        # Counter: threads that finished AFTER their asyncio future hit the
        # timeout. Stuck-thread leak indicator.
        self._compression_leaked_threads: int = 0
        self._compression_metrics_lock = threading.Lock()

        # Backend for Anthropic API (direct, LiteLLM, or any-llm)
        # Supports: "anthropic" (direct), "bedrock", "vertex", "litellm-<provider>", or "anyllm"
        self.anthropic_backend: Backend | None = create_proxy_backend(
            backend=config.backend,
            anyllm_provider=config.anyllm_provider,
            bedrock_region=config.bedrock_region,
            logger=logger,
            anyllm_backend_cls=AnyLLMBackend,
            litellm_backend_cls=LiteLLMBackend,
        )

        # Request counter for IDs
        self._request_counter = 0
        self._request_counter_lock = asyncio.Lock()

        # CCR tool injectors (one per provider)
        self.anthropic_tool_injector = CCRToolInjector(
            provider="anthropic",
            inject_tool=config.ccr_inject_tool,
            inject_system_instructions=config.ccr_inject_system_instructions,
        )
        self.openai_tool_injector = CCRToolInjector(
            provider="openai",
            inject_tool=config.ccr_inject_tool,
            inject_system_instructions=config.ccr_inject_system_instructions,
        )

        # CCR Response Handler (handles CCR tool calls automatically)
        self.ccr_response_handler = (
            CCRResponseHandler(
                ResponseHandlerConfig(
                    enabled=True,
                    max_retrieval_rounds=config.ccr_max_retrieval_rounds,
                )
            )
            if config.ccr_handle_responses
            else None
        )

        # CCR Context Tracker (tracks compressed content across turns)
        self.ccr_context_tracker = (
            ContextTracker(
                ContextTrackerConfig(
                    enabled=True,
                    proactive_expansion=config.ccr_proactive_expansion,
                    max_proactive_expansions=config.ccr_max_proactive_expansions,
                )
            )
            if config.ccr_context_tracking
            else None
        )

        # Seed the global CCR compression store with the configured TTL so that
        # the singleton is created with the right default_ttl on first access.
        # get_compression_store() is idempotent once the store exists; calling it
        # here with default_ttl wins because the store hasn't been built yet.
        get_compression_store(default_ttl=config.ccr_store_ttl_seconds)

        # Turn counter for context tracking
        self._turn_counter = 0

        # Episodic Memory Session Tracker (file-backed cross-session memory)
        self.episodic_tracker = None
        if config.episodic_memory_enabled:
            from cutctx.memory.session_tracker import EpisodicSessionTracker
            from cutctx.memory.store import EpisodicMemoryStore

            _ep_store = EpisodicMemoryStore()
            self.episodic_tracker = EpisodicSessionTracker(
                _ep_store,
                idle_timeout_seconds=config.episodic_idle_timeout_seconds,
                extraction_model=config.episodic_extraction_model,
            )
            logger.info("Episodic Memory: ENABLED (idle timeout: %ds)", config.episodic_idle_timeout_seconds)

        # Memory Handler (persistent user memory)
        self.memory_handler: MemoryHandler | None = None
        if config.memory_enabled:
            # Resolve memory DB path: empty → project-scoped default
            _mem_db_path = config.memory_db_path
            if not _mem_db_path:
                _mem_dir = Path.cwd() / ".cutctx"
                _mem_dir.mkdir(parents=True, exist_ok=True)
                _mem_db_path = str(_mem_dir / "memory.db")
                logger.info(f"Memory: Project-scoped DB at {_mem_db_path}")

            # PR-B6: translate the string-typed ``ProxyConfig.memory_mode``
            # into the typed ``MemoryMode`` enum. Unknown values raise
            # loudly per the no-silent-fallback policy.
            from cutctx.proxy.memory_handler import MemoryMode

            try:
                _memory_mode = MemoryMode(config.memory_mode)
            except ValueError as exc:
                raise ValueError(
                    f"Invalid memory_mode={config.memory_mode!r}; "
                    f"expected one of {[m.value for m in MemoryMode]}"
                ) from exc

            from cutctx.memory.storage_router import MemoryStorageMode

            try:
                _storage_mode = MemoryStorageMode(config.memory_storage_mode)
            except ValueError as exc:
                raise ValueError(
                    f"Invalid memory_storage_mode={config.memory_storage_mode!r}; "
                    f"expected one of {[m.value for m in MemoryStorageMode]}"
                ) from exc

            memory_config = MemoryConfig(
                enabled=True,
                backend=config.memory_backend,
                db_path=_mem_db_path,
                inject_tools=config.memory_inject_tools,
                use_native_tool=config.memory_use_native_tool,
                inject_context=config.memory_inject_context,
                top_k=config.memory_top_k,
                min_similarity=config.memory_min_similarity,
                mode=_memory_mode,
                storage_mode=_storage_mode,
                project_root_override=config.memory_project_root_override,
                qdrant_url=config.memory_qdrant_url,
                qdrant_host=config.memory_qdrant_host,
                qdrant_port=config.memory_qdrant_port,
                qdrant_api_key=config.memory_qdrant_api_key,
                neo4j_uri=config.memory_neo4j_uri,
                neo4j_user=config.memory_neo4j_user,
                neo4j_password=config.memory_neo4j_password,
                bridge_enabled=config.memory_bridge_enabled,
                bridge_md_paths=config.memory_bridge_md_paths,
                bridge_md_format=config.memory_bridge_md_format,
                bridge_auto_import=config.memory_bridge_auto_import,
                bridge_export_path=config.memory_bridge_export_path,
            )
            self.memory_handler = MemoryHandler(
                memory_config,
                agent_type=config.traffic_learning_agent_type,
            )

            # Migration UX (GH #462). When the user is on the new
            # project-scoped default but a legacy single-file DB exists
            # with prior memories, surface that clearly so it doesn't
            # look like an upgrade ate their data.
            if _storage_mode is MemoryStorageMode.PROJECT:
                _legacy_path = Path(_mem_db_path)
                if _legacy_path.exists() and _legacy_path.stat().st_size > 0:
                    logger.info(
                        "event=memory_storage_legacy_detected path=%s mode=project "
                        "hint=pass_--memory-storage=global_to_reach_pre-fix_memories",
                        _legacy_path,
                    )

            # The Memory Bridge binds to the single legacy backend at
            # init time; it doesn't (yet) follow per-project routing.
            # Warn so users running bridge + project mode aren't
            # surprised that only the legacy DB syncs with markdown.
            if config.memory_bridge_enabled and _storage_mode is MemoryStorageMode.PROJECT:
                logger.warning(
                    "event=memory_bridge_global_only mode=project "
                    "hint=bridge_syncs_only_the_legacy_DB_today_per-project_bridge_follow-up_planned"
                )

        # Usage Reporter (license validation + phone-home for managed/enterprise)
        self.usage_reporter: UsageReporter | None = None
        if config.license_key:
            from cutctx.telemetry.reporter import UsageReporter

            self.usage_reporter = UsageReporter(
                license_key=config.license_key,
                cloud_url=config.license_cloud_url,
                report_interval=config.license_report_interval,
            )

        # Entitlement checker (feature gating by tier)
        from cutctx.entitlements import EntitlementChecker

        self.entitlement_checker = EntitlementChecker(
            plan=config.entitlement_tier,
        )

        # Audit logger (enterprise compliance — structured event logging)
        self.audit_logger = None
        if getattr(config, "audit_enabled", True):
            try:
                from cutctx.audit import get_audit_logger

                self.audit_logger = get_audit_logger(
                    db_path=getattr(config, "audit_db_path", None),
                )
            except Exception:
                logger.debug("Audit logger init failed", exc_info=True)

        # Org store (enterprise multi-tenant model)
        self.org_store = None
        if getattr(config, "org_enabled", True):
            try:
                from cutctx.org import get_org_store

                self.org_store = get_org_store(
                    db_path=getattr(config, "org_db_path", None),
                )
            except Exception:
                logger.debug("Org store init failed", exc_info=True)

        # Fleet registry (enterprise deployment inventory)
        self.fleet_store = None
        if getattr(config, "fleet_enabled", True):
            try:
                from cutctx.fleet import get_fleet_store

                self.fleet_store = get_fleet_store(
                    db_path=getattr(config, "fleet_db_path", None),
                )
            except Exception:
                logger.debug("Fleet store init failed", exc_info=True)

        # SCIM provisioning store (enterprise identity sync)
        self.scim_store = None
        if getattr(config, "scim_enabled", True):
            try:
                from cutctx.scim import get_scim_store

                self.scim_store = get_scim_store(
                    db_path=getattr(config, "scim_db_path", None),
                )
            except Exception:
                logger.debug("SCIM store init failed", exc_info=True)

        # Traffic Learner (live pattern extraction from proxy traffic)
        # Only activates with --learn flag; requires --memory for backend
        self.traffic_learner: TrafficLearner | None = None
        self.traffic_learning_agent_type: str = config.traffic_learning_agent_type
        if config.traffic_learning_enabled:
            from cutctx.memory.traffic_learner import TrafficLearner

            self.traffic_learner = TrafficLearner(
                user_id=os.environ.get("CUTCTX_USER_ID", os.environ.get("USER", "default")),
                agent_type=config.traffic_learning_agent_type,
                min_evidence=config.traffic_learning_min_evidence,
            )

        # Code graph file watcher (live reindex on file changes)
        self.code_graph_watcher: CodeGraphWatcher | None = None  # type: ignore[annotation-unchecked]
        if config.code_graph_watcher:
            from cutctx.graph.watcher import CodeGraphWatcher

            self.code_graph_watcher = CodeGraphWatcher(project_dir=Path.cwd())
            if self.code_graph_watcher.start():
                logger.info("Code graph: file watcher started")
            else:
                self.code_graph_watcher = None

        # Knowledge-graph compression (opt-in via --knowledge-graph)
        self.knowledge_graph_indexer = None
        self.knowledge_graph_status = {
            "requested": bool(config.knowledge_graph_enabled),
            "enabled": bool(config.knowledge_graph_enabled),
            "available": False,
            "active": False,
            "status": "disabled",
            "reason": None,
            "interceptor_registered": False,
        }
        if config.knowledge_graph_enabled:
            try:
                from cutctx.graph.graphify import (
                    GraphifyIndexer,
                    graphify_available,
                    networkx_available,
                    set_global_indexer,
                )
                from cutctx.proxy.interceptors import base as interceptors_base
                from cutctx.proxy.interceptors.graph_interceptor import GraphifyInterceptor

                if not graphify_available():
                    self.knowledge_graph_status.update(
                        status="unavailable",
                        reason="graphify_not_installed",
                    )
                    logger.warning("Knowledge graph engine requested (--knowledge-graph) but not installed. Install: pip install cutctx-ai[knowledge-graph]")
                elif not networkx_available():
                    self.knowledge_graph_status.update(
                        status="unavailable",
                        reason="networkx_not_installed",
                    )
                    logger.warning("Graph utilities required for knowledge graph not installed. Install: pip install cutctx-ai[knowledge-graph]")
                else:
                    indexer = GraphifyIndexer(
                        project_dir=Path.cwd(),
                        output_dir=config.knowledge_graph_output_dir,
                    )
                    indexer.start()
                    self.knowledge_graph_indexer = indexer
                    set_global_indexer(indexer)
                    interceptors_base.register(
                        GraphifyInterceptor(
                            bfs_depth=config.knowledge_graph_bfs_depth,
                            max_nodes=config.knowledge_graph_max_nodes,
                            min_chars=config.knowledge_graph_min_chars,
                        ),
                    )
                    self.knowledge_graph_status.update(
                        available=True,
                        active=indexer.get_index() is not None,
                        status="ready" if indexer.get_index() is not None else "building",
                        reason=None,
                        interceptor_registered=True,
                    )
                    logger.info("Knowledge graph: interceptor registered (bfs_depth=%d, max_nodes=%d)", config.knowledge_graph_bfs_depth, config.knowledge_graph_max_nodes)
            except Exception as exc:
                self.knowledge_graph_status.update(
                    status="degraded",
                    reason=exc.__class__.__name__,
                )
                logger.warning("Knowledge graph initialization degraded: %s", exc, exc_info=True)

        # Difftastic structural diff interceptor (opt-in)
        self._difftastic_enabled = config.difftastic_enabled
        self._difftastic_binary = config.difftastic_binary
        self._difftastic_context_lines = config.difftastic_context_lines
        if config.difftastic_enabled:
            from cutctx.binaries import find_difftastic

            difft_path = find_difftastic(config.difftastic_binary)
            if difft_path is None:
                logger.warning("Structural diff engine enabled but binary not found. Diff compression will fall back to DiffCompressor.")
            else:
                logger.info("Structural diff engine: binary resolved at %s", difft_path)
                from cutctx.proxy.interceptors import base as interceptors_base
                from cutctx.proxy.interceptors.difftastic_interceptor import DifftasticInterceptor

                interceptor = DifftasticInterceptor(
                    binary_path=str(difft_path),
                    context_lines=config.difftastic_context_lines,
                )
                interceptors_base.register(interceptor)
                logger.info("Structural diff engine interceptor registered (context_lines=%d)", config.difftastic_context_lines)

        # Stack-graph code navigation (optional)
        self.stack_graph_resolver = None
        if config.stack_graph_enabled:
            if not stack_graph_available():
                logger.warning(
                    "Stack-graph: Rust extension not available. "
                    "Run: maturin develop -m crates/cutctx-py/Cargo.toml"
                )
            else:
                try:
                    resolver = StackGraphResolver()
                    count = resolver.index_project(os.getcwd(), max_files=config.stack_graph_max_files)
                    self.stack_graph_resolver = resolver
                    # Wire incremental re-indexing through the file watcher
                    try:
                        from cutctx.graph.watcher import (
                            set_stack_graph_resolver as _set_sg_resolver,
                        )
                        _set_sg_resolver(resolver)
                    except ImportError:
                        pass  # Watcher module not available — incremental updates disabled
                    logger.info(
                        "Stack-graph: ENABLED — indexed %d files in %s",
                        count, os.getcwd(),
                    )
                except Exception:
                    logger.exception("Stack-graph: failed to initialize")
                    self.stack_graph_resolver = None

        # Wire stack-graph reachability into the code compressor via
        # the content router's pre-compress hook.
        if self.stack_graph_resolver is not None and hasattr(self, '_content_router'):
            resolver_for_hook = self.stack_graph_resolver
            router_for_hook = self._content_router
            # Set the hook on the config (used by ContentRouter.compress())
            router_for_hook.config.pre_compress_hook = (
                lambda _router, _content, _context: self._apply_stack_graph_to_compressor(
                    _router, _content, _context, resolver_for_hook,
                )
            )
            logger.info("Stack-graph: pre_compress_hook wired — reachable functions will be preserved")

        self.pipeline_extensions.emit(
            PipelineStage.SETUP,
            operation="proxy.setup",
            metadata={
                "mode": self.config.mode,
                "optimize": self.config.optimize,
                "backend": self.config.backend,
                "memory_enabled": self.config.memory_enabled,
            },
        )

    def _apply_stack_graph_to_compressor(
        self,
        router: Any,
        content: str,
        context: str,
        resolver: Any = None,
    ) -> None:
        """Extract entry points from user context and protect reachable symbols.

        Called as a pre-compress hook from the ContentRouter.  Resolves
        symbol names found in the context string through the stack graph
        and sets ``protected_symbols`` on the code compressor so that
        reachable functions keep their full bodies.
        """
        if resolver is None:
            resolver = getattr(self, "stack_graph_resolver", None)
        if resolver is None:
            return

        from cutctx.graph.reachability import resolve_entry_points

        # Use the compression context as the query — it typically
        # contains the most recent user message or task description.
        query = context or content[:200]
        if not query:
            return

        protected_symbols, _report = resolve_entry_points(
            resolver, query, max_depth=5,
        )

        if protected_symbols:
            # Find the code compressor and set protected symbols on it.
            code_compressor = router._get_code_compressor()
            if code_compressor is not None and hasattr(code_compressor, "set_protected_symbols"):
                code_compressor.set_protected_symbols(protected_symbols)
                logger.info(
                    "StackGraph: protecting %d symbols from %s",
                    len(protected_symbols),
                    query[:50],
                )

    async def _run_compression_in_executor(
        self,
        fn,  # noqa: ANN001 — caller-supplied no-arg sync callable
        *,
        timeout: float,
    ):
        """Run a synchronous compression callable on the bounded executor
        with cancel-aware metrics.

        Replaces ``asyncio.wait_for(asyncio.to_thread(fn), timeout=...)``.

        Why a dedicated executor: the proxy's compression path is CPU-bound
        Rust work that releases the GIL via ``py.allow_threads``. Sharing
        the loop's default executor (used by ``asyncio.to_thread``) means
        a burst of slow compressions can starve unrelated ``to_thread``
        callers (file IO, etc.). The compression executor is sized
        independently via ``config.compression_max_workers``.

        Why "cancel-aware metrics": when ``asyncio.wait_for`` times out, it
        cancels the *asyncio future*. The underlying
        ``concurrent.futures.Future`` from ``run_in_executor`` cannot
        actually cancel a thread that has started — Python has no way to
        preempt running CPython bytecode or in-flight Rust calls. The
        worker keeps running to completion, ignored. We detect this by
        marking the call timed out on the asyncio side and incrementing
        ``_compression_leaked_threads`` from the worker's ``finally``
        block after it eventually finishes. Jobs that time out before a
        worker starts are removed from the queued gauge instead. Operators
        can see leaked-thread rate and queue pressure climbing in
        ``/stats`` before the pool fills up.

        Args:
            fn: A no-arg sync callable that runs the compression. Must not
                raise asyncio Cancellation; if it does, the wrapper still
                decrements the in-flight gauge but the leaked-thread
                counter may double-count.
            timeout: Wall-clock timeout for the asyncio side. The
                executor worker keeps running past this (Python limitation
                — see above), but at least the awaiter unblocks.

        Returns:
            Whatever ``fn()`` returns.

        Raises:
            ``asyncio.TimeoutError`` if the callable doesn't return within
            ``timeout``. Any exception raised by ``fn`` propagates
            unchanged.
        """
        loop = asyncio.get_running_loop()
        queued_at = time.monotonic()
        state = {"queued": True, "timed_out": False}
        with self._compression_metrics_lock:
            self._compression_queued += 1
            if self._compression_queued > self._compression_queued_max:
                self._compression_queued_max = self._compression_queued

        def _wrapped():  # noqa: ANN202
            started_at = time.monotonic()
            queue_wait = started_at - queued_at
            with self._compression_metrics_lock:
                if state["queued"]:
                    self._compression_queued -= 1
                    state["queued"] = False
                self._compression_queue_wait_seconds_total += queue_wait
                if queue_wait > self._compression_queue_wait_seconds_max:
                    self._compression_queue_wait_seconds_max = queue_wait
                self._compression_in_flight += 1
                if self._compression_in_flight > self._compression_in_flight_max:
                    self._compression_in_flight_max = self._compression_in_flight
            try:
                return fn()
            finally:
                elapsed = time.monotonic() - started_at
                with self._compression_metrics_lock:
                    self._compression_in_flight -= 1
                    self._compression_run_seconds_total += elapsed
                    if elapsed > self._compression_run_seconds_max:
                        self._compression_run_seconds_max = elapsed
                    if state["timed_out"]:
                        self._compression_leaked_threads += 1

        future = loop.run_in_executor(self._compression_executor, _wrapped)
        try:
            return await asyncio.wait_for(future, timeout=timeout)
        except asyncio.TimeoutError:
            with self._compression_metrics_lock:
                state["timed_out"] = True
                if state["queued"]:
                    self._compression_queued -= 1
                    state["queued"] = False
                    self._compression_queue_timeouts += 1
            raise

    def _get_compression_cache(self, session_id: str) -> CompressionCache:
        """Get or create a CompressionCache for a session.

        Thread-safe under `_compression_caches_lock`: a concurrent pair of
        `_get_compression_cache(session_id)` calls (e.g. two async requests
        for the same conversation) must return the **same** instance,
        otherwise the per-session cache state splits and the two halves
        diverge across requests.
        """
        with self._compression_caches_lock:
            if session_id not in self._compression_caches:
                from cutctx.cache.compression_cache import CompressionCache

                # Evict oldest caches if at capacity
                if len(self._compression_caches) >= MAX_COMPRESSION_CACHE_SESSIONS:
                    # Remove oldest quarter to amortize cleanup cost
                    oldest_keys = list(self._compression_caches.keys())[
                        : MAX_COMPRESSION_CACHE_SESSIONS // 4
                    ]
                    for key in oldest_keys:
                        del self._compression_caches[key]
                    logger.info(
                        "Evicted %d compression caches (exceeded %d max sessions)",
                        len(oldest_keys),
                        MAX_COMPRESSION_CACHE_SESSIONS,
                    )

                self._compression_caches[session_id] = CompressionCache()
            return self._compression_caches[session_id]

    def _setup_code_aware(self, config: ProxyConfig, transforms: list) -> str:
        """Set up code-aware compression if enabled.

        Args:
            config: Proxy configuration
            transforms: Transform list to append to

        Returns:
            Status string for logging: 'enabled', 'disabled', 'available', 'unavailable'
        """
        if config.code_aware_enabled:
            if is_tree_sitter_available():
                code_config = CodeCompressorConfig(
                    preserve_imports=True,
                    preserve_signatures=True,
                    preserve_type_annotations=True,
                )
                # CodeAware runs after the content/structure transforms.
                # Phase B PR-B1 retired the trailing context_manager so we
                # append rather than insert(-1).
                transforms.append(CodeAwareCompressor(code_config))
                return "enabled"
            else:
                logger.warning(
                    "Code-aware compression requested but tree-sitter not installed. "
                    "Install with: pip install cutctx-ai[code]"
                )
                return "unavailable"
        else:
            if is_tree_sitter_available():
                return "available"  # Available but not enabled
            return "disabled"

    async def startup(self):
        """Initialize async resources."""
        _patch_getaddrinfo_for_intercept()
        self.pipeline_extensions.emit(
            PipelineStage.PRE_START,
            operation="proxy.startup",
            metadata={"port": self.config.port, "host": self.config.host},
        )
        _ca_bundle = find_ca_bundle()
        self.http_client = httpx.AsyncClient(
            timeout=httpx.Timeout(
                connect=self.config.connect_timeout_seconds,
                read=self.config.request_timeout_seconds,
                write=self.config.request_timeout_seconds,
                pool=self.config.connect_timeout_seconds,
            ),
            limits=httpx.Limits(
                max_connections=self.config.max_connections,
                max_keepalive_connections=self.config.max_keepalive_connections,
            ),
            http2=self.config.http2,
            verify=_ca_bundle if _ca_bundle is not None else True,
        )
        logger.info("Cutctx Proxy started")
        if os.environ.get("CUTCTX_ALLOW_DEBUG", "").strip() in ("1", "true", "yes"):
            logger.warning(
                "⚠️  CUTCTX_ALLOW_DEBUG is set — ptrace/debugger guard is DISABLED. "
                "Do NOT run in production with this flag."
            )
        logger.info(f"Optimization: {'ENABLED' if self.config.optimize else 'DISABLED'}")
        self.config.mode = normalize_proxy_mode(self.config.mode)
        logger.info(f"Mode: {self.config.mode}")
        if self.config.mode == PROXY_MODE_TOKEN:
            logger.info("  Prefix freeze: re-freeze after compression")
            logger.info("  Read protection window: 30%% of excluded-tool messages")
            logger.info("  CCR TTL: extended for session lifetime")
            logger.info("  Compression cache: active")
        if self.config.mode == PROXY_MODE_CACHE:
            logger.info("  Prefix freeze: strict (all prior turns immutable)")
            logger.info("  Mutations: latest turn only")
        logger.info(f"Caching: {'ENABLED' if self.config.cache_enabled else 'DISABLED'}")
        logger.info(f"Rate Limiting: {'ENABLED' if self.config.rate_limit_enabled else 'DISABLED'}")
        logger.info(
            f"Connection Pool: max_connections={self.config.max_connections}, "
            f"max_keepalive={self.config.max_keepalive_connections}, "
            f"http2={'ENABLED' if self.config.http2 else 'DISABLED'}"
        )

        # Unit 4 pre-upstream concurrency announcement. Report the resolved
        # value (auto-detected vs. explicit) so operators can correlate
        # ``pre_upstream_wait_ms`` log lines with the configured cap.
        if self.anthropic_pre_upstream_sem is None:
            logger.info("Anthropic pre-upstream concurrency: unbounded (explicitly disabled)")
        else:
            _explicit = self.config.anthropic_pre_upstream_concurrency
            _origin = "auto-detected" if _explicit is None else "explicit"
            logger.info(
                "Anthropic pre-upstream concurrency: %d (%s)",
                self.anthropic_pre_upstream_concurrency,
                _origin,
            )
        logger.info(
            "Anthropic pre-upstream timeouts: acquire=%.1fs compression=%.1fs memory_context=%.1fs",
            self.anthropic_pre_upstream_acquire_timeout_seconds,
            float(COMPRESSION_TIMEOUT_SECONDS),
            self.anthropic_pre_upstream_memory_context_timeout_seconds,
        )

        logger.info("Smart Routing: ENABLED (ContentRouter is always active)")

        # Eagerly load ALL compressors, parsers, and detectors at startup
        # This eliminates cold-start latency spikes on first requests.
        # Iterate BOTH pipelines (Anthropic + OpenAI) and dedupe transforms
        # by id() so shared-transform instances never load twice. The
        # resulting status dict is merged into ``self.warmup`` so /debug/warmup
        # (Unit 5) and /readyz have a single source of truth.
        self._kompress_status = "not installed"
        eager_status: dict[str, str] = {}

        if self.config.optimize:
            logger.info("Pre-loading compressors and parsers...")
            seen_transform_ids: set[int] = set()
            pipelines = (self.anthropic_pipeline, self.openai_pipeline)
            for pipeline in pipelines:
                for transform in pipeline.transforms:
                    if id(transform) in seen_transform_ids:
                        continue
                    seen_transform_ids.add(id(transform))
                    if not hasattr(transform, "eager_load_compressors"):
                        continue
                    try:
                        transform_status = transform.eager_load_compressors()
                    except Exception as exc:
                        logger.warning(
                            "Eager preload failed for %s: %s",
                            type(transform).__name__,
                            exc,
                        )
                        continue
                    if not isinstance(transform_status, dict):
                        continue
                    # Merge: later writers win only if the key wasn't set.
                    # Preload a transform ONCE — if another pipeline also has
                    # ``eager_load_compressors`` it contributes only new keys.
                    for key, value in transform_status.items():
                        eager_status.setdefault(key, value)
                    self.warmup.merge_transform_status(transform_status)

        # Update internal status from eager loading results
        if eager_status.get("kompress") == "enabled":
            self._kompress_status = "enabled"
        if eager_status.get("code_aware") == "enabled":
            self._code_aware_status = "enabled"

        # Log component status
        if self._kompress_status == "enabled":
            logger.info("Kompress: ENABLED (ModernBERT token compressor)")
        elif self.config.optimize:
            logger.info("Kompress: not installed (pip install cutctx-ai[ml] for ML compression)")

        if self._code_aware_status == "enabled":
            logger.info("Code-Aware: ENABLED (AST-based compression)")
            if "tree_sitter" in eager_status:
                logger.info(f"Code parsing engine: {eager_status['tree_sitter']}")
        elif self._code_aware_status == "lazy":
            logger.info("Code-Aware: LAZY (will load when code content detected)")
        elif self._code_aware_status == "available":
            logger.info("Code-Aware: available but disabled (use --code-aware)")
        elif self._code_aware_status == "unavailable":
            logger.info("Code-Aware: not installed (pip install cutctx-ai[code])")
        elif self._code_aware_status == "disabled":
            logger.info("Code-Aware: DISABLED")

        if eager_status.get("magika") == "enabled":
            logger.info("Content detection engine: ENABLED (ML-based)")

        # Log template mining status is reported by ContentRouter.eager_load_compressors()
        # via the warmup registry. The eager loader handles both the
        # availability check and fallback logging at startup.
        if eager_status.get("drain3") == "ready":
            logger.info(
                "Log template mining: ENABLED "
                "(max_clusters=%d, sim_threshold=%.2f)",
                self.config.drain3_max_clusters,
                self.config.drain3_sim_threshold,
            )
        elif eager_status.get("drain3") == "unavailable":
            logger.warning(
                "Log template mining: requested but not installed. "
                "Falling back to standard LogCompressor. "
                "Install with: pip install cutctx-ai[log-ml]"
            )

        if self.memory_handler:
            if (
                self.config.memory_backend == "qdrant-neo4j"
                and not self.config.memory_neo4j_password
            ):
                logger.warning(
                    "NEO4J password is not set — using default credentials is insecure in production"
                )
            self.warmup.memory_backend.mark_loading()
            try:
                await self.memory_handler.ensure_initialized()
            except Exception as exc:  # pragma: no cover - defensive
                self.warmup.memory_backend.mark_error(str(exc))
                logger.warning("Memory: backend initialization failed (startup continues): %s", exc)
            memory_status = self.memory_handler.health_status()
            if memory_status.get("initialized"):
                self.warmup.memory_backend.mark_loaded(
                    handle=self.memory_handler,
                    backend=memory_status.get("backend"),
                )
                # Force one embed call so the ONNX graph is compiled now,
                # not lazily during the first request. Best-effort — any
                # failure is swallowed inside warmup_embedder.
                self.warmup.memory_embedder.mark_loading()
                warmed = await self.memory_handler.warmup_embedder()
                if warmed:
                    self.warmup.memory_embedder.mark_loaded()
                else:
                    # Not an error — e.g. qdrant-neo4j has no embedder slot
                    # we can reach, or the backend simply exposes no handle.
                    self.warmup.memory_embedder.mark_null()
            else:
                if self.warmup.memory_backend.status != "error":
                    self.warmup.memory_backend.mark_null()
                self.warmup.memory_embedder.mark_null()
            logger.info(
                "Memory: ENABLED "
                f"(backend={memory_status['backend']}, initialized={memory_status['initialized']})"
            )
        else:
            logger.info("Memory: DISABLED")

        # CCR status
        ccr_features = []
        if self.config.ccr_inject_tool:
            ccr_features.append("tool_injection")
        if self.config.ccr_handle_responses:
            ccr_features.append("response_handling")
        if self.config.ccr_context_tracking:
            ccr_features.append("context_tracking")
        if self.config.ccr_proactive_expansion:
            ccr_features.append("proactive_expansion")
        if ccr_features:
            logger.info(f"CCR (Compress-Cache-Retrieve): ENABLED ({', '.join(ccr_features)})")
        else:
            logger.info("CCR: DISABLED")
        logger.info(f"Savings history: {self.metrics.savings_tracker.storage_path}")

        # Reset and rebuild the quota tracker registry for this server instance.
        # reset_quota_registry() ensures a clean slate when the proxy is restarted
        # (e.g. in tests that spin up multiple app instances in the same process).
        reset_quota_registry()
        registry = get_quota_registry()
        tracker = configure_subscription_tracker(
            poll_interval_s=self.config.subscription_poll_interval_s,
            active_window_s=self.config.subscription_active_window_s,
            enabled=self.config.subscription_tracking_enabled,
        )
        registry.register(tracker)
        registry.register(get_codex_rate_limit_state())
        registry.register(get_copilot_quota_tracker())
        await registry.start_all()

        if self.config.subscription_tracking_enabled:
            logger.info(
                "Subscription tracking: ENABLED "
                f"(poll_interval={self.config.subscription_poll_interval_s}s, "
                f"active_window={self.config.subscription_active_window_s}s)"
            )
        else:
            logger.info("Subscription tracking: DISABLED")

        copilot_tracker = get_copilot_quota_tracker()
        if copilot_tracker.is_available():
            logger.info("GitHub Copilot quota tracking: ENABLED")
        else:
            logger.info(
                "GitHub Copilot quota tracking: DISABLED "
                "(set GITHUB_TOKEN or GITHUB_COPILOT_GITHUB_TOKEN to enable)"
            )

        # Log anonymous telemetry status so operators can see it in the log stream
        if is_telemetry_enabled():
            logger.info(
                "Anonymous telemetry: ENABLED (aggregate stats only — no prompts or content). "
                "Opt out: CUTCTX_TELEMETRY=off or --no-telemetry"
            )
        else:
            logger.info("Anonymous telemetry: DISABLED")

        self.pipeline_extensions.emit(
            PipelineStage.POST_START,
            operation="proxy.startup",
            metadata={
                "port": self.config.port,
                "host": self.config.host,
                "warmup": self.warmup.to_dict(),
            },
        )

    async def shutdown(self):
        """Cleanup async resources."""
        if self.http_client:
            await self.http_client.aclose()
            self.http_client = None

        if self.memory_handler and hasattr(self.memory_handler, "close"):
            await self.memory_handler.close()

        with contextlib.suppress(Exception):
            from cutctx.models.ml_models import MLModelRegistry

            released_models = []
            released_models.extend(MLModelRegistry.unload_prefix("technique_router:"))
            released_models.extend(MLModelRegistry.unload_prefix("siglip:"))
            if released_models:
                logger.info("Released image optimizer models: %s", ", ".join(released_models))

        # Stop all quota trackers via the registry
        await get_quota_registry().stop_all()

        # Print final stats
        self._print_summary()

    def _print_summary(self):
        """Print session summary."""
        m = self.metrics
        logger.info("=" * 70)
        logger.info("CUTCTX PROXY SESSION SUMMARY")
        logger.info("=" * 70)
        logger.info(f"Total requests:        {m.requests_total}")
        logger.info(f"Cached responses:      {m.requests_cached}")
        logger.info(f"Rate limited:          {m.requests_rate_limited}")
        logger.info(f"Failed:                {m.requests_failed}")
        logger.info(f"Input tokens:          {m.tokens_input_total:,}")
        logger.info(f"Output tokens:         {m.tokens_output_total:,}")
        logger.info(f"Tokens saved:          {m.tokens_saved_total:,}")
        # Active-compression ratio: savings as a fraction of what we
        # *attempted* to compress (extracted units + tool schema),
        # NOT the whole request. The full-request denominator is
        # dominated by frozen prefix bytes (instructions, user msgs,
        # prior turns) that we never touch — including them collapses
        # the headline number even on sessions where every attempted
        # compression succeeded.
        attempted = getattr(m, "attempted_input_tokens_total", 0)
        if attempted > 0:
            # `attempted` is pre-compression; savings rate is plain
            # saved / attempted.
            savings_pct = (m.tokens_saved_total / attempted) * 100
            logger.info(f"Active compression:    {savings_pct:.1f}%")
            logger.info(f"  (attempted tokens:   {attempted:,})")
        if m.tokens_input_total > 0:
            whole_request_pct = (
                m.tokens_saved_total / (m.tokens_input_total + m.tokens_saved_total)
            ) * 100
            logger.info(f"Of total wire traffic: {whole_request_pct:.2f}%")
        if m.latency_count > 0:
            avg_latency = m.latency_sum_ms / m.latency_count
            logger.info(f"Avg latency:           {avg_latency:.0f}ms")
        logger.info("=" * 70)

    async def _record_request_outcome(self, outcome: RequestOutcome) -> None:
        """Single funnel for per-request bookkeeping.

        Thin wrapper around :func:`cutctx.proxy.outcome.emit_request_outcome`
        so call sites can write ``await self._record_request_outcome(outcome)``
        (idiomatic) instead of ``await emit_request_outcome(self, outcome)``.
        The real implementation lives in ``outcome.py`` as a free function so
        test dummies and provider mixins can call it without inheriting from
        ``CutctxProxy``.

        See ``docs/superpowers/specs/P0-proxy-pipeline-audit.md`` for the
        divergence catalog this funnel collapses.
        """
        from cutctx.proxy.outcome import emit_request_outcome

        await emit_request_outcome(self, outcome)

    async def _next_request_id(self) -> str:
        """Generate unique request ID."""
        async with self._request_counter_lock:
            self._request_counter += 1
            return f"hr_{int(time.time())}_{self._request_counter:06d}"

    def _extract_tags(self, headers: dict) -> dict[str, str]:
        """Backwards-compat wrapper around :func:`extract_tags`.

        Handlers call ``extract_tags(headers)`` directly. Kept here for
        any external caller still using ``proxy._extract_tags(headers)``.
        """
        from cutctx.proxy.helpers import extract_tags

        return extract_tags(headers)

    async def _retry_request(
        self,
        method: str,
        url: str,
        headers: dict,
        body: dict,
        stream: bool = False,
        *,
        original_body_bytes: bytes | None = None,
        body_mutated: bool = True,
        mutation_reasons: list[str] | None = None,
        request_id: str | None = None,
        forwarder_name: str = "server",
        path_for_log: str | None = None,
    ) -> httpx.Response:
        """Make request with retry and exponential backoff.

        Byte-faithful forwarding (PR-A3, fixes P0-2):
          * If ``original_body_bytes`` is provided AND ``body_mutated`` is
            ``False``, the original bytes are forwarded verbatim. SHA-256
            of upstream-received bytes equals client-sent bytes.
          * Otherwise the body dict is canonically re-serialized via
            ``serialize_body_canonical`` (compact separators, ensure_ascii=False).
          * ``CUTCTX_PROXY_PYTHON_FORWARDER_MODE=legacy_json_kwarg`` is an
            explicit operator opt-in for emergency rollback to the old
            ``httpx ... json=body`` behavior.

        The default ``body_mutated=True`` preserves backward compatibility
        for callers that still pass only ``body`` (e.g. CCR continuations
        construct their body from scratch, so canonical serialization is
        correct and original bytes do not exist).
        """
        from cutctx.proxy.helpers import (
            log_outbound_request,
            prepare_outbound_body_bytes,
        )

        last_error = None
        reasons = list(mutation_reasons or [])
        outbound_bytes, source = prepare_outbound_body_bytes(
            body=body,
            original_body_bytes=original_body_bytes,
            body_mutated=body_mutated,
        )
        outbound_headers = {**headers, "content-type": "application/json"}

        log_outbound_request(
            forwarder=forwarder_name,
            method=method,
            path=path_for_log or url,
            body_bytes_count=len(outbound_bytes),
            body_mutated=body_mutated,
            mutation_reasons=reasons,
            request_id=request_id,
            source=source,
        )

        # Audit-Deep-2026-06-21 Blocker 3b: enforce egress policy before
        # opening HTTP connection to provider
        from cutctx.proxy.egress import get_egress_enforcer

        egress_decision = get_egress_enforcer().check(url)
        if not egress_decision.allowed:
            from fastapi import HTTPException

            raise HTTPException(
                status_code=503,
                detail=f"Egress to {url} blocked by policy {egress_decision.policy_id}: {egress_decision.reason}",
            )

        for attempt in range(self.config.retry_max_attempts):
            try:
                if stream:
                    # For streaming, we return early - retry happens at higher level
                    return await self.http_client.post(  # type: ignore[union-attr]
                        url, content=outbound_bytes, headers=outbound_headers
                    )
                else:
                    response = await self.http_client.post(  # type: ignore[union-attr]
                        url, content=outbound_bytes, headers=outbound_headers
                    )

                    # Don't retry client errors (4xx)
                    if 400 <= response.status_code < 500:
                        return response

                    # Retry server errors (5xx)
                    if response.status_code >= 500:
                        raise httpx.HTTPStatusError(
                            f"Server error: {response.status_code}",
                            request=response.request,
                            response=response,
                        )

                    return response

            except (httpx.ConnectError, httpx.TimeoutException, httpx.HTTPStatusError) as e:
                last_error = e

                if not self.config.retry_enabled or attempt >= self.config.retry_max_attempts - 1:
                    raise

                # Exponential backoff with jitter
                delay_with_jitter = jitter_delay_ms(
                    self.config.retry_base_delay_ms,
                    self.config.retry_max_delay_ms,
                    attempt,
                )

                logger.warning(
                    f"Request failed (attempt {attempt + 1}), retrying in {delay_with_jitter:.0f}ms: {e}"
                )
                await asyncio.sleep(delay_with_jitter / 1000)

        if last_error is None:
            raise RuntimeError(
                "retry loop exhausted with no error recorded; retry_max_attempts must be >= 1"
            )
        raise last_error


async def _log_toin_stats_periodically(interval_seconds: int = 300) -> None:
    """Background task that logs TOIN stats periodically.

    Args:
        interval_seconds: How often to log stats (default: 5 minutes).
    """
    while True:
        await asyncio.sleep(interval_seconds)
        try:
            toin = get_toin()
            stats = toin.get_stats()
            total_compressions = stats.get("total_compressions", 0)
            if total_compressions > 0:
                patterns = stats.get("patterns_tracked", 0)
                retrievals = stats.get("total_retrievals", 0)
                retrieval_rate = stats.get("global_retrieval_rate", 0.0)
                logger.info(
                    "TOIN: %d patterns, %d compressions, %d retrievals, %.1f%% retrieval rate",
                    patterns,
                    total_compressions,
                    retrievals,
                    retrieval_rate * 100,
                )
        except Exception as e:
            logger.debug("Failed to log TOIN stats: %s", e)


def _register_memory_components(proxy: CutctxProxy, tracker: MemoryTracker) -> None:
    """Register all memory-tracked components with the tracker.

    This function is idempotent - it checks if components are already registered.

    Args:
        proxy: The CutctxProxy instance.
        tracker: The MemoryTracker instance.
    """
    # Register compression store (global singleton)
    if "compression_store" not in tracker.registered_components:
        store = get_compression_store()
        tracker.register("compression_store", store.get_memory_stats)

    # Register semantic cache (instance on proxy)
    if proxy.cache and "semantic_cache" not in tracker.registered_components:
        tracker.register("semantic_cache", proxy.cache.get_memory_stats)

    # Register request logger (instance on proxy)
    if proxy.logger and "request_logger" not in tracker.registered_components:
        tracker.register("request_logger", proxy.logger.get_memory_stats)

    # Register batch context store (global singleton)
    if "batch_context_store" not in tracker.registered_components:
        try:
            from ..ccr.batch_store import get_batch_context_store

            batch_store = get_batch_context_store()
            if hasattr(batch_store, "get_memory_stats"):
                tracker.register("batch_context_store", batch_store.get_memory_stats)
        except ImportError:
            pass

    # Note: graph_store and vector_index are created per-user within the
    # LocalMemoryBackend, not as global singletons. They would need to be
    # registered when the memory system is initialized with specific backends.


def _create_app_legacy(config: ProxyConfig | None = None) -> FastAPI:
    """Legacy app builder kept only for staged migration safety.

    The public runtime entrypoint is the later ``create_app`` definition in
    this module. Keeping this legacy builder private avoids exporting two
    competing ``create_app`` symbols while the older path is still being
    retired incrementally.
    """
    if not FASTAPI_AVAILABLE:
        raise ImportError("FastAPI required. Install: pip install fastapi uvicorn httpx")

    from contextlib import asynccontextmanager

    # Always-on file logging to ~/.cutctx/logs/ for `cutctx perf` analysis.
    # Installed here (not at module import) so importing cutctx.proxy.server
    # in tests or library contexts does not silently attach a RotatingFileHandler
    # to the user's live proxy.log.
    _setup_file_logging()

    # Air-gap / offline mode validation: must have CUTCTX_LICENSE_HMAC_SECRET
    # set when running without network connectivity.
    from cutctx.proxy.airgap import check_offline_compat

    check_offline_compat()

    config = config or ProxyConfig()
    proxy = CutctxProxy(config)

    # Telemetry beacon (anonymous aggregate stats).
    # With uvicorn workers > 1, each worker runs the lifespan independently.
    # We must ensure only ONE beacon runs across all workers — otherwise each
    # worker creates its own beacon, spamming the telemetry table with N rows
    # per cycle instead of 1 (all reading the same /stats from the same port).
    #
    # Strategy: use a file lock to ensure only the first worker starts the
    # beacon. Other workers see the lock and skip.
    from cutctx.telemetry.beacon import TelemetryBeacon

    _beacon = TelemetryBeacon(
        port=config.port if hasattr(config, "port") else 8787,
        sdk=os.environ.get("CUTCTX_SDK", "proxy").strip() or "proxy",
        backend=config.backend if hasattr(config, "backend") else "anthropic",
    )
    from cutctx import paths as _hr_paths

    _beacon_lock_path = _hr_paths.beacon_lock_path(config.port)
    _beacon_lock_fd: list = [None]  # mutable holder for the lock file descriptor
    _beacon_is_owner: list = [False]

    def _is_stateless() -> bool:
        """Check if stateless mode is active (no filesystem writes)."""
        return config.stateless or os.environ.get(
            "CUTCTX_STATELESS", ""
        ).lower() in ("true", "1", "yes", "on")

    def _try_acquire_beacon_lock() -> bool:
        """Try to acquire the beacon file lock (non-blocking).

        Returns True if this process is the beacon owner.
        In stateless mode, always succeeds without writing files.
        """
        if not HAS_FCNTL or _is_stateless():
            return True

        fd = None
        try:
            _beacon_lock_path.parent.mkdir(parents=True, exist_ok=True)
            fd = open(_beacon_lock_path, "w")  # noqa: SIM115
            fcntl.flock(fd, fcntl.LOCK_EX | fcntl.LOCK_NB)
            fd.write(str(os.getpid()))
            fd.flush()
            _beacon_lock_fd[0] = fd
            return True
        except OSError:
            if fd is not None:
                fd.close()
            return False

    def _release_beacon_lock() -> None:
        """Release the beacon file lock."""
        fd = _beacon_lock_fd[0]
        if fd:
            try:
                if HAS_FCNTL:
                    fcntl.flock(fd, fcntl.LOCK_UN)
                fd.close()
            except Exception:
                pass
            _beacon_lock_fd[0] = None
        try:
            _beacon_lock_path.unlink(missing_ok=True)
        except Exception:
            pass

    @asynccontextmanager
    async def lifespan(app: FastAPI):  # type: ignore[no-untyped-def]
        # Hotfix-A0: Rust core deployment smoke test. Refuse to accept
        # traffic if the Rust extension is missing unless the operator
        # explicitly opted out with CUTCTX_REQUIRE_RUST_CORE=false. See
        # Finding #2 in CUTCTX_PROXY_LOG_FINDINGS_2026_05_03.md.
        # `_check_rust_core` either returns ("loaded"|"disabled", _) or
        # calls `sys.exit(78)` — execution past this line implies the
        # rust_core_status is recorded.
        _rust_core_status, _rust_core_error = _check_rust_core()
        app.state.rust_core_status = _rust_core_status
        app.state.rust_core_error = _rust_core_error

        configure_otel_metrics(OTelMetricsConfig.from_env(default_service_name="cutctx-proxy"))
        configure_langfuse_tracing(
            LangfuseTracingConfig.from_env(default_service_name="cutctx-proxy")
        )

        app.state.started_at = time.time()
        app.state.ready = False
        app.state.startup_error = None
        await initialize_context_tool_session_baseline()

        try:
            try:
                # Startup
                await proxy.startup()
                asyncio.create_task(_log_toin_stats_periodically())

                async def _checkout_seat_periodically() -> None:
                    import asyncio
                    import os
                    import uuid

                    from cutctx.billing.client import checkout_seat
                    license_key = os.environ.get("CUTCTX_LICENSE_KEY")
                    if not license_key:
                        return
                    user_id = f"python-proxy-{uuid.uuid4()}"
                    while True:
                        if not checkout_seat(license_key, user_id):
                            logger.error("License seat limit exceeded! Running in degraded mode.")
                        else:
                            logger.debug("Successfully renewed seat lease for Python proxy.")
                        await asyncio.sleep(1800)

                asyncio.create_task(_checkout_seat_periodically())
                if proxy.usage_reporter:
                    await proxy.usage_reporter.start(proxy)
                    # Sync entitlement tier from validated license
                    if proxy.usage_reporter._license_info and proxy.usage_reporter._license_info.plan:
                        from cutctx.entitlements import EntitlementChecker

                        proxy.entitlement_checker = EntitlementChecker(
                            plan=proxy.usage_reporter._license_info.plan,
                        )
                        logger.info(
                            "Entitlement tier synced from license: %s",
                            proxy.entitlement_checker.plan_name,
                        )
                        # ── Enforce entitlement gating on runtime components ──
                        _ec = proxy.entitlement_checker
                        if not _ec.is_entitled("ccr"):
                            proxy.config.ccr_inject_tool = False
                            proxy.config.ccr_handle_responses = False
                            proxy.config.ccr_context_tracking = False
                            proxy.config.ccr_proactive_expansion = False
                            logger.info(
                                "CCR DISABLED by entitlement (requires TEAM tier, "
                                "current: %s)",
                                _ec.plan_name,
                            )
                        if not _ec.is_entitled("episodic_memory"):
                            proxy.episodic_tracker = None
                            logger.info(
                                "Episodic Memory DISABLED by entitlement "
                                "(requires BUSINESS tier, current: %s)",
                                _ec.plan_name,
                            )
                        if not _ec.is_entitled("live_zone"):
                            os.environ["CUTCTX_MEMORY_INJECTION_MODE"] = "disabled"
                            logger.info(
                                "Live Zone DISABLED by entitlement "
                                "(requires TEAM tier, current: %s)",
                                _ec.plan_name,
                            )
                if proxy.traffic_learner:
                    await proxy.traffic_learner.start()
                if proxy.episodic_tracker:
                    proxy.episodic_tracker.start_sweeper()
                    logger.info("Episodic Memory: session sweeper started")

                # Start retention manager. Blocker-8 (production-audit-
                # 2026-06-20.md) found that the prior code only invoked
                # retention.start() via the manual /retention/cleanup
                # endpoint and never auto-started. The fix wraps the
                # import in a try/except so OSS-only deployments (where
                # the cutctx.retention shim raises ImportError) keep
                # working, and adds a noisy INFO log when retention is
                # actually running so operators can confirm the
                # background task is alive.
                try:
                    from cutctx.retention import get_retention_manager

                    retention_mgr = get_retention_manager()
                    if retention_mgr.enabled:
                        await retention_mgr.start()
                        logger.info(
                            "Retention manager auto-started "
                            "(interval=%ds, ccr=%s, audit=%s, episodic=%s)",
                            getattr(
                                retention_mgr.config, "cleanup_interval_seconds", 0
                            ),
                            getattr(retention_mgr.config, "ccr_enabled", False),
                            getattr(retention_mgr.config, "audit_enabled", False),
                            getattr(retention_mgr.config, "episodic_enabled", False),
                        )
                except ImportError:
                    logger.debug(
                        "Retention manager not started: cutctx_ee not installed "
                        "(OSS-only deployment)."
                    )

                # High-15: start the webhook dispatcher so
                # operator subscriptions are picked up at boot.
                # Idempotent: no-op if CUTCTX_WEBHOOK_URL is
                # unset and no subscriptions were added.
                try:
                    from cutctx.proxy.webhooks import (
                        get_webhook_dispatcher,
                    )

                    webhook_d = get_webhook_dispatcher()
                    if webhook_d.list_subscriptions():
                        await webhook_d.start()
                        logger.info(
                            "WebhookDispatcher started (%d subscriptions)",
                            len(webhook_d.list_subscriptions()),
                        )
                except Exception as webhook_exc:
                    logger.debug(
                        "Webhook dispatcher not started: %s", webhook_exc
                    )

                # Blocker-5 part 2: bind the model router to the
                # proxy state so handlers can call it. The router
                # is OFF by default unless the operator populates
                # CUTCTX_MODEL_ROUTING.
                try:
                    from cutctx.proxy.model_router import ModelRouter

                    proxy._model_router = ModelRouter()
                    if proxy._model_router.config.enabled:
                        logger.info(
                            "ModelRouter enabled with %d routes",
                            len(proxy._model_router.config.routes),
                        )
                except Exception as mr_exc:
                    logger.debug("ModelRouter not bound: %s", mr_exc)
                    proxy._model_router = None

                # Only start beacon if we acquire the lock (first worker wins)
                _beacon_is_owner[0] = _try_acquire_beacon_lock()
                if _beacon_is_owner[0]:
                    await _beacon.start()
                else:
                    logger.debug("Beacon: skipping (another worker owns the lock)")

                app.state.ready = True

                # Audit: log system start
                if proxy.audit_logger:
                    try:
                        from cutctx.audit import AuditEvent

                        await proxy.audit_logger.async_log(
                            AuditEvent(
                                action="system.start",
                                actor="system",
                                detail={
                                    "version": __version__,
                                    "tier": proxy.entitlement_checker.plan_name,
                                    "port": config.port,
                                },
                            )
                        )
                    except Exception:
                        logger.debug("Audit log failed", exc_info=True)

                yield
            except Exception as exc:
                app.state.startup_error = str(exc)
                raise
        finally:
            app.state.ready = False
            # Audit: log system stop
            if proxy.audit_logger:
                try:
                    from cutctx.audit import AuditEvent

                    await proxy.audit_logger.async_log(
                        AuditEvent(
                            action="system.stop",
                            actor="system",
                            detail={"version": __version__},
                        )
                    )
                except Exception:
                    logger.debug("Audit log failed", exc_info=True)
            # Shutdown
            if _beacon_is_owner[0]:
                await _beacon.stop()
                _release_beacon_lock()
            if proxy.usage_reporter:
                await proxy.usage_reporter.stop()
            if proxy.traffic_learner:
                await proxy.traffic_learner.stop()
            if proxy.episodic_tracker:
                proxy.episodic_tracker.stop_sweeper()
            # Stop retention manager. Symmetric with the auto-start
            # block above; wraps the import so OSS-only deployments
            # do not log a stack trace at shutdown.
            try:
                from cutctx.retention import get_retention_manager

                retention_mgr = get_retention_manager()
                await retention_mgr.stop()
            except (ImportError, Exception):
                pass

            # Stop the webhook dispatcher (High-15). Idempotent.
            try:
                from cutctx.proxy.webhooks import (
                    reset_webhook_dispatcher,
                )

                await reset_webhook_dispatcher()
            except (ImportError, Exception):
                pass
            if proxy.code_graph_watcher:
                proxy.code_graph_watcher.stop()
            if getattr(proxy, "knowledge_graph_indexer", None):
                proxy.knowledge_graph_indexer.stop()
            if getattr(proxy, "stack_graph_resolver", None):
                proxy.stack_graph_resolver.clear()
            await proxy.shutdown()
            shutdown_cutctx_tracing()
            shutdown_otel_metrics()

    app = FastAPI(
        title="Cutctx Proxy",
        description="Production-ready LLM optimization proxy",
        version=__version__,
        lifespan=lifespan,
    )
    app.state.proxy = proxy
    app.state.started_at = None
    app.state.ready = False
    app.state.startup_error = None
    # Set by the lifespan startup smoke test (`_check_rust_core`). Default
    # "missing" means lifespan hasn't run yet — anything reading /health
    # before startup completes (rare; lifespan runs before the first
    # request) sees an honest "missing" rather than a stale "loaded".
    app.state.rust_core_status = "missing"
    app.state.rust_core_error = None

    from pathlib import Path
    # cutctx/dashboard/assets/assets — the packaged React build's JS/CSS
    # directory. dashboard/dist/assets (three parents up) is the raw Vite
    # output outside the cutctx/ package tree and is never present in an
    # installed package, so this must stay inside cutctx/dashboard/.
    react_assets = Path(__file__).resolve().parent.parent / "dashboard" / "assets"
    if react_assets.is_dir():
        @app.get("/assets/{filename}", include_in_schema=False)
        async def serve_asset(filename: str):
            asset_path = react_assets / filename
            if asset_path.is_file():
                return FileResponse(str(asset_path))
            return Response(status_code=404)
    def _iso_utc_now() -> str:
        return datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")

    def _uptime_seconds() -> float:
        started_at = getattr(app.state, "started_at", None)
        if not isinstance(started_at, int | float):
            return 0.0
        return round(max(0.0, time.time() - float(started_at)), 3)

    def _component_health(
        *,
        enabled: bool,
        ready: bool,
        **details: Any,
    ) -> dict[str, Any]:
        status = "disabled" if not enabled else ("healthy" if ready else "unhealthy")
    return {
            "enabled": enabled,
            "ready": (ready if enabled else True),
            "status": status,
            **details,
        }

    def _health_checks() -> dict[str, dict[str, Any]]:
        memory_status = (
            proxy.memory_handler.health_status()
            if proxy.memory_handler
            else {
                "enabled": False,
                "backend": None,
                "initialized": False,
                "native_tool": False,
                "bridge_enabled": False,
            }
        )
        memory_enabled = bool(memory_status.get("enabled", False))
        memory_initialized = bool(memory_status.get("initialized", False))
    return {
            "startup": _component_health(
                enabled=True,
                ready=bool(getattr(app.state, "ready", False)),
                error=getattr(app.state, "startup_error", None),
            ),
            "http_client": _component_health(
                enabled=True,
                ready=proxy.http_client is not None,
            ),
            "cache": _component_health(
                enabled=config.cache_enabled,
                ready=(proxy.cache is not None),
            ),
            "rate_limiter": _component_health(
                enabled=config.rate_limit_enabled,
                ready=(proxy.rate_limiter is not None),
            ),
            "memory": _component_health(
                enabled=memory_enabled,
                ready=memory_initialized,
                backend=memory_status["backend"],
                initialized=memory_initialized,
                native_tool=bool(memory_status.get("native_tool", False)),
                bridge_enabled=bool(memory_status.get("bridge_enabled", False)),
            ),
            "upstream": _component_health(
                enabled=os.environ.get("CUTCTX_SKIP_UPSTREAM_CHECK", "").strip() != "1",
                ready=bool(_upstream_check_cache["ok"]),
                url=_upstream_check_cache["url"],
                error=_upstream_check_cache["error"],
            ),
        }

    def _runtime_payload() -> dict[str, Any]:
        ws_registry = getattr(proxy, "ws_sessions", None)
        ws_active_sessions = ws_registry.active_count() if ws_registry is not None else 0
        ws_active_relay_tasks = (
            ws_registry.active_relay_task_count() if ws_registry is not None else 0
        )
        # Snapshot compression executor metrics under their lock (gauges
        # mutated by worker threads; not safe to read without).
        with proxy._compression_metrics_lock:
            _comp_queued = proxy._compression_queued
            _comp_queued_max = proxy._compression_queued_max
            _comp_queue_timeouts = proxy._compression_queue_timeouts
            _comp_queue_wait_total = proxy._compression_queue_wait_seconds_total
            _comp_queue_wait_max = proxy._compression_queue_wait_seconds_max
            _comp_in_flight = proxy._compression_in_flight
            _comp_in_flight_max = proxy._compression_in_flight_max
            _comp_run_total = proxy._compression_run_seconds_total
            _comp_run_max = proxy._compression_run_seconds_max
            _comp_leaked = proxy._compression_leaked_threads
        return {
            "anthropic_pre_upstream": {
                "enabled": proxy.anthropic_pre_upstream_sem is not None,
                "resolved_concurrency": proxy.anthropic_pre_upstream_concurrency,
                "source": (
                    "auto" if config.anthropic_pre_upstream_concurrency is None else "explicit"
                ),
                "acquire_timeout_seconds": proxy.anthropic_pre_upstream_acquire_timeout_seconds,
                "compression_timeout_seconds": float(COMPRESSION_TIMEOUT_SECONDS),
                "memory_context_timeout_seconds": (
                    proxy.anthropic_pre_upstream_memory_context_timeout_seconds
                ),
                "codex_ws_gated": False,
            },
            "compression_executor": {
                "max_workers": proxy.compression_max_workers,
                "queued": _comp_queued,
                "queued_max": _comp_queued_max,
                "queue_timeouts_total": _comp_queue_timeouts,
                "queue_wait_seconds_total": _comp_queue_wait_total,
                "queue_wait_seconds_max": _comp_queue_wait_max,
                "running": _comp_in_flight,
                "in_flight": _comp_in_flight,
                "in_flight_max": _comp_in_flight_max,
                "run_seconds_total": _comp_run_total,
                "run_seconds_max": _comp_run_max,
                "leaked_threads_total": _comp_leaked,
                "source": ("auto" if config.compression_max_workers is None else "explicit"),
            },
            "websocket_sessions": {
                "active_sessions": ws_active_sessions,
                "active_relay_tasks": ws_active_relay_tasks,
            },
        }

    def _health_payload(*, include_config: bool) -> dict[str, Any]:
        checks = _health_checks()
        ready = all(check["ready"] for check in checks.values())
        payload: dict[str, Any] = {
            "service": "cutctx-proxy",
            "status": "healthy" if ready else "unhealthy",
            "ready": ready,
            "version": __version__,
            "timestamp": _iso_utc_now(),
            "uptime_seconds": _uptime_seconds(),
            "checks": checks,
            "runtime": _runtime_payload(),
            # Hotfix-A0: surface rust core load state so operators can alert
            # on `rust_core != "loaded"` (Finding #2).
            "rust_core": getattr(app.state, "rust_core_status", "missing"),
        }
        rust_core_error = getattr(app.state, "rust_core_error", None)
        if rust_core_error:
            payload["rust_core_error"] = rust_core_error
        deployment_profile = os.environ.get("CUTCTX_DEPLOYMENT_PROFILE")
        if deployment_profile:
            payload["deployment"] = {
                "profile": deployment_profile,
                "preset": os.environ.get("CUTCTX_DEPLOYMENT_PRESET"),
                "runtime": os.environ.get("CUTCTX_DEPLOYMENT_RUNTIME"),
                "supervisor": os.environ.get("CUTCTX_DEPLOYMENT_SUPERVISOR"),
                "scope": os.environ.get("CUTCTX_DEPLOYMENT_SCOPE"),
            }
        if include_config:
            profile_kwargs = proxy_pipeline_kwargs(config)
            effective_target_ratio = cast(
                float | None,
                profile_kwargs.get("target_ratio", config.target_ratio),
            )
            payload["config"] = {
                "backend": config.backend,
                "optimize": config.optimize,
                "cache": config.cache_enabled,
                "rate_limit": config.rate_limit_enabled,
                "disable_kompress": config.disable_kompress,
                "memory": config.memory_enabled,
                "learn": config.traffic_learning_enabled,
                "code_graph": config.code_graph_watcher,
                "log_template_mining_enabled": config.drain3_enabled,
                "log_template_mining_max_clusters": config.drain3_max_clusters if config.drain3_enabled else None,
                "log_template_mining_similarity_threshold": config.drain3_sim_threshold if config.drain3_enabled else None,
                "anthropic_api_url": config.anthropic_api_url,
                "openai_api_url": config.openai_api_url,
                "gemini_api_url": config.gemini_api_url,
                "cloudcode_api_url": config.cloudcode_api_url,
                "savings_profile": config.savings_profile,
                "target_ratio": effective_target_ratio,
                "target_savings_percent": (
                    round(max(0.0, min(1.0, 1.0 - float(effective_target_ratio))) * 100, 1)
                    if effective_target_ratio is not None
                    else None
                ),
                "compress_user_messages": bool(
                    profile_kwargs.get("compress_user_messages", config.compress_user_messages)
                ),
                "compress_system_messages": bool(
                    profile_kwargs.get(
                        "compress_system_messages",
                        config.compress_system_messages,
                    )
                ),
                "protect_recent": profile_kwargs.get(
                    "read_protection_window",
                    config.protect_recent,
                ),
                "protect_analysis_context": profile_kwargs.get(
                    "protect_analysis_context",
                    config.protect_analysis_context,
                ),
                "min_tokens_to_crush": profile_kwargs.get(
                    "min_tokens_to_compress",
                    config.min_tokens_to_crush,
                ),
                "max_items_after_crush": profile_kwargs.get(
                    "max_items_after_crush",
                    config.max_items_after_crush,
                ),
                "smart_crusher_with_compaction": profile_kwargs.get(
                    "smart_crusher_with_compaction",
                    config.smart_crusher_with_compaction,
                ),
                "force_kompress": bool(profile_kwargs.get("force_kompress", False)),
                "accuracy_guard": config.accuracy_guard,
                "pid": os.getpid(),
                "task_aware_enabled": config.task_aware_enabled,
                "dedup_enabled": config.dedup_enabled,
                "context_budget_enabled": config.context_budget_enabled,
                "profiles_enabled": config.profiles_enabled,
                "firewall_enabled": getattr(config, "firewall_enabled", False),
            }
            # Merge runtime flag overrides so dashboard sees live state.
            try:
                from cutctx.proxy.intelligence_pipeline import get_all_runtime_flags
                runtime = get_all_runtime_flags()
                if runtime:
                    for k, v in runtime.items():
                        payload["config"][k] = v
                    payload["config"]["runtime_overrides"] = runtime
            except ImportError:
                pass
        return payload

    # ---------------------------------------------------------------------------
    # Upstream connectivity check — cached to avoid hammering the upstream on
    # every /readyz poll.  Set CUTCTX_SKIP_UPSTREAM_CHECK=1 to opt out (e.g.
    # in air-gapped or test environments where the upstream isn't reachable at
    # startup time).
    # ---------------------------------------------------------------------------

    _UPSTREAM_CHECK_TTL = 30.0  # seconds
    _upstream_check_cache: dict[str, Any] = {
        "expires_at": 0.0,
        "ok": True,
        "error": None,
        "url": None,
    }
    _upstream_check_lock = asyncio.Lock()

    def _upstream_target_url() -> str:
        """Return the primary upstream base URL to probe."""
        # Use the resolved API target from the provider runtime so we respect
        # any overrides set by ProxyConfig.anthropic_api_url / env vars.
        return proxy.provider_runtime.api_targets.anthropic

    async def _check_upstream() -> None:
        """Probe the upstream API endpoint and update the cached result.

        Uses a HEAD request with a 5-second timeout — just enough to verify
        TLS + TCP reachability without triggering an inference call.
        """
        if os.environ.get("CUTCTX_SKIP_UPSTREAM_CHECK", "").strip() == "1":
            # Opt-out: treat upstream as always reachable.
            _upstream_check_cache["ok"] = True
            _upstream_check_cache["error"] = None
            _upstream_check_cache["expires_at"] = time.monotonic() + _UPSTREAM_CHECK_TTL
            return

        now = time.monotonic()
        # Fast-path: return if the cached result is still fresh (no lock needed
        # for a simple float comparison — worst case we re-check twice).
        if now < _upstream_check_cache["expires_at"]:
            return

        async with _upstream_check_lock:
            # Re-check inside the lock to handle concurrent waiters.
            if time.monotonic() < _upstream_check_cache["expires_at"]:
                return
            url = _upstream_target_url()
            _upstream_check_cache["url"] = url
            client = proxy.http_client
            if client is None:
                _upstream_check_cache["ok"] = False
                _upstream_check_cache["error"] = "proxy client not initialised"
                _upstream_check_cache["expires_at"] = time.monotonic() + _UPSTREAM_CHECK_TTL
                return
            try:
                resp = await client.head(url, timeout=5.0)
                # Any HTTP response (even 4xx/5xx) means TLS+TCP worked.
                _ = resp.status_code
                _upstream_check_cache["ok"] = True
                _upstream_check_cache["error"] = None
            except Exception as exc:  # noqa: BLE001
                _upstream_check_cache["ok"] = False
                _upstream_check_cache["error"] = str(exc)
            _upstream_check_cache["expires_at"] = time.monotonic() + _UPSTREAM_CHECK_TTL

    # CORS — configurable origins, default closed (empty list).
    # Set CUTCTX_CORS_ORIGINS="*" for dev, or explicit origins for production.
    _cors_origins = getattr(config, "cors_origins", None) or []
    if "*" in _cors_origins:
        _cors_allow_origins = ["*"]
        # Wildcard origins and credentialed responses are an unsafe combo.
        # Keep the developer-friendly open policy, but never advertise
        # credential support when any origin may read the response.
        _cors_allow_credentials = False
    else:
        _cors_allow_origins = _cors_origins
        _cors_allow_credentials = bool(_cors_origins)
    # Wildcard origins → permissive methods/headers (dev/local mode).
    # Explicit origin allowlist → restrict to methods and headers the proxy
    # actually uses, reducing attack surface in production deployments.
    if _cors_allow_origins == ["*"]:
        _cors_methods: list[str] = ["*"]
        _cors_headers: list[str] = ["*"]
    else:
        _cors_methods = ["GET", "POST", "PUT", "DELETE", "PATCH", "OPTIONS"]
        _cors_headers = [
            "Authorization",
            "Content-Type",
            "X-Cutctx-Admin-Key",
            "X-Request-ID",
            "X-Cutctx-MFA-Code",
            "anthropic-version",
            "anthropic-beta",
        ]
    app.add_middleware(
        CORSMiddleware,
        allow_origins=_cors_allow_origins,
        allow_credentials=_cors_allow_credentials,
        allow_methods=_cors_methods,
        allow_headers=_cors_headers,
    )

    # Global JSON decode error handler — invalid request body JSON
    # returns 400 instead of a raw 404 or 500 crash.
    @app.exception_handler(json.JSONDecodeError)
    async def _json_decode_error_handler(request: Request, exc: json.JSONDecodeError) -> JSONResponse:
        return JSONResponse(
            status_code=400,
            content={
                "type": "error",
                "error": {
                    "type": "invalid_request_error",
                    "message": f"Invalid JSON in request body: {exc!s}",
                },
            },
        )

    # Generic HTTPException handler — converts FastAPI's default
    # `{"detail": "..."}` shape into OpenAI's `{"error": {...}}` shape
    # so clients (Codex, codex CLI, OpenAI SDKs) see a consistent error
    # envelope. Without this, `RequestValidationError` and other 4xx that
    # surface as `{"detail": "Bad Request"}` would be shown to the user
    # verbatim, masking the real cause.
    from fastapi import HTTPException as _HTTPException  # local alias

    @app.exception_handler(_HTTPException)
    async def _http_exception_handler(request: Request, exc: _HTTPException) -> JSONResponse:
        # Detail may be a string, dict, or list. Preserve structure.
        detail = exc.detail
        if isinstance(detail, dict):
            message = detail.get("message") or detail.get("error") or str(detail)
        elif isinstance(detail, list):
            message = "; ".join(str(d) for d in detail)
        else:
            message = str(detail)
        logger.warning(
            f"HTTPException path={request.url.path} method={request.method} "
            f"status={exc.status_code} detail={detail!r}"
        )
        return JSONResponse(
            status_code=exc.status_code,
            content={
                "type": "error",
                "error": {
                    "type": "invalid_request_error" if exc.status_code < 500 else "server_error",
                    "message": message,
                    "code": f"http_{exc.status_code}",
                },
            },
        )

    # Request ID propagation — every request gets a unique ID that
    # follows through the entire middleware stack, logging, and response.
    # Clients can send X-Request-ID; we generate one if absent.
    import uuid as _uuid

    @app.middleware("http")
    async def _request_id_middleware(request, call_next):
        req_id = request.headers.get("x-request-id") or str(_uuid.uuid4())
        request.state.cutctx_request_id = req_id
        response = await call_next(request)
        response.headers["X-Request-ID"] = req_id
        return response

    @app.middleware("http")
    async def _minimal_build_middleware(request, call_next):
        mode = resolve_minimal_build_mode(request.headers)
        if mode is None or request.method != "POST":
            return await call_next(request)

        path = request.url.path
        if path not in {"/v1/messages", "/v1/chat/completions"}:
            return await call_next(request)

        try:
            body_bytes = await request.body()
            if not body_bytes or len(body_bytes) > 1024 * 1024:
                return await call_next(request)
            payload = json.loads(body_bytes)
            if not isinstance(payload, dict):
                return await call_next(request)

            if path == "/v1/messages":
                applied = apply_minimal_build_to_anthropic_body(payload, mode)
            else:
                applied = apply_minimal_build_to_openai_body(payload, mode)
            if applied:
                request._body = json.dumps(
                    payload,
                    separators=(",", ":"),
                    ensure_ascii=False,
                ).encode("utf-8")
                request._json = payload
                request.state.cutctx_minimal_build_mode = mode
        except (json.JSONDecodeError, ValueError, AttributeError, TypeError):
            return await call_next(request)
        except Exception as exc:
            logger.debug("Minimal-build middleware skipped: %s", exc)
            return await call_next(request)

        return await call_next(request)

    # API versioning header — every response gets X-Cutctx-Version so
    # clients and load balancers can verify which proxy version is serving.
    @app.middleware("http")
    async def _add_version_header(request, call_next):
        response = await call_next(request)
        response.headers["X-Cutctx-Version"] = __version__
        return response

    # ── LLM Firewall ───────────────────────────────────────────────
    # Scans incoming messages for prompt injections, PII, and jailbreaks.
    # Blocks requests with violations when enabled. Also provides a
    # StreamingRedactor for PII redaction in streaming responses.
    _firewall_scanner = None
    _streaming_redactor = None
    try:
        from cutctx.security.firewall import FirewallConfig, FirewallScanner, StreamingRedactor

        _fw_config = FirewallConfig(
            enabled=getattr(config, "firewall_enabled", False),
            block_pii=getattr(config, "firewall_block_pii", True),
            block_injection=getattr(config, "firewall_block_injection", True),
            block_jailbreak=getattr(config, "firewall_block_jailbreak", True),
            redact_streaming=getattr(config, "firewall_redact_streaming", True),
        )
        if _fw_config.enabled:
            _firewall_scanner = FirewallScanner(_fw_config)
            _streaming_redactor = StreamingRedactor(
                enabled=_fw_config.redact_streaming,
            )
            # Blocker-10 (production-audit-progress-2026-06-20.md):
            # expose the redactor on the proxy state so the streaming
            # mixin can pick it up and wrap the SSE chunk iterator.
            proxy._streaming_redactor = _streaming_redactor
            logger.info("LLM Firewall enabled (injection=%s, pii=%s, jailbreak=%s)",
                        _fw_config.block_injection, _fw_config.block_pii, _fw_config.block_jailbreak)
    except Exception:
        logger.debug("LLM Firewall not available", exc_info=True)

    # Audit-Deep-2026-06-21: warn loudly when the firewall is
    # disabled in a non-dev / non-test deployment. The
    # production recommendation is to enable at least
    # prompt-injection + PII scanning for any deployment that
    # serves untrusted input. The warning is one-time at
    # boot, not per-request, so it does not pollute logs.
    if _firewall_scanner is None:
        import os as _os
        if not _os.environ.get("CUTCTX_FIREWALL_OPT_OUT_WARNING") and not _os.environ.get("PYTEST_CURRENT_TEST"):
            tier = _os.environ.get("CUTCTX_TIER", "self-hosted")
            if tier in ("public-cloud", "business", "enterprise"):
                logger.warning(
                    "LLM Firewall is DISABLED on a %s deployment. "
                    "Recommended: set CUTCTX_FIREWALL_ENABLED=1 to "
                    "enable prompt-injection + PII scanning. "
                    "Set CUTCTX_FIREWALL_OPT_OUT_WARNING=1 to suppress.",
                    tier,
                )

    @app.middleware("http")
    async def _firewall_scan_middleware(request, call_next):
        """Scan incoming proxy requests for prompt injections and PII.

        Only scans POST requests to LLM proxy paths (/v1/messages,
        /v1/chat/completions, /v1/responses). Returns 403 on violations.
        """
        if _firewall_scanner is None:
            return await call_next(request)

        if request.method != "POST":
            return await call_next(request)

        path = request.url.path
        if not any(path.startswith(p) for p in (
            "/v1/messages", "/v1/chat/completions", "/v1/responses",
        )):
            return await call_next(request)

        # Read and buffer the body for scanning
        try:
            body_bytes = await request.body()
            if len(body_bytes) > 1024 * 1024:  # skip scanning >1MB bodies
                return await call_next(request)

            body_json = json.loads(body_bytes)
            messages = body_json.get("messages", [])

            violations = _firewall_scanner.scan_messages(messages)
            if violations and _firewall_scanner.should_block(violations):
                from fastapi.responses import JSONResponse
                logger.warning(
                    "Firewall blocked request to %s: %d violation(s)",
                    path, len(violations),
                )
                return JSONResponse(
                    status_code=403,
                    content={
                        "error": {
                            "type": "forbidden",
                            "message": "Request blocked by LLM firewall",
                            "violations": [
                                {"kind": v.kind.value, "description": v.description}
                                for v in violations
                            ],
                        }
                    },
                )
        except (json.JSONDecodeError, ValueError):
            pass  # Non-JSON body — let it through
        except Exception as exc:
            logger.debug("Firewall scan error (pass-through): %s", exc)

        return await call_next(request)

    # ── Rate Limiting Middleware ─────────────────────────────────────
    # Applies per-IP token bucket rate limiting to POST requests on LLM
    # proxy paths (/v1/messages, /v1/chat/completions, /v1/responses).
    # Returns 429 Too Many Requests with Retry-After when exceeded.

    @app.middleware("http")
    async def _rate_limit_middleware(request, call_next):
        if not getattr(config, "rate_limit_enabled", False):
            return await call_next(request)

        if request.method != "POST":
            return await call_next(request)

        path = request.url.path
        if not any(path.startswith(p) for p in (
            "/v1/messages", "/v1/chat/completions", "/v1/responses",
        )):
            return await call_next(request)

        client_ip = getattr(request.client, "host", "unknown") if request.client else "unknown"
        # High-14 (production-audit-progress-2026-06-20.md): the
        # rate limiter was previously per-IP only, which means a
        # 500-user corporate egress behind a single NAT shared one
        # 60-rpm bucket. The fix: when an authenticated identity
        # is available (SSO user_id, API key fingerprint, or
        # admin auth user_id), key the bucket on that identity
        # instead of the IP. Falls back to IP for unauthenticated
        # traffic.
        # Order of preference: SSO user_id > admin user_id > client IP.
        # Each tier gets its own bucket so a noisy corporate
        # egress does not starve an individual authenticated
        # user (and vice versa).
        identity_key = None
        sso_user = getattr(request.state, "cutctx_user_id", None)
        if sso_user:
            identity_key = f"user:{sso_user}"
        if identity_key is None:
            # Use IP as fallback. Prefix 'ip:' so user-buckets and
            # ip-buckets cannot collide.
            identity_key = f"ip:{client_ip}"
        try:
            allowed, wait_seconds = await proxy.rate_limiter.check_request(key=identity_key)
            if not allowed:
                from fastapi.responses import JSONResponse as _JSONResp
                retry_after = max(1, int(wait_seconds))
                return _JSONResp(
                    status_code=429,
                    content={
                        "error": {
                            "type": "rate_limit_exceeded",
                            "message": f"Rate limit exceeded. Retry after {retry_after}s.",
                            "retry_after_seconds": retry_after,
                        }
                    },
                    headers={"Retry-After": str(retry_after)},
                )
        except Exception as exc:
            logger.debug("Rate limiter check failed (pass-through): %s", exc)

        return await call_next(request)

    # ---------------------------------------------------------------------------
    # 2.6 FIX: Trial enforcement middleware.
    # Blocks LLM proxy requests when the 14-day trial has expired and no
    # paid license has been activated. Health checks, admin endpoints, and
    # the CLI status path are exempt.
    # ---------------------------------------------------------------------------

    _trial_enforcement_enabled = os.environ.get(
        "CUTCTX_TRIAL_ENFORCEMENT", ""
    ).strip().lower() not in ("0", "false", "no")

    _trial_manager = None
    if _trial_enforcement_enabled:
        try:
            from cutctx.trial import TrialManager
            _trial_manager = TrialManager()
            logger.info("Trial enforcement middleware enabled")
        except Exception:
            logger.debug("TrialManager not available", exc_info=True)

    @app.middleware("http")
    async def _trial_enforcement_middleware(request, call_next):
        """Enforce trial expiry: block LLM requests when trial is expired.

        Exempts health/readiness endpoints, admin API, and non-proxy paths.
        """
        if _trial_manager is None:
            return await call_next(request)

        path = request.url.path

        # Exempt non-proxy paths (health, admin, metrics, etc.)
        if not any(path.startswith(p) for p in (
            "/v1/messages", "/v1/chat/completions", "/v1/responses",
            "/v1/conversations",
        )):
            return await call_next(request)

        # Only enforce on POST (actual LLM requests)
        if request.method != "POST":
            return await call_next(request)

        try:
            if _trial_manager.enforce_trial():
                from fastapi.responses import JSONResponse
                logger.warning(
                    "Trial expired — blocking request to %s. "
                    "Activate a license with: cutctx license activate <key>",
                    path,
                )
                return JSONResponse(
                    status_code=403,
                    content={
                        "error": {
                            "type": "trial_expired",
                            "message": (
                                "Your 14-day trial has expired. "
                                "Activate a license to continue using Cutctx. "
                                "Get a license through PitchToShip."
                            ),
                            "upgrade_url": checkout_url("team"),
                            "contact": "hello@cutctx.dev",
                        }
                    },
                )
        except Exception as exc:
            logger.debug("Trial enforcement check failed (pass-through): %s", exc)

        return await call_next(request)

    # Admin API key authentication for sensitive endpoints.
    # When admin_api_key is configured, /dashboard, /stats, /stats-reset,
    # /stats-history, and /transformations/feed require a valid key.
    # Accepts: Authorization: Bearer <key> or X-Cutctx-Admin-Key: <key>
    #
    # SECURE-BY-DEFAULT: When not configured, auto-generate a random key.
    # Blocker-7 (production-audit-2026-06-20.md): the previous code logged
    # the auto-generated key at WARNING level, which leaks the admin
    # credential to any centralized log aggregator (Datadog, Splunk,
    # CloudWatch). The fix prints the key to stdout ONLY (so the operator
    # can copy it from the server console), and never to the Python
    # logging subsystem.
    _admin_api_key = getattr(config, "admin_api_key", None)
    if not _admin_api_key:
        _admin_api_key = os.environ.get("CUTCTX_ADMIN_API_KEY")
    if not _admin_api_key:
        import secrets as _secrets
        _admin_api_key = _secrets.token_urlsafe(32)
        # Log to Python logger WITHOUT the key value.
        logger.warning(
            "No CUTCTX_ADMIN_API_KEY configured — auto-generated key for "
            "this session. Set CUTCTX_ADMIN_API_KEY env var for a "
            "persistent key. The new key is printed to stdout (not the log)."
        )
        # Print the key to stdout ONLY, with a clear marker so the
        # operator can copy it from the server console. Never goes
        # through the Python logger.
        sys.stderr.write(
            "\n[cutctx] Auto-generated admin API key (not logged):\n"
            f"  CUTCTX_ADMIN_API_KEY={_admin_api_key}\n"
            "  Set this env var on next start to keep the same key.\n\n"
        )
        sys.stderr.flush()

    def _mark_admin_auth_success(
        request: Request,
        *,
        method: str,
        role: str | None = None,
        user_id: str | None = None,
        claims: dict[str, Any] | None = None,
    ) -> None:
        request.state._cutctx_admin_checked = True
        request.state._cutctx_admin_error = None
        request.state.cutctx_admin_auth_method = method
        if role:
            request.state.cutctx_role = role
        if user_id:
            request.state.cutctx_user_id = user_id
        if claims is not None:
            request.state.cutctx_sso_claims = claims

    async def _enforce_mfa_if_enrolled(request: Request) -> None:
        """Audit-Deep-2026-06-21 High-12: second-factor auth.

        If the authenticated user has an MFA enrollment, the
        request must include a valid TOTP code in the
        ``X-Cutctx-MFA-Code`` header. Codes are single-use
        (replay-protected via the last_used_counter).

        API-key authenticated requests are bypassed: the admin
        key is itself a long-lived secret and the user_id
        is unknown (it's the key fingerprint, not a human).
        This matches the threat model: SSO identities are
        the ones that need a second factor; admin keys are
        already a high-entropy secret.
        """
        # Already verified in this request? Skip.
        if getattr(request.state, "_cutctx_mfa_verified", False):
            return
        # Skip when the request was authenticated by an API key
        # (no human user to enroll).
        if getattr(request.state, "cutctx_admin_auth_method", None) == "api_key":
            return
        # Determine the user_id (SSO subject).
        user_id = getattr(request.state, "cutctx_user_id", None)
        if not user_id:
            return
        # Lazily import the MFA store; opens the same DB file
        # as the RBAC store.
        from cutctx.security.mfa import MfaStore, verify_totp

        store_path = os.environ.get("CUTCTX_RBAC_DB_PATH") or "~/.cutctx/rbac.db"
        try:
            mfa_store = MfaStore(db_path=store_path)
        except Exception:
            # If the store can't open (read-only mount, etc.)
            # we silently allow the request through. Logging
            # the failure is enough; we don't want to break
            # auth when the FS is in a weird state.
            logger.warning("MFA store unavailable; skipping MFA check", exc_info=True)
            return
        enrollment = mfa_store.get(user_id)
        if enrollment is None:
            # No enrollment; nothing to enforce.
            return
        # Enrollment exists: the caller MUST supply a valid TOTP.
        code = request.headers.get("x-cutctx-mfa-code", "").strip()
        if not code:
            error = HTTPException(
                status_code=401,
                detail=(
                    "MFA required. Pass the current TOTP code in the "
                    "X-Cutctx-MFA-Code header. Enroll via POST /v1/admin/mfa."
                ),
            )
            request.state._cutctx_admin_error = error
            try:
                if proxy.audit_logger is not None:
                    from cutctx.audit import AuditEvent

                    await proxy.audit_logger.async_log(
                        AuditEvent(
                            action="auth.failed",
                            actor="anonymous",
                            success=False,
                            detail={
                                "method": "sso",
                                "path": request.url.path,
                                "reason": "mfa_missing",
                                "user_id": user_id,
                            },
                            ip_address=getattr(request.client, "host", None)
                            if request.client
                            else None,
                            user_agent=request.headers.get("user-agent", ""),
                        )
                    )
            except Exception:
                logger.debug("audit emit failed", exc_info=True)
            raise error
        # Verify the TOTP (with replay protection).
        ok = verify_totp(
            enrollment["secret_b32"],
            code,
            last_used_counter=enrollment["last_used_counter"],
        )
        if not ok:
            error = HTTPException(
                status_code=401,
                detail=(
                    "MFA TOTP invalid or replayed. "
                    "Wait for a fresh 30s code from your "
                    "authenticator app."
                ),
            )
            request.state._cutctx_admin_error = error
            try:
                if proxy.audit_logger is not None:
                    from cutctx.audit import AuditEvent

                    await proxy.audit_logger.async_log(
                        AuditEvent(
                            action="auth.failed",
                            actor="anonymous",
                            success=False,
                            detail={
                                "method": "sso",
                                "path": request.url.path,
                                "reason": "mfa_invalid",
                                "user_id": user_id,
                            },
                            ip_address=getattr(request.client, "host", None)
                            if request.client
                            else None,
                            user_agent=request.headers.get("user-agent", ""),
                        )
                    )
            except Exception:
                logger.debug("audit emit failed", exc_info=True)
            raise error
        # Success: advance the single-use counter to prevent
        # replay.
        import time as _time

        now = _time.time()
        current_counter = int(now) // 30
        mfa_store.consume_counter(user_id, current_counter)
        # Mark the cached path as MFA-verified so the
        # inner-loop call doesn't re-enforce.
        request.state._cutctx_mfa_verified = True

    async def _authenticate_admin_request(request: Request) -> None:
        """Authenticate an admin request using API key or enterprise SSO."""
        # SECURITY: Test mode bypass removed. Tests use CUTCTX_ADMIN_API_KEY
        # env var for deterministic auth. The CUTCTX_TEST_MODE flag is
        # NO LONGER honored for admin auth — it was a security risk that
        # could expose admin endpoints if accidentally set in production.

        if getattr(request.state, "_cutctx_admin_checked", False):
            cached_error = getattr(request.state, "_cutctx_admin_error", None)
            if cached_error is not None:
                raise cached_error
            # Audit-Deep-2026-06-21 High-12: if MFA is enrolled for
            # this user, the second-factor check must also pass on
            # every request (including the cached fast path).
            await _enforce_mfa_if_enrolled(request)
            return

        # Loopback bypass for read-only: GET/HEAD requests from localhost
        # are implicitly trusted for dashboard/stats access. Mutating
        # requests (POST, PUT, DELETE, PATCH) still require admin credentials.
        # Only specific read-only paths are allowed; all other paths require auth.
        client_host = getattr(request.client, "host", "") if request.client else ""
        if (
            client_host in ("127.0.0.1", "::1", "localhost")
            and request.method in ("GET", "HEAD")
            and any(request.url.path == p or request.url.path.startswith(p + "/") for p in _LOOPBACK_OPEN_PATHS)
        ):
            request.state._cutctx_admin_checked = True
            return

        auth_header = request.headers.get("authorization", "")
        bearer_token = auth_header[7:].strip() if auth_header.startswith("Bearer ") else ""
        admin_header = request.headers.get("x-cutctx-admin-key", "") or request.query_params.get("key", "")

        # Medium-27 (production-audit-progress-2026-06-20.md):
        # helper to emit an audit event for the auth attempt. Wraps
        # the audit_logger.async_log call so we never block the
        # request on a slow audit sink.
        async def _emit_auth_event(action: str, success: bool, detail: dict[str, Any]) -> None:
            try:
                if proxy.audit_logger is None:
                    return
                from cutctx.audit import AuditEvent

                await proxy.audit_logger.async_log(
                    AuditEvent(
                        action=action,
                        actor=(
                            bearer_token[:16] if success else "anonymous"
                        ),
                        success=success,
                        detail=detail,
                        ip_address=getattr(request.client, "host", None) if request.client else None,
                        user_agent=request.headers.get("user-agent", ""),
                    )
                )
            except Exception:  # noqa: BLE001
                logger.debug("audit log emit failed", exc_info=True)

        if _admin_api_key:
            import hmac as _hmac
            if _hmac.compare_digest(bearer_token, _admin_api_key) or _hmac.compare_digest(admin_header, _admin_api_key):
                _mark_admin_auth_success(request, method="api_key")
                await _emit_auth_event(
                    "auth.login",
                    True,
                    {"method": "api_key", "path": request.url.path},
                )
                return
            # API key was provided but did not match — emit a failure event.
            if bearer_token or admin_header:
                await _emit_auth_event(
                    "auth.failed",
                    False,
                    {
                        "method": "api_key",
                        "path": request.url.path,
                        "reason": "key_mismatch",
                    },
                )

        if _sso_validator_ref is not None:
            if not bearer_token:
                error = HTTPException(
                    status_code=401,
                    detail="Missing Bearer token for SSO-protected admin endpoint.",
                )
                request.state._cutctx_admin_checked = True
                request.state._cutctx_admin_error = error
                await _emit_auth_event(
                    "auth.failed",
                    False,
                    {"method": "sso", "path": request.url.path, "reason": "missing_token"},
                )
                raise error
            try:
                from cutctx.sso import SsoError

                claims = await _sso_validator_ref.validate_token(bearer_token)
                _mark_admin_auth_success(
                    request,
                    method="sso",
                    role=claims.role,
                    user_id=claims.subject,
                    claims=claims.to_dict(),
                )
                await _emit_auth_event(
                    "auth.login",
                    True,
                    {
                        "method": "sso",
                        "path": request.url.path,
                        "subject": getattr(claims, "subject", None),
                        "role": getattr(claims, "role", None),
                    },
                )
                # Audit-Deep-2026-06-21 High-12: enforce MFA
                # second factor. Raises 401 if the user is
                # enrolled but didn't supply a valid TOTP.
                await _enforce_mfa_if_enrolled(request)
                return
            except SsoError as exc:
                logger.debug("SSO token validation failed: %s", exc)
                error = HTTPException(
                    status_code=401,
                    detail="Invalid or expired SSO bearer token for admin endpoint.",
                )
                request.state._cutctx_admin_checked = True
                request.state._cutctx_admin_error = error
                await _emit_auth_event(
                    "auth.failed",
                    False,
                    {
                        "method": "sso",
                        "path": request.url.path,
                        "reason": "validation_failed",
                    },
                )
                raise error from exc

        # SECURE-BY-DEFAULT: Admin key is always required.
        # If we reach here, the key didn't match and no SSO authenticated.
        error = HTTPException(
            status_code=401,
            detail="Invalid or missing admin credentials. Set Authorization: Bearer <token> "
            "or X-Cutctx-Admin-Key: <key>.",
        )
        request.state._cutctx_admin_checked = True
        request.state._cutctx_admin_error = error
        await _emit_auth_event(
            "auth.failed",
            False,
            {"method": "none", "path": request.url.path, "reason": "no_credentials"},
        )
        raise error

    async def _require_admin_auth(request: Request):
        """Dependency that gates endpoints behind admin API key auth."""
        await _authenticate_admin_request(request)

    # ── RBAC dependency ────────────────────────────────────────────────
    # Usage: Depends(_require_rbac_permission("stats.read"))
    # Resolves caller's role from headers/org-store, checks permission.
    # Falls through to admin (backward-compatible) when no RBAC configured.
    _rbac_checker_ref = None
    try:
        from cutctx.rbac import get_rbac_checker

        _rbac_checker_ref = get_rbac_checker()
    except Exception:
        logger.debug("RBAC checker not available", exc_info=True)

'''
def _require_rbac_permission(permission: str):
        """Factory that returns a dependency checking a specific RBAC permission."""

        async def _check(request: Request):
            await _authenticate_admin_request(request)
            if _rbac_checker_ref is None:
                raise HTTPException(
                    status_code=503,
                    detail="RBAC unavailable",
                )
            role = _rbac_checker_ref.resolve_role(request)
            _rbac_checker_ref.check_permission(role, permission)

 return _check
'''


def _require_rbac_permission(permission: str):
    """Factory returning a dependency that checks one RBAC permission."""

    async def _check(request: Request):
        await _authenticate_admin_request(request)
        if _rbac_checker_ref is None:
            raise HTTPException(
                status_code=503,
                detail="RBAC unavailable",
            )
        role = _rbac_checker_ref.resolve_role(request)
        _rbac_checker_ref.check_permission(role, permission)

    return _check

    '''

    def _feature_availability_snapshot() -> dict[str, dict[str, Any]]:
        """Surface which optional best-in-class features are actually usable.

        This keeps operator claims honest: several advanced surfaces are
        optional extras or external binaries and may silently degrade if their
        dependencies are missing. The snapshot is lightweight and safe to call
        from ``/stats``.
        """
    graphify_py = importlib.util.find_spec("graphifyy") is not None or importlib.util.find_spec("graphify") is not None
        networkx_py = importlib.util.find_spec("networkx") is not None
        pillow_py = importlib.util.find_spec("PIL") is not None
        llmlingua_py = importlib.util.find_spec("llmlingua") is not None
        # Use module-level check so tests can monkeypatch the cutctx transform availability
        llmlingua_module_py = importlib.util.find_spec("cutctx.transforms.llmlingua_compressor") is not None

        try:
            from cutctx.binaries import find_difftastic

            difft_path = find_difftastic(getattr(proxy.config, "difftastic_binary", "difft"))
        except Exception:
            difft_path = None

        try:
            from cutctx.transforms.drain3_compressor import drain3_available

            drain3_ready = bool(drain3_available())
        except Exception:
            drain3_ready = False
        try:
            from cutctx.memory.backends.usearch_store import usearch_available

            usearch_ready = bool(usearch_available())
        except Exception:
            usearch_ready = False

        model_router = getattr(proxy, "_model_router", None)
        model_router_config = getattr(model_router, "config", None)
        model_router_enabled = bool(getattr(model_router_config, "enabled", False))
        model_router_routes = list(getattr(model_router_config, "routes", []) or [])
        model_routing_status = {
            "requested": model_router_enabled,
            "available": model_router is not None,
            "configured_routes": len(model_router_routes),
            "reason": (
                "router_uninitialized"
                if model_router is None
                else "no_routes_configured"
                if model_router_enabled and not model_router_routes
                else None
            ),
            "install_hint": "configure CUTCTX_MODEL_ROUTING or a [model_routing] block in cutctx.toml",
        }

        return {
            "knowledge_graph": {
                "requested": bool(getattr(proxy.config, "knowledge_graph_enabled", False)),
                "available": graphify_py and networkx_py,
                "knowledge_graph_engine_installed": graphify_py,
                "graph_utilities_installed": networkx_py,
                "reason": (
                    None
                    if graphify_py and networkx_py
                    else "knowledge_graph_engine_missing"
                    if not graphify_py
                    else "graph_utilities_missing"
                ),
                "install_hint": "pip install cutctx-ai[knowledge-graph]",
            },
            "log_template_mining": {
                "requested": bool(getattr(proxy.config, "use_drain3", False)),
                "available": drain3_ready,
                "reason": None if drain3_ready else "log_template_mining_missing",
                "install_hint": "pip install cutctx-ai[log-ml]",
            },
            "structural_diff_engine": {
                "requested": bool(getattr(proxy.config, "difftastic_enabled", False)),
                "available": difft_path is not None,
                "binary": str(difft_path) if difft_path else None,
                "reason": None if difft_path is not None else "difft_binary_missing",
                "install_hint": "brew install structural-diff-engine or cargo install structural-diff-engine",
            },
            "text_compression_engine": {
                "available": llmlingua_py,
                "reason": None if llmlingua_py else "text_compression_engine_missing",
                "install_hint": "pip install cutctx-ai[text-compression]",
            },
            "multimodal_image": {
                "requested": False,
                "available": pillow_py,
                "reason": None if pillow_py else "pillow_missing",
                "install_hint": "pip install cutctx-ai[image]",
            },
            "smart_crusher": {
                "requested": True,  # always attempted when Rust ext is available
                "available": importlib.util.find_spec("cutctx._core") is not None,
                "reason": None if importlib.util.find_spec("cutctx._core") is not None else "rust_extension_not_built",
                "install_hint": "pip install cutctx-ai  # built wheel includes _core.so",
            },
            "kompress": {
                "requested": False,
                "available": importlib.util.find_spec("onnxruntime") is not None,
                "reason": None if importlib.util.find_spec("onnxruntime") is not None else "ml_inference_runtime_missing",
                "install_hint": "pip install cutctx-ai[proxy]  # ml_inference_runtime is in [proxy]",
            },
            "html_extractor": {
                "requested": False,
                "available": importlib.util.find_spec("trafilatura") is not None,
                "reason": None if importlib.util.find_spec("trafilatura") is not None else "html_extraction_engine_missing",
                "install_hint": "pip install cutctx-ai[html]",
            },
            "voice_filler": {
                "requested": False,
                "available": importlib.util.find_spec("torch") is not None,
                "reason": None if importlib.util.find_spec("torch") is not None else "ml_framework_missing",
                "install_hint": "pip install cutctx-ai[voice]",
            },
            "code_ast": {
                "requested": False,
                "available": importlib.util.find_spec("tree_sitter_language_pack") is not None,
                "reason": None if importlib.util.find_spec("tree_sitter_language_pack") is not None else "code_parsing_engine_missing",
                "install_hint": "pip install cutctx-ai[code]",
            },
            "audio": {
                "requested": True,
                "available": True,
                "compression": "pass-through",
                "reason": "audio_proxy_only_no_token_compression",
                "install_hint": None,
            },
    }
    '''

    def _feature_availability_snapshot() -> dict[str, dict[str, Any]]:
        """Surface optional best-in-class features actually usable."""
        graphify_py = importlib.util.find_spec("graphifyy") is not None or importlib.util.find_spec("graphify") is not None
        networkx_py = importlib.util.find_spec("networkx") is not None
        pillow_py = importlib.util.find_spec("PIL") is not None
        llmlingua_py = importlib.util.find_spec("llmlingua") is not None
        llmlingua_module_py = importlib.util.find_spec("cutctx.transforms.llmlingua_compressor") is not None
        rust_core_py = importlib.util.find_spec("cutctx._core") is not None
        onnxruntime_py = importlib.util.find_spec("onnxruntime") is not None
        trafilatura_py = importlib.util.find_spec("trafilatura") is not None
        torch_py = importlib.util.find_spec("torch") is not None
        tree_sitter_py = importlib.util.find_spec("tree_sitter_language_pack") is not None
        try:
            from cutctx.binaries import find_difftastic

            difft_path = find_difftastic(getattr(proxy.config, "difftastic_binary", "difft"))
        except Exception:
            difft_path = None

        try:
            from cutctx.transforms.drain3_compressor import drain3_available

            drain3_ready = bool(drain3_available())
        except Exception:
            drain3_ready = False

        try:
            from cutctx.memory.backends.usearch_store import usearch_available

            usearch_ready = bool(usearch_available())
        except Exception:
            usearch_ready = False

        model_router = getattr(proxy, "_model_router", None)
        model_router_config = getattr(model_router, "config", None)
        model_router_enabled = bool(getattr(model_router_config, "enabled", False))
        model_router_routes = list(getattr(model_router_config, "routes", []) or [])
        model_router_route_count = len(model_router_routes)

        return {
            "knowledge_graph": {
                "requested": bool(getattr(proxy.config, "knowledge_graph_enabled", False)),
                "available": graphify_py and networkx_py,
                "knowledge_graph_engine_installed": graphify_py,
                "graph_utilities_installed": networkx_py,
                "reason": None if graphify_py and networkx_py else "knowledge_graph_engine_missing" if not graphify_py else "graph_utilities_missing",
                "install_hint": "pip install cutctx-ai[knowledge-graph]",
            },
            "log_template_mining": {
                "requested": bool(getattr(proxy.config, "use_drain3", False)),
                "available": drain3_ready,
                "reason": None if drain3_ready else "log_template_mining_missing",
                "install_hint": "pip install cutctx-ai[log-ml]",
            },
            "structural_diff_engine": {
                "requested": bool(getattr(proxy.config, "difftastic_enabled", False)),
                "available": difft_path is not None,
                "binary": str(difft_path) if difft_path else None,
                "reason": None if difft_path is not None else "difft_binary_missing",
                "install_hint": "brew install structural-diff-engine or cargo install structural-diff-engine",
            },
            "text_compression_engine": {
                "requested": bool(getattr(proxy.config, "use_llmlingua", False)),
                "available": llmlingua_py and llmlingua_module_py,
                "reason": None if llmlingua_py and llmlingua_module_py else "text_compression_runtime_missing" if llmlingua_py else "text_compression_engine_missing",
                "install_hint": "pip install cutctx-ai[llmlingua]",
            },
            "multimodal_image": {
                "requested": False,
                "available": pillow_py,
                "reason": None if pillow_py else "pillow_missing",
                "install_hint": "pip install cutctx-ai[image]",
            },
            "smart_crusher": {
                "requested": True,
                "available": rust_core_py,
                "reason": None if rust_core_py else "rust_extension_not_built",
                "install_hint": "pip install cutctx-ai",
            },
            "kompress": {
                "requested": False,
                "available": onnxruntime_py,
                "reason": None if onnxruntime_py else "ml_inference_runtime_missing",
                "install_hint": "pip install cutctx-ai[proxy]",
            },
            "html_extractor": {
                "requested": False,
                "available": trafilatura_py,
                "reason": None if trafilatura_py else "html_extraction_engine_missing",
                "install_hint": "pip install cutctx-ai[html]",
            },
            "voice_filler": {
                "requested": False,
                "available": torch_py,
                "reason": None if torch_py else "ml_framework_missing",
                "install_hint": "pip install cutctx-ai[voice]",
            },
            "code_ast": {
                "requested": False,
                "available": tree_sitter_py,
                "reason": None if tree_sitter_py else "code_parsing_engine_missing",
                "install_hint": "pip install cutctx-ai[code]",
            },
            "stack_graph": {
                "requested": bool(getattr(proxy.config, "stack_graph_enabled", False)),
                "available": stack_graph_available(),
                "active": bool(getattr(proxy, "stack_graph_resolver", None)),
                "reason": None if stack_graph_available() else "stack_graph_extension_not_built",
                "install_hint": "pip install cutctx-ai[dev] or build the Rust extension for stack-graph support",
            },
            "usearch": {
                "requested": False,
                "available": usearch_ready,
                "reason": None if usearch_ready else "usearch_package_missing",
                "install_hint": "pip install cutctx-ai[memory] or pip install usearch",
            },
            "model_routing": {
                "requested": model_router_enabled,
                "available": model_router is not None,
                "configured_routes": model_router_route_count,
                "reason": (
                    "router_uninitialized"
                    if model_router is None
                    else "no_routes_configured"
                    if model_router_enabled and model_router_route_count == 0
                    else None
                ),
                "install_hint": "configure CUTCTX_MODEL_ROUTING or a [model_routing] block in cutctx.toml",
            },
            "audio": {
                "requested": True,
                "available": True,
                "compression": "pass-through",
                "reason": "audio_proxy_only_no_token_compression",
                "install_hint": None,
            },
        }

    # ── SSO token validation dependency ────────────────────────────────
    # When SSO is configured, validates Bearer tokens against the enterprise
    # IdP. Adds X-Cutctx-Sso-Role header so RBAC can resolve from SSO claims.
    _sso_validator_ref = None
    try:
        from cutctx.sso import SsoConfig, SsoValidator

        _sso_config = SsoConfig.from_proxy_config(config)
        if _sso_config.enabled:
            _sso_validator_ref = SsoValidator(_sso_config)
            logger.info("SSO validation enabled (provider: %s)", _sso_config.provider_type)
    except Exception:
        logger.debug("SSO validator not available", exc_info=True)

    async def _validate_sso_token(request: Request):
        """Dependency that validates SSO tokens and injects role into headers."""
        if _sso_validator_ref is None:
            return  # No SSO configured
        try:
            await _authenticate_admin_request(request)
        except HTTPException:
            return

    # Entitlement enforcement dependency.
    # Usage: Depends(_require_entitlement("team_analytics"))
    # Returns the entitlement checker for further use. Raises 403 if the
    # current tier doesn't include the requested feature.
    #
    # FAIL-CLOSED: If the checker is unavailable, default to BUILDER tier
    # (most restrictive paid tier — allows core compression, denies all
    # paid features). This prevents accidental exposure of paid features
    # when the entitlement system fails to initialize.
    #
    # 2.5 FIX: Periodic refresh — re-read the license cache every 5 minutes
    # so tier changes (upgrades/downgrades) take effect without restart.
    _ENTITLEMENT_REFRESH_TTL = 300.0  # seconds

    class _RefreshingEntitlementChecker:
        """Wraps EntitlementChecker and periodically re-reads the license cache."""

        def __init__(self, initial_checker: Any, refresh_ttl: float = _ENTITLEMENT_REFRESH_TTL):
            self._checker = initial_checker
            self._refresh_ttl = refresh_ttl
            self._last_refresh: float = time.monotonic()
            self._license_cache_path: Any = None
            try:
                from cutctx import paths
                self._license_cache_path = paths.license_cache_path()
            except Exception:
                pass

        @property
        def checker(self) -> Any:
            self._maybe_refresh()
            return self._checker

        def _maybe_refresh(self) -> None:
            now = time.monotonic()
            if now - self._last_refresh < self._refresh_ttl:
                return
            self._last_refresh = now
            try:
                if self._license_cache_path is None or not self._license_cache_path.exists():
                    return
                from cutctx.security.state_crypto import read_hmac_json
                cache = read_hmac_json(self._license_cache_path)
                if cache is None:
                    return
                plan = cache.get("plan", "builder")
                from cutctx.entitlements import EntitlementChecker
                new_checker = EntitlementChecker(plan)
                if new_checker.tier != self._checker.tier:
                    logger.info(
                        "Entitlement tier refreshed: %s -> %s (from license cache)",
                        self._checker.plan_name,
                        new_checker.plan_name,
                    )
                    self._checker = new_checker
            except Exception:
                logger.debug("Entitlement refresh failed, keeping current tier", exc_info=True)

    _entitlement_checker_ref = proxy.entitlement_checker
    if _entitlement_checker_ref is None:
        from cutctx.entitlements import EntitlementChecker
        _entitlement_checker_ref = EntitlementChecker("enterprise")
        logger.warning(
            "Entitlement checker unavailable — defaulting to ENTERPRISE tier (fail-open for dashboard)"
        )
    _refreshing_checker = _RefreshingEntitlementChecker(_entitlement_checker_ref)

    def _require_entitlement(feature: str):
        """Factory that returns a dependency checking a specific feature."""

        async def _check(request: Request):
            checker = _refreshing_checker.checker
            if not checker.is_entitled(feature):
                from cutctx.entitlements import FEATURE_TIERS

                required = FEATURE_TIERS.get(feature)
                # Log the denial
                try:
                    from cutctx.audit import AuditEvent, get_audit_logger

                    await get_audit_logger().async_log(
                        AuditEvent(
                            action="entitlement.denied",
                            actor=request.headers.get("x-cutctx-user-id", "anonymous"),
                            detail={
                                "feature": feature,
                                "required_tier": required.name if required else "unknown",
                                "current_tier": checker.plan_name,
                                "path": str(request.url.path),
                            },
                            success=False,
                            ip_address=getattr(request.client, "host", None),
                            user_agent=request.headers.get("user-agent"),
                        )
                    )
                except Exception:
                    logger.debug("Failed to log entitlement denial", exc_info=True)
                raise HTTPException(
                    status_code=403,
                    detail={
                        "error": "feature_not_available",
                        "feature": feature,
                        "required_tier": required.name.lower() if required else "unknown",
                        "current_tier": checker.plan_name,
                        "upgrade_url": upgrade_url(checker.plan_name),
                        "contact": "hello@cutctx.dev",
                    },
                )

        return _check

    # X-Cutctx-Stack: SDK adapters (TS openai/anthropic/etc.) tag their
    # requests so telemetry can segment by integration surface. Registered
    # before extension middleware so any extension-level auth/guards run
    # outermost and we don't count requests they reject.
    @app.middleware("http")
    async def _record_cutctx_stack(request, call_next):
        started = time.perf_counter()
        inbound_id = f"inbound-{time.time_ns()}"
        # Project attribution: an explicit X-Cutctx-Project header wins
        # (claude/codex wraps); otherwise a /p/<name> base-URL prefix (aider,
        # Copilot BYOK, Cursor — clients that cannot send custom headers).
        # The prefix strip mutates the scope, so it must happen before
        # request.url is first accessed (Starlette caches the URL).
        prefix_project = strip_project_path_prefix(request.scope)
        path = request.url.path
        method = request.method
        query = request.url.query
        headers = dict(request.headers.items())
        set_current_project(classify_project(headers) or prefix_project)
        client = getattr(request, "client", None)
        client_addr = ""
        if client is not None:
            client_host = getattr(client, "host", None)
            client_port = getattr(client, "port", None)
            client_addr = f"{client_host}:{client_port}" if client_port else str(client_host)
        try:
            proxy.metrics.record_inbound_request(method=method, path=path)
        except Exception:
            logger.debug("record_inbound_request failed", exc_info=True)
        try:
            from cutctx.proxy.helpers import redact_for_wire_debug

            safe_headers = redact_for_wire_debug(headers)
        except Exception:
            safe_headers = {"redaction_error": True}
        logger.info(
            "event=proxy_inbound_request id=%s method=%s path=%s query=%s client=%s "
            "content_length=%s headers=%s",
            inbound_id,
            method,
            path,
            query,
            client_addr,
            request.headers.get("content-length", ""),
            json.dumps(safe_headers, ensure_ascii=False, default=str),
        )
        if request.url.path.startswith("/v1/"):
            stack = request.headers.get("x-cutctx-stack")
            if stack:
                try:
                    proxy.metrics.record_stack(stack)
                except Exception:
                    logger.debug("record_stack failed", exc_info=True)
        try:
            response = await call_next(request)
        except asyncio.CancelledError:
            try:
                proxy.metrics.record_inbound_aborted(reason="cancelled")
            except Exception:
                logger.debug("record_inbound_aborted failed", exc_info=True)
            logger.info(
                "event=proxy_inbound_request_aborted id=%s method=%s path=%s reason=cancelled "
                "duration_ms=%.2f",
                inbound_id,
                method,
                path,
                (time.perf_counter() - started) * 1000.0,
            )
            raise
        except Exception as exc:
            try:
                proxy.metrics.record_inbound_aborted(reason=type(exc).__name__)
            except Exception:
                logger.debug("record_inbound_aborted failed", exc_info=True)
            logger.error(
                "event=proxy_inbound_request_aborted id=%s method=%s path=%s reason=%s "
                "duration_ms=%.2f",
                inbound_id,
                method,
                path,
                type(exc).__name__,
                (time.perf_counter() - started) * 1000.0,
                exc_info=True,
            )
            raise
        try:
            proxy.metrics.record_inbound_response(status_code=response.status_code)
        except Exception:
            logger.debug("record_inbound_response failed", exc_info=True)
        logger.info(
            "event=proxy_inbound_response id=%s method=%s path=%s status=%s duration_ms=%.2f",
            inbound_id,
            method,
            path,
            response.status_code,
            (time.perf_counter() - started) * 1000.0,
        )
        return response

    # Third-party proxy extensions (Enterprise, custom plugins). Discovered via
    # the `cutctx.proxy_extension` entry-point group, but **opt-in only**:
    # only names listed in config.proxy_extensions (CLI: --proxy-extension,
    # env: CUTCTX_PROXY_EXTENSIONS) actually get installed. Discovery alone
    # never runs third-party code. An extension that raises from its install()
    # is a deliberate fail-closed signal and aborts startup.
    from cutctx.proxy.extensions import install_all as _install_extensions

    _install_extensions(app, config, enabled=getattr(config, "proxy_extensions", None))

    # Health & Metrics
    @app.get("/livez")
    async def livez():
        return JSONResponse(
            status_code=200,
            content={
                "service": "cutctx-proxy",
                "status": "healthy",
                "alive": True,
                "version": __version__,
                "timestamp": _iso_utc_now(),
                "uptime_seconds": _uptime_seconds(),
            },
        )

    @app.get("/v1/version")
    async def get_v1_version():
        return JSONResponse(status_code=200, content={"version": __version__})

    @app.post("/v1/memory/search")
    async def v1_memory_search():
        return JSONResponse(status_code=501, content={"error": "Not implemented"})

    @app.get("/readyz")
    async def readyz():
        await _check_upstream()
        payload = _health_payload(include_config=False)
        return JSONResponse(status_code=200 if payload["ready"] else 503, content=payload)

    @app.get("/health")
    async def health():
        await _check_upstream()
        payload = _health_payload(include_config=True)
        return JSONResponse(status_code=200, content=payload)



    @app.get("/favicon.svg", include_in_schema=False)
    async def favicon():
        fav_path = react_assets.parent / "favicon.svg"
        if fav_path.exists():
            return FileResponse(fav_path, media_type="image/svg+xml")
        raise HTTPException(status_code=404, detail="favicon not found")

    @app.get("/dashboard", response_class=HTMLResponse)
    @app.get("/dashboard/{path:path}", response_class=HTMLResponse)
    async def dashboard(path: str = ""):
        """Serve the Cutctx dashboard UI, handling client-side routing."""
        return get_dashboard_html(prefer_react=True)

    DASHBOARD_STATS_CACHE_TTL_SECONDS = 5.0
    _stats_snapshot_lock = asyncio.Lock()
    _stats_snapshot: dict[str, Any] = {"expires_at": 0.0, "value": None}

    async def _build_stats_payload() -> dict[str, Any]:
        """Build the full `/stats` response payload.

        This is the main stats endpoint - it aggregates data from all subsystems:
        - Request metrics (total, cached, failed, by model/provider)
        - Token usage and savings
        - Cost tracking
        - Canonical persisted display_session metrics for downstream dashboards
        - Compression (CCR) statistics
        - Telemetry/TOIN (data flywheel) statistics
        - Cache and rate limiter stats
        """
        m = proxy.metrics

        # Calculate average latency
        avg_latency_ms = round(m.latency_sum_ms / m.latency_count, 2) if m.latency_count > 0 else 0
        min_latency_ms = (
            round(m.latency_min_ms, 2)
            if m.latency_count > 0 and m.latency_min_ms != float("inf")
            else 0
        )
        max_latency_ms = round(m.latency_max_ms, 2) if m.latency_count > 0 else 0

        # Calculate Cutctx overhead (optimization time only, excludes pass-through requests)
        avg_overhead_ms = (
            round(m.overhead_sum_ms / m.overhead_count, 2) if m.overhead_count > 0 else 0
        )
        min_overhead_ms = (
            round(m.overhead_min_ms, 2)
            if m.overhead_count > 0 and m.overhead_min_ms != float("inf")
            else 0
        )
        max_overhead_ms = round(m.overhead_max_ms, 2) if m.overhead_count > 0 else 0

        # Calculate TTFB (time to first byte)
        avg_ttfb_ms = round(m.ttfb_sum_ms / m.ttfb_count, 2) if m.ttfb_count > 0 else 0
        min_ttfb_ms = (
            round(m.ttfb_min_ms, 2) if m.ttfb_count > 0 and m.ttfb_min_ms != float("inf") else 0
        )
        max_ttfb_ms = round(m.ttfb_max_ms, 2) if m.ttfb_count > 0 else 0

        def _pct(part: int | float, whole: int | float) -> float:
            return round((float(part) / float(whole)) * 100.0, 2) if whole else 0.0

        # Get compression store stats
        store = get_compression_store()
        compression_stats = store.get_stats()

        # Get telemetry/TOIN stats
        telemetry = get_telemetry_collector()
        telemetry_stats = telemetry.get_stats()

        # Get feedback loop stats
        feedback = get_compression_feedback()
        feedback_stats = feedback.get_stats()

        # Load compression profile for stats exposure (best-effort)
        try:
            from cutctx.profiles import CompressionProfile

            _profile_summary = CompressionProfile.load().summary()
        except Exception:
            _profile_summary = None

        # Compute content router overrides count
        _content_router = getattr(proxy, "_content_router", None)
        _router_overrides_count = (
            len(_content_router.config.per_type_overrides)
            if _content_router is not None and getattr(_content_router, "config", None) is not None
            else 0
        )

        # Build prefix cache stats once (used in both prefix_cache and cost)
        prefix_cache_stats = _build_prefix_cache_stats(m, proxy.cost_tracker)

        # Fetch CLI filtering savings from the selected context tool. These
        # tokens are avoided before they reach model context.
        cli_filtering_stats = await asyncio.to_thread(_get_context_tool_stats)
        cli_filtering_tool = (
            str(cli_filtering_stats.get("tool", "rtk")) if cli_filtering_stats else "rtk"
        )
        cli_filtering_label = (
            str(cli_filtering_stats.get("label", "RTK")) if cli_filtering_stats else "RTK"
        )
        cli_tokens_avoided = (
            cli_filtering_stats.get("tokens_saved", 0) if cli_filtering_stats else 0
        )
        cli_filtering_session = (
            cli_filtering_stats.get("session", {}) if cli_filtering_stats else {}
        )
        cli_filtering_lifetime = (
            cli_filtering_stats.get("lifetime", {}) if cli_filtering_stats else {}
        )
        rtk_tokens_avoided = cli_tokens_avoided if cli_filtering_tool == "rtk" else 0
        lean_ctx_tokens_avoided = cli_tokens_avoided if cli_filtering_tool == "lean-ctx" else 0

        # Calculate total tokens before Cutctx-side reduction. Proxy
        # compression and the configured context tool both remove tokens before
        # they reach model context, so dashboard-facing savings combines them.
        proxy_compression_tokens = m.tokens_saved_total
        all_layers_tokens_saved = proxy_compression_tokens + cli_tokens_avoided
        total_tokens_before = m.tokens_input_total + all_layers_tokens_saved
        proxy_total_before_compression = m.tokens_input_total + proxy_compression_tokens
        # `attempted_input_tokens` is the compressible-only denominator
        # (extracted units + tool schema). The "active compression"
        # ratio is what fraction of the tokens we *tried* to compress
        # actually got compressed. Excludes prefix-frozen content
        # (user/system messages, prior turns) we never touched —
        # otherwise the ratio is dominated by content we deliberately
        # avoided changing for prefix-cache safety.
        # `attempted_input_tokens_total` is already pre-compression: it
        # accumulates `unit.tokens_before` for each eligible unit that
        # reached the router, plus the original (pre-compaction) tool
        # schema size. So the savings rate is plain `saved / attempted`
        # — adding `saved` again would double-count.
        attempted_input_tokens = getattr(m, "attempted_input_tokens_total", 0)

        # Build human-readable summary
        summary = _build_session_summary(
            proxy, m, prefix_cache_stats, cli_tokens_avoided, total_tokens_before
        )
        # DEBUG: log the summary payload for external upsert consumers
        try:
            logger.debug("/stats summary data: %r", summary)
        except Exception:
            logger.warning("Failed to log /stats summary payload")

        # Compression cache stats (token mode). Snapshot the cache list under
        # the dict lock so a concurrent eviction can't mutate the dict while
        # we iterate. Each per-session `get_stats()` is independently
        # thread-safe via the cache's own internal lock.
        compression_cache_stats: dict = {}
        if proxy.config.mode == PROXY_MODE_TOKEN and proxy._compression_caches:
            with proxy._compression_caches_lock:
                _caches_snapshot = list(proxy._compression_caches.values())
                _active_sessions = len(proxy._compression_caches)
            total_entries = 0
            total_hits = 0
            total_misses = 0
            total_tokens_saved = 0
            for cache in _caches_snapshot:
                s = cache.get_stats()
                total_entries += s.get("entries", 0)
                total_hits += s.get("hits", 0)
                total_misses += s.get("misses", 0)
                total_tokens_saved += s.get("total_tokens_saved", 0)
            compression_cache_stats = {
                "mode": PROXY_MODE_TOKEN,
                "active_sessions": _active_sessions,
                "total_entries": total_entries,
                "total_hits": total_hits,
                "total_misses": total_misses,
                "hit_rate": round(total_hits / max(1, total_hits + total_misses) * 100, 1),
                "total_tokens_saved": total_tokens_saved,
            }
        else:
            compression_cache_stats = {"mode": proxy.config.mode}

        # Build unified savings summary (all layers)
        cache_net_usd = prefix_cache_stats.get("totals", {}).get("net_savings_usd", 0.0)
        total_tokens_all_layers = all_layers_tokens_saved
        compression_cache_stats: dict[str, Any] = {"mode": proxy.config.mode}
        if proxy.config.mode == PROXY_MODE_TOKEN and proxy._compression_caches:
            with proxy._compression_caches_lock:
                caches_snapshot = list(proxy._compression_caches.values())
                active_sessions = len(proxy._compression_caches)
            total_entries = 0
            total_hits = 0
            total_misses = 0
            total_tokens_saved = 0
            for cache in caches_snapshot:
                cache_stats = cache.get_stats()
                total_entries += cache_stats.get("entries", 0)
                total_hits += cache_stats.get("hits", 0)
                total_misses += cache_stats.get("misses", 0)
                total_tokens_saved += cache_stats.get("total_tokens_saved", 0)
            compression_cache_stats = {
                "mode": PROXY_MODE_TOKEN,
                "active_sessions": active_sessions,
                "total_entries": total_entries,
                "total_hits": total_hits,
                "total_misses": total_misses,
                "hit_rate": round(total_hits / max(1, total_hits + total_misses) * 100, 1),
                "total_tokens_saved": total_tokens_saved,
            }

        persistent_savings = m.savings_tracker.stats_preview()
        display_session = persistent_savings.get("display_session", {})

        _kg_indexer = getattr(proxy, "knowledge_graph_indexer", None)
        _kg_idx = None
        if _kg_indexer is not None:
            try:
                _kg_idx = _kg_indexer.ensure_ready()
                _kg_stats = _kg_indexer.stats
                proxy.knowledge_graph_status.update(
                    available=bool(_kg_stats.get("available")),
                    active=_kg_idx is not None,
                    status=(
                        "ready"
                        if _kg_idx is not None
                        else "building"
                        if _kg_stats.get("building")
                        else proxy.knowledge_graph_status.get("status", "disabled")
                    ),
                    reason=_kg_stats.get("last_error") or proxy.knowledge_graph_status.get("reason"),
                )
            except Exception as exc:
                proxy.knowledge_graph_status.update(
                    active=False,
                    status="degraded",
                    reason=exc.__class__.__name__,
                )

        savings_sources = tuple(src.value for src in SavingsSource)

        return {
            "summary": summary,
            # Phase 1.4: per-source attribution for the dashboard's
            # "Savings by Source" panel. The dashboard reads this object at
            # ``stats.savings_by_source.{tokens,usd,total_tokens}``
            # so the keys must match exactly. Tokens and USD come
            # from the durable savings_tracker lifetime map so
            # values survive a proxy restart.
            "savings_by_source": {
                "total_tokens": sum(
                    int(
                        persistent_savings.get("lifetime", {}).get(
                            f"savings_by_source_tokens.{src}", 0
                        )
                        or 0
                    )
                    for src in savings_sources
                ),
                "tokens": {
                    src: int(
                        persistent_savings.get("lifetime", {}).get(
                            f"savings_by_source_tokens.{src}", 0
                        )
                        or 0
                    )
                    for src in savings_sources
                },
                "usd": {
                    src: round(
                        float(
                            persistent_savings.get("lifetime", {}).get(
                                f"savings_by_source_usd.{src}", 0.0
                            )
                            or 0.0
                        ),
                        6,
                    )
                    for src in savings_sources
                },
            },
            "savings": {
                "total_tokens": total_tokens_all_layers,
                "per_project": persistent_savings.get("projects", {}),
                "by_layer": {
                    "cli_filtering": {
                        "tool": cli_filtering_tool,
                        "label": cli_filtering_label,
                        "tokens": cli_tokens_avoided,
                        "tokens_saved": cli_tokens_avoided,
                        "session": cli_filtering_session,
                        "lifetime": cli_filtering_lifetime,
                        "session_savings_pct": (
                            cli_filtering_stats.get("session_savings_pct")
                            if cli_filtering_stats
                            else None
                        ),
                        "lifetime_savings_pct": (
                            cli_filtering_stats.get("lifetime_avg_savings_pct")
                            if cli_filtering_stats
                            else None
                        ),
                        "refresh_interval_seconds": (
                            cli_filtering_stats.get("refresh_interval_seconds")
                            if cli_filtering_stats
                            else None
                        ),
                        "included_in": "tokens.saved",
                        "description": (
                            f"Tokens avoided by CLI output filtering ({cli_filtering_label}) "
                            "before reaching context. "
                            "Included in dashboard token savings, but not in dollar savings."
                        ),
                    },
                    "compression": {
                        "tokens": proxy_compression_tokens,
                        "proxy_tokens": proxy_compression_tokens,
                        "cli_filtering_tokens": cli_tokens_avoided,
                        "rtk_tokens": rtk_tokens_avoided,
                        "lean_ctx_tokens": lean_ctx_tokens_avoided,
                        "all_layers_tokens": all_layers_tokens_saved,
                        "description": (
                            "Tokens removed by Cutctx proxy compression. "
                            "Dashboard token savings also includes CLI context-tool filtering."
                        ),
                    },
                    "prefix_cache": {
                        "discount_usd": round(cache_net_usd, 4),
                        "description": (
                            "Cost discount from provider prefix caching. "
                            "Cutctx's CacheAligner improves hit rates; "
                            "baseline caching is provider-native."
                        ),
                    },
                },
            },
            "requests": {
                "total": m.requests_total,
                "cached": m.requests_cached,
                "rate_limited": m.requests_rate_limited,
                "failed": m.requests_failed,
                "by_provider": dict(m.requests_by_provider),
                "by_model": dict(m.requests_by_model),
                "by_stack": dict(m.requests_by_stack),
            },
            "tokens": {
                "input": m.tokens_input_total,
                "output": m.tokens_output_total,
                "saved": all_layers_tokens_saved,
                "proxy_compression_saved": proxy_compression_tokens,
                "cli_filtering_saved": cli_tokens_avoided,
                "rtk_saved": rtk_tokens_avoided,
                "lean_ctx_saved": lean_ctx_tokens_avoided,
                "cli_tokens_avoided": cli_tokens_avoided,
                "proxy_total_before_compression": proxy_total_before_compression,
                "total_before_compression": total_tokens_before,
                "all_layers_saved": all_layers_tokens_saved,
                # Compressible-only denominator: tokens we extracted as
                # candidates + tool-schema tokens we compacted. Excludes
                # frozen-prefix content (user msgs, system prompt, prior
                # turns) that we deliberately don't touch. Already
                # pre-compression — do NOT add `tokens_saved` again.
                "proxy_attempted_tokens": attempted_input_tokens,
                # Active compression: savings as a fraction of what we
                # *tried* to compress. The number the dashboard headline
                # should show — it answers "are we doing well *when we
                # have something to compress?*" rather than diluting the
                # win by frozen-prefix bytes we never touched.
                "active_savings_percent": round(
                    (proxy_compression_tokens / attempted_input_tokens * 100)
                    if attempted_input_tokens > 0
                    else 0,
                    2,
                ),
                # Whole-request ratio kept for transparency. Heavily
                # diluted by frozen prefix on Codex-style requests
                # where most input is non-compressible by design.
                "proxy_savings_percent": round(
                    (proxy_compression_tokens / proxy_total_before_compression * 100)
                    if proxy_total_before_compression > 0
                    else 0,
                    2,
                ),
                "savings_percent": round(
                    (all_layers_tokens_saved / total_tokens_before * 100)
                    if total_tokens_before > 0
                    else 0,
                    2,
                ),
                "all_layers_savings_percent": round(
                    (all_layers_tokens_saved / total_tokens_before * 100)
                    if total_tokens_before > 0
                    else 0,
                    2,
                ),
            },
            "latency": {
                "average_ms": avg_latency_ms,
                "min_ms": min_latency_ms,
                "max_ms": max_latency_ms,
                "total_requests": m.latency_count,
            },
            "overhead": {
                "average_ms": avg_overhead_ms,
                "min_ms": min_overhead_ms,
                "max_ms": max_overhead_ms,
            },
            "ttfb": {
                "average_ms": avg_ttfb_ms,
                "min_ms": min_ttfb_ms,
                "max_ms": max_ttfb_ms,
            },
            "pipeline_timing": {
                name: {
                    "average_ms": round(
                        m.transform_timing_sum[name] / m.transform_timing_count[name], 2
                    ),
                    "max_ms": round(m.transform_timing_max[name], 2),
                    "count": m.transform_timing_count[name],
                }
                for name in sorted(m.transform_timing_sum.keys())
            }
            if m.transform_timing_sum
            else {},
            "intelligence": {
                "autopilot": (
                    proxy.intelligence_pipeline.sync_from_config(proxy.config).autopilot_snapshot()
                    if hasattr(proxy, "intelligence_pipeline")
                    else {"enabled": False}
                ),
                "policies": _policies_summary(),
            },
            "compressions_by_strategy": dict(m.compressions_by_strategy),
            "tokens_saved_by_strategy": dict(m.tokens_saved_by_strategy),
            "codex_ws": {
                "units_total": m.codex_ws_units_total,
                "units_modified_total": m.codex_ws_units_modified_total,
                "units_by_strategy": dict(m.codex_ws_units_by_strategy),
                "units_by_category": dict(m.codex_ws_units_by_category),
                "units_by_content_type": dict(m.codex_ws_units_by_content_type),
                "units_by_text_shape": dict(m.codex_ws_units_by_text_shape),
                "units_to_kompress_total": m.codex_ws_units_to_kompress_total,
                "units_kompress_attempted_total": m.codex_ws_units_kompress_attempted_total,
                "units_to_kompress_percent": _pct(
                    m.codex_ws_units_to_kompress_total,
                    m.codex_ws_units_total,
                ),
                "units_kompress_attempted_percent": _pct(
                    m.codex_ws_units_kompress_attempted_total,
                    m.codex_ws_units_total,
                ),
                "unit_elapsed_ms": {
                    "average": round(
                        m.codex_ws_unit_elapsed_ms_sum / m.codex_ws_units_total,
                        2,
                    )
                    if m.codex_ws_units_total
                    else 0.0,
                    "max": round(m.codex_ws_unit_elapsed_ms_max, 2),
                },
                "unit_bytes_sum": m.codex_ws_unit_bytes_sum,
                "unit_tokens_before_sum": m.codex_ws_unit_tokens_before_sum,
                "unit_tokens_after_sum": m.codex_ws_unit_tokens_after_sum,
                "unit_tokens_saved_sum": m.codex_ws_unit_tokens_saved_sum,
                "frames_attempted_total": m.codex_ws_frames_attempted_total,
                "frames_compressed_total": m.codex_ws_frames_compressed_total,
                "frames_failed_total": m.codex_ws_frames_failed_total,
                "frames_to_kompress_total": m.codex_ws_frames_to_kompress_total,
                "frames_kompress_attempted_total": (m.codex_ws_frames_kompress_attempted_total),
                "frames_to_kompress_percent": _pct(
                    m.codex_ws_frames_to_kompress_total,
                    m.codex_ws_frames_attempted_total,
                ),
                "frames_kompress_attempted_percent": _pct(
                    m.codex_ws_frames_kompress_attempted_total,
                    m.codex_ws_frames_attempted_total,
                ),
                "frame_elapsed_ms": {
                    "average": round(
                        m.codex_ws_frame_elapsed_ms_sum / m.codex_ws_frames_attempted_total,
                        2,
                    )
                    if m.codex_ws_frames_attempted_total
                    else 0.0,
                    "max": round(m.codex_ws_frame_elapsed_ms_max, 2),
                },
                "frame_bytes_before_sum": m.codex_ws_frame_bytes_before_sum,
                "frame_bytes_after_sum": m.codex_ws_frame_bytes_after_sum,
                "frame_attempted_tokens_sum": m.codex_ws_frame_attempted_tokens_sum,
                "frame_tokens_saved_sum": m.codex_ws_frame_tokens_saved_sum,
            },
            "waste_signals": dict(m.waste_signals_total) if m.waste_signals_total else {},
            # ContentRouter protection categories aggregated across the
            # session. Lets operators see, e.g., that 80% of messages
            # were `user_msg` (protected) and only 5% reached the
            # compressor — explains why compression rate is low and
            # whether `--compress-user-messages` would help (#454).
            "router": {
                "route_counts": dict(m.router_route_counts) if m.router_route_counts else {},
            },
            "savings_history": m.savings_history[-100:],  # Last 100 data points
            "display_session": display_session,
            "persistent_savings": persistent_savings,
            "otel": get_otel_metrics_status(),
            "langfuse": get_langfuse_tracing_status(),
            "prefix_cache": prefix_cache_stats,
            "cost": _merge_cost_stats(
                proxy.cost_tracker.stats() if proxy.cost_tracker else None,
                prefix_cache_stats,
                cli_tokens_avoided=cli_tokens_avoided,
            ),
            "compression": {
                "ccr_entries": compression_stats.get("entry_count", 0),
                "ccr_max_entries": compression_stats.get("max_entries", 0),
                "original_tokens_cached": compression_stats.get("total_original_tokens", 0),
                "compressed_tokens_cached": compression_stats.get("total_compressed_tokens", 0),
                "ccr_retrievals": compression_stats.get("total_retrievals", 0),
            },
            "compression_cache": compression_cache_stats,
            "knowledge_graph": {
                **getattr(proxy, "knowledge_graph_status", {}),
                "active": _kg_idx is not None,
                "status": (
                    "ready"
                    if _kg_idx is not None
                    else getattr(proxy, "knowledge_graph_status", {}).get("status", "disabled")
                ),
                **(_kg_indexer.stats if _kg_indexer else {}),
            },
            "stack_graph": {
                "enabled": bool(getattr(proxy, "stack_graph_resolver", None)),
                "files_indexed": getattr(proxy.stack_graph_resolver, "file_count", lambda: 0)()
                    if hasattr(proxy, "stack_graph_resolver") and proxy.stack_graph_resolver else 0,
                "nodes": getattr(proxy.stack_graph_resolver, "node_count", lambda: 0)()
                    if hasattr(proxy, "stack_graph_resolver") and proxy.stack_graph_resolver else 0,
            },
            "feature_availability": _feature_availability_snapshot(),
            "anon_telemetry_shipping": is_telemetry_enabled(),
            "telemetry": {
                "enabled": telemetry_stats.get("enabled", False),
                "total_compressions": telemetry_stats.get("total_compressions", 0),
                "total_retrievals": telemetry_stats.get("total_retrievals", 0),
                "global_retrieval_rate": round(telemetry_stats.get("global_retrieval_rate", 0), 4),
                "tool_signatures_tracked": telemetry_stats.get("tool_signatures_tracked", 0),
                "avg_compression_ratio": round(telemetry_stats.get("avg_compression_ratio", 0), 4),
                "avg_token_reduction": round(telemetry_stats.get("avg_token_reduction", 0), 4),
            },
            "otel": get_otel_metrics_status(),
            "langfuse": get_langfuse_tracing_status(),
            "feedback_loop": {
                "tools_tracked": feedback_stats.get("tools_tracked", 0),
                "total_compressions": feedback_stats.get("total_compressions", 0),
                "total_retrievals": feedback_stats.get("total_retrievals", 0),
                "global_retrieval_rate": round(feedback_stats.get("global_retrieval_rate", 0), 4),
                "tools_with_high_retrieval": sum(
                    1
                    for p in feedback_stats.get("tool_patterns", {}).values()
                    if p.get("retrieval_rate", 0) > 0.3
                ),
            },
            "toin": get_toin().get_stats(),
            "profile": _profile_summary,
            "content_router_overrides_count": _router_overrides_count,
            "context_tool": {
                "configured": cli_filtering_tool,
                "label": cli_filtering_label,
                "available": bool(
                    cli_filtering_stats and cli_filtering_stats.get("installed", False)
                ),
                "stats": cli_filtering_stats,
            },
            "cli_filtering": cli_filtering_stats,
            "proxy_inbound": proxy.metrics.inbound_snapshot(),
            "cache": await proxy.cache.stats() if proxy.cache else None,
            "rate_limiter": await proxy.rate_limiter.stats() if proxy.rate_limiter else None,
            "recent_requests": proxy.logger.get_recent(10) if proxy.logger else [],
            "log_full_messages": proxy.config.log_full_messages if proxy else False,
            "config": {
                "cache": getattr(proxy.config, "cache_enabled", False) if proxy else False,
                "ccr": getattr(proxy.config, "ccr_context_tracking", False) if proxy else False,
                "memory": getattr(proxy.config, "episodic_memory_enabled", False) if proxy else False,
                "firewall": getattr(proxy.config, "firewall_enabled", False) if proxy else False,
                "rate_limiter": getattr(proxy.config, "rate_limit_enabled", False) if proxy else False,
                "orchestrator": bool(getattr(proxy, "_model_router", None) and getattr(proxy._model_router, "config", None) and proxy._model_router.config.enabled) if proxy else False,
            },
            **get_quota_registry().get_all_stats(),
        }

    async def _get_cached_stats_payload() -> dict[str, Any]:
        """Return a short-TTL cached `/stats` snapshot for dashboard polling."""
        now = time.monotonic()
        cached_payload = cast(dict[str, Any] | None, _stats_snapshot.get("value"))
        if cached_payload is not None and now < float(_stats_snapshot["expires_at"]):
            return cached_payload

        async with _stats_snapshot_lock:
            now = time.monotonic()
            cached_payload = cast(dict[str, Any] | None, _stats_snapshot.get("value"))
            if cached_payload is not None and now < float(_stats_snapshot["expires_at"]):
                return cached_payload

            payload = await _build_stats_payload()
            _stats_snapshot["value"] = payload
            _stats_snapshot["expires_at"] = time.monotonic() + DASHBOARD_STATS_CACHE_TTL_SECONDS
            return payload

    @app.post("/admin/config/flags", dependencies=[Depends(_require_admin_auth)])
    async def update_config_flags(request: Request):
        """Update live intelligence layer feature flags at runtime."""
        # Wait for the payload
        payload = await request.json()

        # Apply the changes to the global config object
        if "cache" in payload:
            config.cache_enabled = bool(payload["cache"])
        if "ccr" in payload:
            ccr_enabled = bool(payload["ccr"])
            config.ccr_context_tracking = ccr_enabled
            config.ccr_handle_responses = ccr_enabled
        if "memory" in payload:
            config.episodic_memory_enabled = bool(payload["memory"])
            if config.episodic_memory_enabled and getattr(proxy, "episodic_tracker", None) is None:
                try:
                    from cutctx.intelligence_pipeline import IntelligencePipeline
                    from cutctx.memory.session_tracker import EpisodicSessionTracker
                    from cutctx.memory.store import EpisodicMemoryStore

                    store = EpisodicMemoryStore()
                    intel = IntelligencePipeline(config)
                    proxy.episodic_tracker = EpisodicSessionTracker(store, intel, proxy.logger)
                except ImportError as e:
                    logger.warning(f"Could not load memory dependencies: {e}")
        if "firewall" in payload:
            config.firewall_enabled = bool(payload["firewall"])
        if "rate_limiter" in payload:
            config.rate_limit_enabled = bool(payload["rate_limiter"])
        if "orchestrator" in payload:
            if hasattr(proxy, "_model_router") and proxy._model_router is not None:
                proxy._model_router.config.enabled = bool(payload["orchestrator"])

        logger.info(f"Runtime configuration updated: {payload}")
        return {
            "status": "success",
            "config": {
                "cache": getattr(config, "cache_enabled", False),
                "ccr": getattr(config, "ccr_context_tracking", False),
                "memory": getattr(config, "episodic_memory_enabled", False),
                "firewall": getattr(config, "firewall_enabled", False),
                "rate_limiter": getattr(config, "rate_limit_enabled", False),
                "orchestrator": bool(getattr(proxy, "_model_router", None) and getattr(proxy._model_router, "config", None) and proxy._model_router.config.enabled) if proxy else False,
            }
        }

    @app.get("/stats", dependencies=[Depends(_require_admin_auth), Depends(_require_rbac_permission("stats.read"))])
    @app.get("/v1/stats", dependencies=[Depends(_require_admin_auth), Depends(_require_rbac_permission("stats.read"))])
    async def stats(cached: bool = False):
        """Get comprehensive proxy statistics.

        This is the main stats endpoint - it aggregates data from all subsystems:
        - Request metrics (total, cached, failed, by model/provider)
        - Token usage and savings
        - Cost tracking
        - Canonical persisted display_session metrics for downstream dashboards
        - Compression (CCR) statistics
        - Telemetry/TOIN (data flywheel) statistics
        - Cache and rate limiter stats

        Use ``?cached=1`` for the dashboard fast path. That returns a short-TTL
        snapshot to avoid rebuilding the full payload on every UI poll.
        """
        if cached:
            return await _get_cached_stats_payload()
        return await _build_stats_payload()

    @app.post("/stats/reset", dependencies=[Depends(_require_admin_auth), Depends(_require_rbac_permission("stats.reset"))])
    async def stats_reset(request: Request):
        """Reset in-memory proxy stats for local test/debug isolation."""
        await proxy.metrics.reset_runtime()
        if proxy.cost_tracker:
            proxy.cost_tracker.reset_runtime()
        await initialize_context_tool_session_baseline()
        async with _stats_snapshot_lock:
            _stats_snapshot["value"] = None
            _stats_snapshot["expires_at"] = 0.0
        # Audit the reset
        if proxy.audit_logger:
            try:
                from cutctx.audit import AuditEvent
                from cutctx.proxy.routes.admin import _resolve_audit_actor

                # Audit-Deep-2026-06-21 Blocker 6: use the shared actor
                # resolver so the audit attribution matches the
                # sso: > key: > admin hierarchy used by every other
                # admin path. The previous code took the actor from a
                # client-controllable X-Cutctx-User-Id header, which
                # let a caller with a valid admin key forge audit
                # attribution.
                await proxy.audit_logger.async_log(
                    AuditEvent(
                        action="stats.reset",
                        actor=_resolve_audit_actor(request),
                        detail={},
                        ip_address=getattr(request.client, "host", None),
                    )
                )
            except Exception as exc:
                logger.warning("Failed to audit stats reset: %s", exc)
        return JSONResponse(status_code=200, content={"status": "reset"})

    @app.get("/stats-history", dependencies=[Depends(_require_admin_auth), Depends(_require_rbac_permission("stats.history"))])
    async def stats_history(
        format: Literal["json", "csv"] = "json",
        series: Literal["history", "hourly", "daily", "weekly", "monthly"] = "history",
        history_mode: Literal["compact", "full", "none"] = "compact",
    ):
        """Get durable proxy compression history plus display-session state."""
        if format == "csv":
            filename = f"cutctx-stats-history-{series}.csv"
            return Response(
                content=proxy.metrics.savings_tracker.export_csv(series=series),
                media_type="text/csv; charset=utf-8",
                headers={"Content-Disposition": f'attachment; filename="{filename}"'},
            )

        return proxy.metrics.savings_tracker.history_response(history_mode=history_mode)

    @app.get("/transformations/feed", dependencies=[Depends(_require_admin_auth), Depends(_require_rbac_permission("transformations.read"))])
    async def transformations_feed(limit: int = 20):
        """Get recent message transformations for the live feed.

        Returns empty list if log_full_messages is disabled (messages are not stored).
        """
        if limit > 100:
            limit = 100

        transformations = []
        log_full_messages = proxy.config.log_full_messages if proxy else False

        if proxy and proxy.logger:
            logs = proxy.logger.get_recent_with_messages(limit)
            for log in logs:
                transformations.append(
                    {
                        "request_id": log.get("request_id"),
                        "timestamp": log.get("timestamp"),
                        "provider": log.get("provider"),
                        "model": log.get("model"),
                        "input_tokens_original": log.get("input_tokens_original"),
                        "input_tokens_optimized": log.get("input_tokens_optimized"),
                        "tokens_saved": log.get("tokens_saved"),
                        "savings_percent": log.get("savings_percent"),
                        "transforms_applied": log.get("transforms_applied", []),
                        "request_messages": log.get("request_messages"),
                        "compressed_messages": log.get("compressed_messages"),
                        "response_content": log.get("response_content"),
                        "turn_id": log.get("turn_id"),
                    }
                )

        return {"transformations": transformations, "log_full_messages": log_full_messages}

    # ── Enterprise admin routes (extracted to routes/admin.py) ──────
    from cutctx.proxy.routes import create_admin_router

    app.include_router(
        create_admin_router(
            proxy,
            config,
            require_admin_auth=_require_local_admin_auth,
            require_rbac_permission=None,
            require_entitlement=_require_entitlement,
            firewall_scanner=_firewall_scanner,
        )
    )

    # ── License validation + Stripe webhook routes ──────────────────
    # Blocker-1: every EE-facing router in this block is built via a
    # factory that accepts the auth dependencies and applies them to
    # every endpoint. The Stripe webhook is the only exception — it
    # uses HMAC signature verification, not admin auth.
    try:
        from cutctx.proxy.routes.license_validation import (
            create_license_validation_router,
        )

        app.include_router(
            create_license_validation_router(
                require_admin_auth=_require_local_admin_auth,
                require_rbac_permission=None,
            )
        )
    except ImportError:
        pass

    try:
        from cutctx.proxy.routes.spend import create_spend_router

        app.include_router(
            create_spend_router(
                require_admin_auth=_require_local_admin_auth,
                require_rbac_permission=None,
            )
        )
    except ImportError:
        pass

    try:
        from cutctx.proxy.routes.policy import create_policy_router

        app.include_router(
            create_policy_router(
                require_admin_auth=_require_local_admin_auth,
                require_rbac_permission=None,
            )
        )
    except ImportError:
        pass

    try:
        from cutctx.proxy.routes.license import create_license_router

        app.include_router(
            create_license_router(
                require_admin_auth=_require_local_admin_auth,
                require_rbac_permission=None,
            )
        )
    except ImportError:
        pass

    try:
        from cutctx.proxy.routes.audit import create_audit_router

        app.include_router(
            create_audit_router(
                require_admin_auth=_require_local_admin_auth,
                require_rbac_permission=None,
            )
        )
    except ImportError:
        pass

    # Team Memory Service: same pattern — admin auth + memory.write RBAC.
    try:
        from cutctx.proxy.routes.memory import create_memory_router

        app.include_router(
            create_memory_router(
                require_admin_auth=_require_local_admin_auth,
                require_rbac_permission=None,
            )
        )
    except ImportError:
        pass

    # MFA (TOTP) enrollment + management — admin auth + mfa.write RBAC.
    # Audit-Deep-2026-06-21 High-12: the second-factor admin
    # auth surface lives behind the same auth pattern as the
    # other admin routes.
    try:
        from cutctx.proxy.routes.mfa import create_mfa_router

        app.include_router(
            create_mfa_router(
                require_admin_auth=_require_local_admin_auth,
                require_rbac_permission=None,
            )
        )
    except ImportError:
        pass

    # GDPR/CCPA DSR (Data Subject Request) endpoints -- admin auth +
    # privacy.dsr RBAC. Router takes the live proxy so it can
    # reach the configured memory subsystem for export/delete.
    try:
        from cutctx.proxy.routes.dsr import create_dsr_router

        app.include_router(
            create_dsr_router(
                proxy=proxy,
                require_admin_auth=_require_local_admin_auth,
                require_rbac_permission=None,
            )
        )
    except ImportError:
        pass

    # Residency proof: gated behind admin auth + residency.read RBAC.
    # The route exposes the data-region list, egress blocklist, and audit
    # chain tail hash — none of which should be world-readable (round-4 P0).
    try:
        from cutctx.proxy.routes.residency import create_residency_router

        app.include_router(
            create_residency_router(
                require_admin_auth=_require_local_admin_auth,
                require_rbac_permission=None,
            )
        )
        logger.debug("Residency proof route mounted at /v1/residency/proof")
    except ImportError:
        pass

    try:
        from cutctx.proxy.routes.rbac import create_rbac_router

        app.include_router(
            create_rbac_router(
                require_admin_auth=_require_local_admin_auth,
                require_rbac_permission=None,
            )
        )
    except ImportError:
        pass

    try:
        from cutctx.proxy.routes.sso import create_sso_router

        app.include_router(
            create_sso_router(
                require_admin_auth=_require_local_admin_auth,
                require_rbac_permission=None,
            )
        )
    except ImportError:
        pass

    try:
        from cutctx.proxy.routes.rate_limit import create_rate_limit_router

        app.include_router(
            create_rate_limit_router(
                require_admin_auth=_require_local_admin_auth,
                require_rbac_permission=None,
            )
        )
    except ImportError:
        pass

    try:
        from cutctx.proxy.routes.airgap import create_airgap_router

        app.include_router(
            create_airgap_router(
                require_admin_auth=_require_local_admin_auth,
                require_rbac_permission=None,
            )
        )
    except ImportError:
        pass

    try:
        from cutctx.proxy.routes.secrets import create_secrets_router

        app.include_router(
            create_secrets_router(
                require_admin_auth=_require_local_admin_auth,
                require_rbac_permission=None,
            )
        )
    except ImportError:
        pass

    # Provider failover admin: requires admin auth + providers.write RBAC.
    # The create_failover_router factory accepts an injected FailoverRouter
    # so this site is the only one that touches the proxy state for these
    # routes. We only mount it if a FailoverRouter is configured.
    failover_router = getattr(proxy, "failover_router", None)
    if failover_router is not None:
        try:
            from cutctx.proxy.routes.failover import create_failover_router

            app.include_router(
                create_failover_router(
                    failover_router=failover_router,
                    require_admin_auth=_require_local_admin_auth,
                    require_rbac_permission=None,
                )
            )
        except ImportError:
            pass


    register_provider_routes(app, proxy)

    return app


def _json_ready(value: Any) -> Any:
    if is_dataclass(value) and not isinstance(value, type):
        return {field.name: _json_ready(getattr(value, field.name)) for field in fields(value)}
    if isinstance(value, dict):
        return {str(key): _json_ready(item) for key, item in value.items()}
    if isinstance(value, list | tuple | set):
        return [_json_ready(item) for item in value]
    return value


def _proxy_config_payload(config: ProxyConfig) -> dict[str, Any]:
    payload: dict[str, Any] = {}
    for field in fields(config):
        value = _json_ready(getattr(config, field.name))
        try:
            json.dumps(value)
        except TypeError:
            continue
        payload[field.name] = value
    return payload


def _proxy_config_from_env() -> ProxyConfig:
    raw_config = os.environ.get(_MULTI_WORKER_CONFIG_ENV)
    if raw_config:
        try:
            return ProxyConfig(**json.loads(raw_config))
        except (TypeError, ValueError, json.JSONDecodeError):
            logger.warning(
                "Invalid %s; falling back to CUTCTX_* env vars", _MULTI_WORKER_CONFIG_ENV
            )

    return ProxyConfig(
        host=_get_env_str("CUTCTX_HOST", "127.0.0.1"),
        port=_get_env_int("CUTCTX_PORT", 8787),
        openai_api_url=os.environ.get("OPENAI_TARGET_API_URL"),
        anthropic_api_url=os.environ.get("ANTHROPIC_TARGET_API_URL"),
        vertex_api_url=os.environ.get("VERTEX_TARGET_API_URL"),
        backend=_get_env_str("CUTCTX_BACKEND", "anthropic"),
        bedrock_region=_get_env_str("CUTCTX_BEDROCK_REGION", "us-west-2"),
        bedrock_profile=os.environ.get("AWS_PROFILE"),
        anyllm_provider=_get_env_str("CUTCTX_ANYLLM_PROVIDER", "openai"),
        disable_kompress=_get_env_bool("CUTCTX_DISABLE_KOMPRESS", False),
        max_connections=_get_env_int("CUTCTX_MAX_CONNECTIONS", 500),
        max_keepalive_connections=_get_env_int("CUTCTX_MAX_KEEPALIVE", 100),
        http2=_get_env_bool("CUTCTX_HTTP2", True),
        mode=normalize_proxy_mode(_get_env_str("CUTCTX_MODE", PROXY_MODE_TOKEN)),
    )


# Backward-compat alias (pre-db7f7a4 rebrand).
# Audit-Deep-2026-06-21: the CutctxProxy class was renamed
# from CutctxProxy but ~8 test files still reference the
# old name. The alias below keeps the rename and the test
# suite green at the same time. Will be removed in the next
# minor release.
CutctxProxy = CutctxProxy


def create_app(config: ProxyConfig | None = None) -> FastAPI:
    """Create the runtime FastAPI app for dashboard and proxy surfaces."""
    if not FASTAPI_AVAILABLE:
        raise ImportError("FastAPI required. Install: pip install fastapi uvicorn httpx")

    _setup_file_logging()
    from cutctx.proxy.airgap import check_offline_compat

    check_offline_compat()
    config = config or ProxyConfig()
    proxy = CutctxProxy(config)
    from cutctx.telemetry.beacon import TelemetryBeacon

    _beacon = TelemetryBeacon(
        port=config.port if hasattr(config, "port") else 8787,
        sdk=os.environ.get("CUTCTX_SDK", "proxy").strip() or "proxy",
        backend=config.backend if hasattr(config, "backend") else "anthropic",
    )

    @contextlib.asynccontextmanager
    async def _lifespan(_: FastAPI):
        configure_otel_metrics(OTelMetricsConfig.from_env(default_service_name="cutctx-proxy"))
        configure_langfuse_tracing(
            LangfuseTracingConfig.from_env(default_service_name="cutctx-proxy")
        )
        await proxy.startup()
        try:
            yield
        finally:
            await proxy.shutdown()
            shutdown_cutctx_tracing()
            shutdown_otel_metrics()

    app = FastAPI(
        title="Cutctx Proxy",
        description="Production-ready LLM optimization proxy",
        version=__version__,
        lifespan=_lifespan,
    )
    _rust_core_status, _rust_core_error = _check_rust_core()
    app.state.proxy = proxy
    app.state.started_at = time.time()
    app.state.ready = True
    app.state.startup_error = None
    app.state.rust_core_status = _rust_core_status
    app.state.rust_core_error = _rust_core_error

    _firewall_scanner = None
    _streaming_redactor = None
    try:
        from cutctx.security.firewall import FirewallConfig, FirewallScanner, StreamingRedactor

        firewall_config = FirewallConfig(
            enabled=bool(getattr(config, "firewall_enabled", False)),
            block_pii=bool(getattr(config, "firewall_block_pii", True)),
            block_injection=bool(getattr(config, "firewall_block_injection", True)),
            block_jailbreak=bool(getattr(config, "firewall_block_jailbreak", True)),
            redact_streaming=bool(getattr(config, "firewall_redact_streaming", True)),
        )
        if firewall_config.enabled:
            _firewall_scanner = FirewallScanner(firewall_config)
            _streaming_redactor = StreamingRedactor(
                enabled=firewall_config.redact_streaming,
            )
            proxy._streaming_redactor = _streaming_redactor
            logger.info(
                "LLM Firewall enabled (injection=%s, pii=%s, jailbreak=%s)",
                firewall_config.block_injection,
                firewall_config.block_pii,
                firewall_config.block_jailbreak,
            )
    except Exception:
        logger.debug("LLM Firewall not available", exc_info=True)

    try:
        import cutctx_ee.memory_service.api as team_memory_api
        from cutctx_ee.memory_service.store import MemoryStore as TeamMemoryStore

        team_memory_db_path = getattr(config, "memory_db_path", "") or str(
            Path.cwd() / ".cutctx" / "memory.db"
        )
        Path(team_memory_db_path).parent.mkdir(parents=True, exist_ok=True)
        team_memory_api._store = TeamMemoryStore(f"sqlite:///{team_memory_db_path}")
    except Exception:
        logger.debug("Team memory service not available", exc_info=True)

    try:
        from cutctx.proxy.model_router import ModelRouter

        proxy._model_router = ModelRouter()
        if getattr(proxy._model_router.config, "enabled", False):
            config.orchestrator_enabled = True
            logger.info(
                "ModelRouter enabled with %d routes",
                len(getattr(proxy._model_router.config, "routes", [])),
            )
    except Exception:
        logger.debug("ModelRouter not bound in runtime app", exc_info=True)
        proxy._model_router = None

    stats_cache_ttl_seconds = 5.0
    stats_snapshot: dict[str, Any] = {"value": None, "expires_at": 0.0}
    stats_snapshot_lock = asyncio.Lock()
    _UPSTREAM_CHECK_TTL = 30.0
    _upstream_check_cache: dict[str, Any] = {
        "expires_at": 0.0,
        "ok": True,
        "error": None,
        "url": None,
    }
    _upstream_check_lock = asyncio.Lock()

    def _upstream_target_url() -> str:
        return proxy.provider_runtime.api_targets.anthropic

    async def _check_upstream() -> None:
        if os.environ.get("CUTCTX_SKIP_UPSTREAM_CHECK", "").strip() == "1":
            _upstream_check_cache["ok"] = True
            _upstream_check_cache["error"] = None
            _upstream_check_cache["expires_at"] = time.monotonic() + _UPSTREAM_CHECK_TTL
            return

        now = time.monotonic()
        if now < float(_upstream_check_cache["expires_at"]):
            return

        async with _upstream_check_lock:
            if time.monotonic() < float(_upstream_check_cache["expires_at"]):
                return

            url = _upstream_target_url()
            _upstream_check_cache["url"] = url
            client = proxy.http_client
            if client is None:
                _upstream_check_cache["ok"] = False
                _upstream_check_cache["error"] = "proxy client not initialised"
                _upstream_check_cache["expires_at"] = time.monotonic() + _UPSTREAM_CHECK_TTL
                return

            try:
                response = await client.head(url, timeout=5.0)
                _upstream_check_cache["ok"] = response.status_code < 500
                _upstream_check_cache["error"] = (
                    None if response.status_code < 500 else f"upstream returned {response.status_code}"
                )
            except Exception as exc:
                _upstream_check_cache["ok"] = False
                _upstream_check_cache["error"] = str(exc)
                _upstream_check_cache["expires_at"] = time.monotonic() + _UPSTREAM_CHECK_TTL

    # Mirror the primary app's CORS behavior in the runtime app branch.
    _cors_origins = getattr(config, "cors_origins", None) or []
    if "*" in _cors_origins:
        _cors_allow_origins = ["*"]
        _cors_allow_credentials = False
    else:
        _cors_allow_origins = _cors_origins
        _cors_allow_credentials = bool(_cors_origins)

    if _cors_allow_origins == ["*"]:
        _cors_methods: list[str] = ["*"]
        _cors_headers: list[str] = ["*"]
    else:
        _cors_methods = ["GET", "POST", "PUT", "DELETE", "PATCH", "OPTIONS"]
        _cors_headers = [
            "Authorization",
            "Content-Type",
            "X-Cutctx-Admin-Key",
            "X-Request-ID",
            "X-Cutctx-MFA-Code",
            "anthropic-version",
            "anthropic-beta",
        ]

    app.add_middleware(
        CORSMiddleware,
        allow_origins=_cors_allow_origins,
        allow_credentials=_cors_allow_credentials,
        allow_methods=_cors_methods,
        allow_headers=_cors_headers,
    )

    async def _build_stats_payload() -> dict[str, Any]:
        m = proxy.metrics
        store = get_compression_store()
        compression_stats = store.get_stats()
        telemetry = get_telemetry_collector()
        telemetry_stats = telemetry.get_stats()
        feedback = get_compression_feedback()
        feedback_stats = feedback.get_stats()
        prefix_cache_stats = _build_prefix_cache_stats(m, proxy.cost_tracker)
        cli_filtering_stats = await asyncio.to_thread(_get_context_tool_stats)
        cli_filtering_tool = str(cli_filtering_stats.get("tool", "rtk")) if cli_filtering_stats else "rtk"
        cli_filtering_label = str(cli_filtering_stats.get("label", "RTK")) if cli_filtering_stats else "RTK"
        cli_tokens_avoided = int(cli_filtering_stats.get("tokens_saved", 0) if cli_filtering_stats else 0)
        graphify_py = importlib.util.find_spec("graphifyy") is not None or importlib.util.find_spec("graphify") is not None
        networkx_py = importlib.util.find_spec("networkx") is not None
        llmlingua_py = importlib.util.find_spec("llmlingua") is not None
        llmlingua_runtime_py = importlib.util.find_spec("cutctx.transforms.llmlingua_compressor") is not None
        pillow_py = importlib.util.find_spec("PIL") is not None
        rust_core_py = importlib.util.find_spec("cutctx._core") is not None
        onnxruntime_py = importlib.util.find_spec("onnxruntime") is not None
        trafilatura_py = importlib.util.find_spec("trafilatura") is not None
        torch_py = importlib.util.find_spec("torch") is not None
        tree_sitter_py = importlib.util.find_spec("tree_sitter_language_pack") is not None

        try:
            from cutctx.binaries import find_difftastic

            difft_path = find_difftastic(getattr(proxy.config, "difftastic_binary", "difft"))
        except Exception:
            difft_path = None

        try:
            from cutctx.transforms.drain3_compressor import drain3_available

            drain3_ready = bool(drain3_available())
        except Exception:
            drain3_ready = False

        try:
            from cutctx.memory.backends.usearch_store import usearch_available

            usearch_ready = bool(usearch_available())
        except Exception:
            usearch_ready = False

        model_router = getattr(proxy, "_model_router", None)
        model_router_config = getattr(model_router, "config", None)
        model_router_enabled = bool(getattr(model_router_config, "enabled", False))
        model_router_routes = list(getattr(model_router_config, "routes", []) or [])
        model_routing_status = {
            "requested": model_router_enabled,
            "available": model_router is not None,
            "configured_routes": len(model_router_routes),
            "reason": (
                "router_uninitialized"
                if model_router is None
                else "no_routes_configured"
                if model_router_enabled and not model_router_routes
                else None
            ),
            "install_hint": "configure CUTCTX_MODEL_ROUTING or a [model_routing] block in cutctx.toml",
        }

        compression_cache_stats: dict[str, Any] = {"mode": proxy.config.mode}
        if proxy.config.mode == PROXY_MODE_TOKEN and proxy._compression_caches:
            with proxy._compression_caches_lock:
                caches_snapshot = list(proxy._compression_caches.values())
                active_sessions = len(proxy._compression_caches)
            total_entries = 0
            total_hits = 0
            total_misses = 0
            total_tokens_saved = 0
            for cache in caches_snapshot:
                cache_stats = cache.get_stats()
                total_entries += cache_stats.get("entries", 0)
                total_hits += cache_stats.get("hits", 0)
                total_misses += cache_stats.get("misses", 0)
                total_tokens_saved += cache_stats.get("total_tokens_saved", 0)
            compression_cache_stats = {
                "mode": PROXY_MODE_TOKEN,
                "active_sessions": active_sessions,
                "total_entries": total_entries,
                "total_hits": total_hits,
                "total_misses": total_misses,
                "hit_rate": round(total_hits / max(1, total_hits + total_misses) * 100, 1),
                "total_tokens_saved": total_tokens_saved,
            }

        persistent_savings = m.savings_tracker.stats_preview()
        display_session = persistent_savings.get("display_session", {})
        savings_sources = tuple(src.value for src in SavingsSource)
        cli_filtering_session = cli_filtering_stats.get("session", {}) if cli_filtering_stats else {}
        cli_filtering_lifetime = cli_filtering_stats.get("lifetime", {}) if cli_filtering_stats else {}
        kg_indexer = getattr(proxy, "knowledge_graph_indexer", None)
        kg_idx = None
        if kg_indexer is not None:
            try:
                ensure_ready = getattr(kg_indexer, "ensure_ready", None)
                if callable(ensure_ready):
                    kg_idx = ensure_ready()
            except Exception:
                kg_idx = None

        total_tokens_before = int(getattr(m, "tokens_input_total", getattr(m, "prompt_tokens_total", 0)) or 0)
        proxy_total_before_compression = int(getattr(m, "attempted_prompt_tokens_total", total_tokens_before) or total_tokens_before)
        attempted_input_tokens = proxy_total_before_compression
        proxy_compression_tokens = int(getattr(m, "tokens_saved_total", getattr(m, "prompt_tokens_saved", 0)) or 0)
        rtk_tokens_avoided = int(cli_filtering_stats.get("rtk_tokens_saved", 0) if cli_filtering_stats else 0)
        lean_ctx_tokens_avoided = int(cli_filtering_stats.get("lean_ctx_tokens_saved", 0) if cli_filtering_stats else 0)
        if cli_tokens_avoided > 0 and rtk_tokens_avoided == 0 and lean_ctx_tokens_avoided == 0:
            if cli_filtering_tool == "lean-ctx":
                lean_ctx_tokens_avoided = cli_tokens_avoided
            else:
                rtk_tokens_avoided = cli_tokens_avoided
        all_layers_tokens_saved = proxy_compression_tokens + cli_tokens_avoided
        requests_total = int(getattr(m, "requests_total", 0) or 0)

        summary = {
            "saved": all_layers_tokens_saved,
            "input": total_tokens_before,
            "proxy_compression_saved": proxy_compression_tokens,
            "cli_filtering_saved": cli_tokens_avoided,
            "rtk_saved": rtk_tokens_avoided,
            "lean_ctx_saved": lean_ctx_tokens_avoided,
            "cli_tokens_avoided": cli_tokens_avoided,
            "proxy_total_before_compression": proxy_total_before_compression,
            "total_before_compression": total_tokens_before,
            "all_layers_saved": all_layers_tokens_saved,
            "proxy_attempted_tokens": attempted_input_tokens,
            "active_savings_percent": round((proxy_compression_tokens / attempted_input_tokens * 100) if attempted_input_tokens > 0 else 0, 2),
            "proxy_savings_percent": round((proxy_compression_tokens / proxy_total_before_compression * 100) if proxy_total_before_compression > 0 else 0, 2),
            "savings_percent": round((all_layers_tokens_saved / total_tokens_before * 100) if total_tokens_before > 0 else 0, 2),
            "all_layers_savings_percent": round((all_layers_tokens_saved / total_tokens_before * 100) if total_tokens_before > 0 else 0, 2),
        }

        return {
            "summary": summary,
            "savings_by_source": {
                "total_tokens": sum(
                    int(
                        persistent_savings.get("lifetime", {}).get(
                            f"savings_by_source_tokens.{src}", 0
                        )
                        or 0
                    )
                    for src in savings_sources
                ),
                "tokens": {
                    src: int(
                        persistent_savings.get("lifetime", {}).get(
                            f"savings_by_source_tokens.{src}", 0
                        )
                        or 0
                    )
                    for src in savings_sources
                },
                "usd": {
                    src: round(
                        float(
                            persistent_savings.get("lifetime", {}).get(
                                f"savings_by_source_usd.{src}", 0.0
                            )
                            or 0.0
                        ),
                        6,
                    )
                    for src in savings_sources
                },
            },
            "tokens": summary,
            "requests": {
                "total": requests_total,
                "by_provider": dict(getattr(m, "requests_by_provider", {})),
                "by_model": dict(getattr(m, "requests_by_model", {})),
            },
            "savings": {
                "per_project": persistent_savings.get("projects", {}),
                "by_layer": {
                    "cli_filtering": {
                        "tool": cli_filtering_tool,
                        "label": cli_filtering_tool,
                        "tokens": cli_tokens_avoided,
                        "tokens_saved": cli_tokens_avoided,
                        "session": cli_filtering_session,
                        "lifetime": cli_filtering_lifetime,
                        "session_savings_pct": cli_filtering_stats.get("session_savings_pct") if cli_filtering_stats else None,
                        "lifetime_savings_pct": cli_filtering_stats.get("lifetime_avg_savings_pct") if cli_filtering_stats else None,
                    },
                    "compression": {
                        "tokens": proxy_compression_tokens,
                        "proxy_tokens": proxy_compression_tokens,
                        "cli_filtering_tokens": cli_tokens_avoided,
                        "rtk_tokens": rtk_tokens_avoided,
                        "lean_ctx_tokens": lean_ctx_tokens_avoided,
                        "all_layers_tokens": all_layers_tokens_saved,
                    },
                }
            },
            "context_tool": {
                "configured": cli_filtering_tool,
                "label": cli_filtering_label,
                "available": bool(cli_filtering_stats and cli_filtering_stats.get("installed", False)),
                "stats": cli_filtering_stats,
            },
            "compression_cache": compression_cache_stats,
            "cli_filtering": cli_filtering_stats,
            "savings_history": getattr(m, "savings_history", [])[-100:],
            "display_session": display_session,
            "persistent_savings": persistent_savings,
            "compressions_by_strategy": dict(getattr(m, "compressions_by_strategy", {})),
            "tokens_saved_by_strategy": dict(getattr(m, "tokens_saved_by_strategy", {})),
            "anon_telemetry_shipping": is_telemetry_enabled(),
            "otel": get_otel_metrics_status(),
            "langfuse": get_langfuse_tracing_status(),
            "prefix_cache": prefix_cache_stats,
            "cost": _merge_cost_stats(proxy.cost_tracker.stats() if proxy.cost_tracker else None, prefix_cache_stats, cli_tokens_avoided=cli_tokens_avoided),
            "compression": {
                "ccr_entries": compression_stats.get("entry_count", 0),
                "ccr_max_entries": compression_stats.get("max_entries", 0),
                "original_tokens_cached": compression_stats.get("total_original_tokens", 0),
                "compressed_tokens_cached": compression_stats.get("total_compressed_tokens", 0),
                "ccr_retrievals": compression_stats.get("total_retrievals", 0),
            },
            "knowledge_graph": {
                **getattr(proxy, "knowledge_graph_status", {}),
                "active": kg_idx is not None,
                "status": "ready" if kg_idx is not None else getattr(proxy, "knowledge_graph_status", {}).get("status", "disabled"),
                **(getattr(kg_indexer, "stats", {}) if kg_indexer else {}),
            },
            "stack_graph": {
                "enabled": bool(getattr(proxy, "stack_graph_resolver", None)),
                "files_indexed": getattr(proxy.stack_graph_resolver, "file_count", lambda: 0)()
                if hasattr(proxy, "stack_graph_resolver") and proxy.stack_graph_resolver else 0,
                "nodes": getattr(proxy.stack_graph_resolver, "node_count", lambda: 0)()
                if hasattr(proxy, "stack_graph_resolver") and proxy.stack_graph_resolver else 0,
            },
            "model_routing": model_routing_status,
            "feature_availability": {
                "knowledge_graph": {
                    "requested": bool(getattr(proxy.config, "knowledge_graph_enabled", False)),
                    "available": graphify_py and networkx_py,
                    "knowledge_graph_engine_installed": graphify_py,
                    "graph_utilities_installed": networkx_py,
                    "reason": None if graphify_py and networkx_py else "knowledge_graph_engine_missing" if not graphify_py else "graph_utilities_missing",
                    "install_hint": "pip install cutctx-ai[knowledge-graph]",
                },
                "log_template_mining": {
                    "requested": bool(getattr(proxy.config, "use_drain3", False)),
                    "available": drain3_ready,
                    "reason": None if drain3_ready else "log_template_mining_missing",
                    "install_hint": "pip install cutctx-ai[log-ml]",
                },
                "structural_diff_engine": {
                    "requested": bool(getattr(proxy.config, "difftastic_enabled", False)),
                    "available": difft_path is not None,
                    "binary": str(difft_path) if difft_path else None,
                    "reason": None if difft_path is not None else "difft_binary_missing",
                    "install_hint": "brew install structural-diff-engine or cargo install structural-diff-engine",
                },
                "text_compression_engine": {
                    "requested": bool(getattr(proxy.config, "use_llmlingua", False)),
                    "available": llmlingua_py and llmlingua_runtime_py,
                    "reason": None if llmlingua_py and llmlingua_runtime_py else "text_compression_runtime_missing" if llmlingua_py else "text_compression_engine_missing",
                    "install_hint": "pip install cutctx-ai[llmlingua]",
                },
                "multimodal_image": {
                    "requested": False,
                    "available": pillow_py,
                    "reason": None if pillow_py else "pillow_missing",
                    "install_hint": "pip install cutctx-ai[image]",
                },
                "smart_crusher": {
                    "requested": True,
                    "available": rust_core_py,
                    "reason": None if rust_core_py else "rust_extension_not_built",
                    "install_hint": "pip install cutctx-ai",
                },
                "kompress": {
                    "requested": False,
                    "available": onnxruntime_py,
                    "reason": None if onnxruntime_py else "ml_inference_runtime_missing",
                    "install_hint": "pip install cutctx-ai[proxy]",
                },
                "html_extractor": {
                    "requested": False,
                    "available": trafilatura_py,
                    "reason": None if trafilatura_py else "html_extraction_engine_missing",
                    "install_hint": "pip install cutctx-ai[html]",
                },
                "voice_filler": {
                    "requested": False,
                    "available": torch_py,
                    "reason": None if torch_py else "ml_framework_missing",
                    "install_hint": "pip install cutctx-ai[voice]",
                },
                "code_ast": {
                    "requested": False,
                    "available": tree_sitter_py,
                    "reason": None if tree_sitter_py else "code_parsing_engine_missing",
                    "install_hint": "pip install cutctx-ai[code]",
                },
                "stack_graph": {
                    "requested": bool(getattr(proxy.config, "stack_graph_enabled", False)),
                    "available": stack_graph_available(),
                    "active": bool(getattr(proxy, "stack_graph_resolver", None)),
                    "reason": None if stack_graph_available() else "stack_graph_extension_not_built",
                    "install_hint": "pip install cutctx-ai[dev] or build the Rust extension for stack-graph support",
                },
                "usearch": {
                    "requested": False,
                    "available": usearch_ready,
                    "reason": None if usearch_ready else "usearch_package_missing",
                    "install_hint": "pip install cutctx-ai[memory] or pip install usearch",
                },
                "model_routing": model_routing_status,
            "audio": {
                "requested": True,
                "available": True,
                "compression": "pass-through",
                "reason": "audio_proxy_only_no_token_compression",
                "install_hint": None,
            },
        },
        "config": {
            "cache": bool(getattr(config, "cache_enabled", False)),
            "ccr": bool(getattr(config, "ccr_context_tracking", False)),
            "memory": bool(getattr(config, "episodic_memory_enabled", False)),
            "firewall": bool(getattr(config, "firewall_enabled", False)),
            "rate_limiter": bool(getattr(config, "rate_limit_enabled", False)),
            "orchestrator": bool(getattr(config, "orchestrator_enabled", False)),
        },
        "telemetry": telemetry_stats,
        "feedback": feedback_stats,
        "recent_requests": proxy.logger.get_recent(10) if proxy.logger else [],
    }

    def _uptime_seconds() -> float:
        return max(0.0, time.time() - float(app.state.started_at))

    def _iso_utc_now() -> str:
        return datetime.now(timezone.utc).isoformat()

    @app.middleware("http")
    async def _bind_project_context(request: Request, call_next):
        prefix_project = strip_project_path_prefix(request.scope)
        headers = dict(request.headers.items())
        set_current_project(classify_project(headers) or prefix_project)
        return await call_next(request)

    def _component_health(
        *,
        enabled: bool,
        ready: bool,
        **details: Any,
    ) -> dict[str, Any]:
        status = "disabled" if not enabled else ("healthy" if ready else "unhealthy")
        return {
            "enabled": enabled,
            "ready": (ready if enabled else True),
            "status": status,
            **details,
        }

    def _health_checks() -> dict[str, dict[str, Any]]:
        memory_status = (
            proxy.memory_handler.health_status()
            if proxy.memory_handler
            else {
                "enabled": False,
                "backend": None,
                "initialized": False,
                "native_tool": False,
                "bridge_enabled": False,
            }
        )
        memory_enabled = bool(memory_status.get("enabled", False))
        memory_initialized = bool(memory_status.get("initialized", False))
        return {
            "startup": _component_health(
                enabled=True,
                ready=bool(getattr(app.state, "ready", False)),
                error=getattr(app.state, "startup_error", None),
            ),
            "http_client": _component_health(
                enabled=True,
                ready=proxy.http_client is not None,
            ),
            "cache": _component_health(
                enabled=config.cache_enabled,
                ready=(proxy.cache is not None),
            ),
            "rate_limiter": _component_health(
                enabled=config.rate_limit_enabled,
                ready=(proxy.rate_limiter is not None),
            ),
            "memory": _component_health(
                enabled=memory_enabled,
                ready=memory_initialized,
                backend=memory_status["backend"],
                initialized=memory_initialized,
                native_tool=bool(memory_status.get("native_tool", False)),
                bridge_enabled=bool(memory_status.get("bridge_enabled", False)),
            ),
            "upstream": _component_health(
                enabled=os.environ.get("CUTCTX_SKIP_UPSTREAM_CHECK", "").strip() != "1",
                ready=bool(_upstream_check_cache["ok"]),
                url=_upstream_check_cache["url"],
                error=_upstream_check_cache["error"],
            ),
        }

    def _runtime_payload() -> dict[str, Any]:
        ws_registry = getattr(proxy, "ws_sessions", None)
        ws_active_sessions = ws_registry.active_count() if ws_registry is not None else 0
        ws_active_relay_tasks = (
            ws_registry.active_relay_task_count() if ws_registry is not None else 0
        )
        with proxy._compression_metrics_lock:
            queued = proxy._compression_queued
            queued_max = proxy._compression_queued_max
            queue_timeouts_total = proxy._compression_queue_timeouts
            queue_wait_seconds_total = proxy._compression_queue_wait_seconds_total
            queue_wait_seconds_max = proxy._compression_queue_wait_seconds_max
            in_flight = proxy._compression_in_flight
            in_flight_max = proxy._compression_in_flight_max
            run_seconds_total = proxy._compression_run_seconds_total
            run_seconds_max = proxy._compression_run_seconds_max
            leaked_threads_total = proxy._compression_leaked_threads
        return {
            "anthropic_pre_upstream": {
                "enabled": proxy.anthropic_pre_upstream_sem is not None,
                "resolved_concurrency": proxy.anthropic_pre_upstream_concurrency,
                "source": (
                    "auto"
                    if config.anthropic_pre_upstream_concurrency is None
                    else "explicit"
                ),
                "acquire_timeout_seconds": proxy.anthropic_pre_upstream_acquire_timeout_seconds,
                "compression_timeout_seconds": float(COMPRESSION_TIMEOUT_SECONDS),
                "memory_context_timeout_seconds": (
                    proxy.anthropic_pre_upstream_memory_context_timeout_seconds
                ),
                "codex_ws_gated": False,
            },
            "compression_executor": {
                "max_workers": proxy.compression_max_workers,
                "queued": queued,
                "queued_max": queued_max,
                "queue_timeouts_total": queue_timeouts_total,
                "queue_wait_seconds_total": queue_wait_seconds_total,
                "queue_wait_seconds_max": queue_wait_seconds_max,
                "running": in_flight,
                "in_flight": in_flight,
                "in_flight_max": in_flight_max,
                "run_seconds_total": run_seconds_total,
                "run_seconds_max": run_seconds_max,
                "leaked_threads_total": leaked_threads_total,
                "source": (
                    "auto" if config.compression_max_workers is None else "explicit"
                ),
            },
            "websocket_sessions": {
                "active_sessions": ws_active_sessions,
                "active_relay_tasks": ws_active_relay_tasks,
            },
        }

    def _health_payload(include_config: bool = False) -> dict[str, Any]:
        checks = _health_checks()
        ready = all(check["ready"] for check in checks.values())
        payload = {
            "service": "cutctx-proxy",
            "status": "healthy" if ready else "unhealthy",
            "ready": ready,
            "alive": True,
            "version": __version__,
            "timestamp": _iso_utc_now(),
            "uptime_seconds": _uptime_seconds(),
            "checks": checks,
            "runtime": _runtime_payload(),
            "rust_core": getattr(app.state, "rust_core_status", "missing"),
        }
        rust_core_error = getattr(app.state, "rust_core_error", None)
        if rust_core_error:
            payload["rust_core_error"] = rust_core_error
        deployment_profile = os.environ.get("CUTCTX_DEPLOYMENT_PROFILE")
        if deployment_profile:
            payload["deployment"] = {
                "profile": deployment_profile,
                "preset": os.environ.get("CUTCTX_DEPLOYMENT_PRESET"),
                "runtime": os.environ.get("CUTCTX_DEPLOYMENT_RUNTIME"),
                "supervisor": os.environ.get("CUTCTX_DEPLOYMENT_SUPERVISOR"),
                "scope": os.environ.get("CUTCTX_DEPLOYMENT_SCOPE"),
            }
        if include_config:
            profile_kwargs = proxy_pipeline_kwargs(config)
            effective_target_ratio = cast(
                float | None,
                profile_kwargs.get("target_ratio", config.target_ratio),
            )
            payload["mode"] = getattr(proxy.config, "mode", None)
            payload["backend"] = getattr(proxy.config, "backend", None)
            payload["config"] = {
                "backend": config.backend,
                "optimize": config.optimize,
                "cache": config.cache_enabled,
                "rate_limit": config.rate_limit_enabled,
                "disable_kompress": config.disable_kompress,
                "memory": config.memory_enabled,
                "learn": config.traffic_learning_enabled,
                "code_graph": config.code_graph_watcher,
                "savings_profile": config.savings_profile,
                "target_ratio": effective_target_ratio,
                "target_savings_percent": (
                    round(max(0.0, min(1.0, 1.0 - float(effective_target_ratio))) * 100, 1)
                    if effective_target_ratio is not None
                    else None
                ),
                "compress_user_messages": bool(
                    profile_kwargs.get(
                        "compress_user_messages",
                        config.compress_user_messages,
                    )
                ),
                "compress_system_messages": bool(
                    profile_kwargs.get(
                        "compress_system_messages",
                        config.compress_system_messages,
                    )
                ),
                "protect_recent": profile_kwargs.get(
                    "read_protection_window",
                    config.protect_recent,
                ),
                "protect_analysis_context": profile_kwargs.get(
                    "protect_analysis_context",
                    config.protect_analysis_context,
                ),
                "min_tokens_to_crush": profile_kwargs.get(
                    "min_tokens_to_compress",
                    config.min_tokens_to_crush,
                ),
                "max_items_after_crush": profile_kwargs.get(
                    "max_items_after_crush",
                    config.max_items_after_crush,
                ),
                "smart_crusher_with_compaction": profile_kwargs.get(
                    "smart_crusher_with_compaction",
                    config.smart_crusher_with_compaction,
                ),
                "force_kompress": bool(profile_kwargs.get("force_kompress", False)),
                "accuracy_guard": config.accuracy_guard,
                "pid": os.getpid(),
                "task_aware_enabled": config.task_aware_enabled,
                "dedup_enabled": config.dedup_enabled,
                "context_budget_enabled": config.context_budget_enabled,
                "profiles_enabled": config.profiles_enabled,
                "firewall_enabled": getattr(config, "firewall_enabled", False),
            }
        return payload

    async def _get_cached_payload() -> dict[str, Any]:
        async with stats_snapshot_lock:
            now = time.monotonic()
            cached_payload = cast(dict[str, Any] | None, stats_snapshot.get("value"))
            if cached_payload is not None and now < float(stats_snapshot["expires_at"]):
                return cached_payload
            payload = await _build_stats_payload()
            stats_snapshot["value"] = payload
            stats_snapshot["expires_at"] = time.monotonic() + stats_cache_ttl_seconds
            return payload

    async def _require_local_admin_auth(request: Request) -> None:
        expected_admin_key = config.admin_api_key or os.environ.get("CUTCTX_ADMIN_API_KEY")
        auth_header = request.headers.get("authorization", "")
        bearer_token = auth_header[7:].strip() if auth_header.startswith("Bearer ") else ""
        admin_header = request.headers.get("x-cutctx-admin-key", "") or request.query_params.get("key", "")
        legacy_header = request.headers.get("x-headroom-admin-key", "")
        import hmac as _hmac

        if expected_admin_key and (
            _hmac.compare_digest(bearer_token, expected_admin_key)
            or _hmac.compare_digest(admin_header, expected_admin_key)
            or _hmac.compare_digest(legacy_header, expected_admin_key)
        ):
            return

        sso_configured = bool(
            getattr(config, "sso_provider_type", None)
            and getattr(config, "sso_jwks_uri", None)
            and getattr(config, "sso_issuer", None)
            and getattr(config, "sso_audience", None)
        )
        if sso_configured:
            if not bearer_token:
                raise HTTPException(status_code=401, detail="Unauthorized")
            try:
                from cutctx.sso import SsoConfig, SsoValidator

                sso_config = SsoConfig.from_proxy_config(config)
                validator = SsoValidator(sso_config)
                claims = await validator.validate_token(bearer_token)
                if getattr(claims, "role", None):
                    request.state.cutctx_role = claims.role
                if getattr(claims, "subject", None):
                    request.state.cutctx_user_id = claims.subject
                request.state.cutctx_sso_claims = claims
                return
            except Exception as exc:
                logger.debug("SSO validation failed in runtime app", exc_info=True)
                raise HTTPException(status_code=401, detail="Unauthorized") from exc

        if not expected_admin_key:
            return
        raise HTTPException(status_code=401, detail="Unauthorized")

    def _runtime_require_rbac_permission(permission: str):
        async def _check(request: Request) -> None:
            await _require_local_admin_auth(request)
            try:
                from cutctx.rbac import get_rbac_checker
            except ImportError:
                return
            try:
                checker = get_rbac_checker()
            except Exception:
                logger.debug("RBAC checker unavailable in runtime app", exc_info=True)
                return
            if checker is None:
                return
            role = checker.resolve_role(request)
            checker.check_permission(role, permission)

        return _check

    def _runtime_require_entitlement(feature: str):
        min_tier_by_feature = {
            "usage_reports": "team",
            "workspace_model": "business",
            "project_model": "business",
            "audit_logs": "enterprise",
            "retention_controls": "enterprise",
            "rbac": "enterprise",
            "fleet_management": "enterprise",
            "scim": "enterprise",
        }
        tier_rank = {"builder": 0, "team": 1, "business": 2, "enterprise": 3}

        async def _check(_request: Request) -> None:
            required_tier = min_tier_by_feature.get(feature)
            if required_tier is None:
                return
            current_tier = str(getattr(config, "entitlement_tier", "enterprise") or "enterprise").lower()
            if tier_rank.get(current_tier, 99) < tier_rank[required_tier]:
                raise HTTPException(
                    status_code=403,
                    detail={
                        "error": "feature_not_available",
                        "feature": feature,
                        "required_tier": required_tier,
                        "current_tier": current_tier,
                    },
                )

        return _check


    @app.get("/stats")
    @app.get("/v1/stats")
    async def stats(request: Request, cached: bool = False):
        await _require_local_admin_auth(request)
        if cached:
            return await _get_cached_payload()
        return await _build_stats_payload()

    @app.get("/v1/sessions/{session_id}/replay")
    async def session_replay(session_id: str, request: Request):
        await _require_local_admin_auth(request)
        from cutctx.proxy.session_replay import get_replay_store

        replay_store = get_replay_store()
        if replay_store is None:
            return JSONResponse(
                status_code=404,
                content={
                    "error": {
                        "type": "replay_disabled",
                        "message": "Session replay is disabled. Set CUTCTX_REPLAY=1.",
                    }
                },
            )
        payload = replay_store.get(session_id)
        if payload["event_count"] == 0:
            return JSONResponse(
                status_code=404,
                content={
                    "error": {
                        "type": "replay_not_found",
                        "message": f"No replay events for session {session_id!r}.",
                    }
                },
            )
        return payload

    @app.post("/stats/reset")
    async def stats_reset(request: Request):
        await _require_local_admin_auth(request)
        await proxy.metrics.reset_runtime()
        if proxy.cost_tracker:
            proxy.cost_tracker.reset_runtime()
        await initialize_context_tool_session_baseline()
        async with stats_snapshot_lock:
            stats_snapshot["value"] = None
            stats_snapshot["expires_at"] = 0.0
        if proxy.audit_logger:
            try:
                from cutctx.audit import AuditEvent
                from cutctx.proxy.routes.admin import _resolve_audit_actor

                await proxy.audit_logger.async_log(
                    AuditEvent(
                        action="stats.reset",
                        actor=_resolve_audit_actor(request),
                        detail={},
                        ip_address=getattr(request.client, "host", None),
                    )
                )
            except Exception as exc:
                logger.warning("Failed to audit stats reset: %s", exc)
        return {"ok": True, "status": "reset"}

    @app.get("/livez")
    async def livez():
        return JSONResponse(status_code=200, content=_health_payload(include_config=False))

    @app.get("/readyz")
    async def readyz():
        await _check_upstream()
        payload = _health_payload(include_config=False)
        return JSONResponse(status_code=200 if payload["ready"] else 503, content=payload)

    @app.get("/health")
    async def health():
        await _check_upstream()
        return JSONResponse(status_code=200, content=_health_payload(include_config=True))



    @app.get("/v1/version")
    async def get_v1_version():
        return JSONResponse(status_code=200, content={"version": __version__})

    @app.get("/stats-history")
    async def stats_history(
        request: Request,
        format: str = "json",
        series: str = "daily",
        history_mode: str = "compact",
    ):
        await _require_local_admin_auth(request)
        if format == "csv":
            filename = f"cutctx-stats-history-{series}.csv"
            return Response(
                content=proxy.metrics.savings_tracker.export_csv(series=series),
                media_type="text/csv; charset=utf-8",
                headers={"Content-Disposition": f'attachment; filename="{filename}"'},
            )
        return proxy.metrics.savings_tracker.history_response(history_mode=history_mode)

    @app.get("/transformations/feed")
    async def transformations_feed(limit: int = 50):
        transformations = []
        log_full_messages = proxy.config.log_full_messages if proxy else False

        if proxy and proxy.logger:
            logs = proxy.logger.get_recent_with_messages(limit)
            for log in logs:
                transformations.append(
                    {
                        "request_id": log.get("request_id"),
                        "timestamp": log.get("timestamp"),
                        "provider": log.get("provider"),
                        "model": log.get("model"),
                        "input_tokens_original": log.get("input_tokens_original"),
                        "input_tokens_optimized": log.get("input_tokens_optimized"),
                        "tokens_saved": log.get("tokens_saved"),
                        "savings_percent": log.get("savings_percent"),
                        "transforms_applied": log.get("transforms_applied", []),
                        "request_messages": log.get("request_messages"),
                        "compressed_messages": log.get("compressed_messages"),
                        "response_content": log.get("response_content"),
                        "turn_id": log.get("turn_id"),
                    }
                )

        return {"transformations": transformations, "log_full_messages": log_full_messages}

    @app.post("/v1/compress")
    async def compress_endpoint(request: Request):
        return await proxy.handle_compress(request)

    @app.get("/v1/retrieve/stats")
    async def retrieve_stats_endpoint():
        store = get_compression_store()
        stats = store.get_stats()
        return JSONResponse(
            status_code=200,
            content={
                "store": stats,
                "recent_retrievals": _json_ready(store.get_retrieval_events()),
            },
        )

    def _retrieve_entry(hash_key: str, query: str | None = None):
        from cutctx.cache.compression_store import format_retrieval_miss_detail

        store = get_compression_store()
        status = store.get_entry_status(hash_key, clean_expired=False)
        if status.get("status") == "expired":
            raise HTTPException(status_code=404, detail=format_retrieval_miss_detail(status))

        entry = store.retrieve(hash_key, query=query)
        if entry is not None:
            return entry

        backend = getattr(store, "_backend", None)
        items = getattr(backend, "items", None)
        if callable(items):
            for stored_hash, _candidate in items():
                if (
                    stored_hash == hash_key
                    or stored_hash.startswith(hash_key)
                    or hash_key.startswith(stored_hash)
                ):
                    status = store.get_entry_status(stored_hash, clean_expired=False)
                    if status.get("status") == "expired":
                        raise HTTPException(status_code=404, detail=format_retrieval_miss_detail(status))
                    entry = store.retrieve(stored_hash, query=query)
                    if entry is not None:
                        return entry
                    hash_key = stored_hash
                    break

        status = store.get_entry_status(hash_key, clean_expired=False)
        raise HTTPException(status_code=404, detail=format_retrieval_miss_detail(status))

    @app.post("/v1/retrieve")
    async def retrieve_endpoint(request: Request):
        payload = await request.json()
        hash_key = str(payload.get("hash", "") or "").strip()
        query = payload.get("query")
        if not hash_key:
            raise HTTPException(status_code=400, detail="hash required")

        store = get_compression_store()
        entry = _retrieve_entry(hash_key, query=query)
        resolved_hash = entry.hash

        if query:
            results = store.search(resolved_hash, str(query))
            return JSONResponse(
                status_code=200,
                content={
                    "hash": resolved_hash,
                    "query": query,
                    "results": results,
                    "count": len(results),
                },
            )

        return JSONResponse(
            status_code=200,
            content={
                "hash": resolved_hash,
                "original_content": entry.original_content,
                "compressed_content": entry.compressed_content,
                "original_tokens": entry.original_tokens,
                "compressed_tokens": entry.compressed_tokens,
                "original_item_count": entry.original_item_count,
                "compressed_item_count": entry.compressed_item_count,
                "tool_name": entry.tool_name,
                "query_context": entry.query_context,
                "retrieval_count": entry.retrieval_count,
            },
        )

    @app.get("/v1/retrieve/{hash_key}")
    async def retrieve_by_hash_endpoint(hash_key: str, query: str | None = None):
        store = get_compression_store()
        entry = _retrieve_entry(hash_key, query=query)
        if query:
            results = store.search(entry.hash, str(query))
            return JSONResponse(
                status_code=200,
                content={
                    "hash": entry.hash,
                    "query": query,
                    "results": results,
                    "count": len(results),
                },
            )
        return JSONResponse(
            status_code=200,
            content={
                "hash": entry.hash,
                "original_content": entry.original_content,
                "compressed_content": entry.compressed_content,
                "original_tokens": entry.original_tokens,
                "compressed_tokens": entry.compressed_tokens,
                "original_item_count": entry.original_item_count,
                "compressed_item_count": entry.compressed_item_count,
                "tool_name": entry.tool_name,
                "query_context": entry.query_context,
                "retrieval_count": entry.retrieval_count,
            },
        )

    from pathlib import Path as _Path
    # See the matching comment on the other `/assets` mount above — this
    # must stay inside cutctx/dashboard/ to survive a real package install.
    _react_assets = _Path(__file__).resolve().parent.parent / "dashboard" / "assets"
    if _react_assets.is_dir():
        @app.get("/assets/{filename}", include_in_schema=False)
        async def serve_asset_legacy(filename: str):
            asset_path = _react_assets / filename
            if asset_path.is_file():
                return FileResponse(str(asset_path))
            return Response(status_code=404)
    @app.get("/favicon.svg", include_in_schema=False)
    async def _favicon():
        fav = _react_assets.parent / "favicon.svg"
        if fav.is_file():
            return FileResponse(str(fav), media_type="image/svg+xml")
        return Response(status_code=404)

    @app.get("/dashboard", response_class=HTMLResponse)
    @app.get("/dashboard/{path:path}", response_class=HTMLResponse)
    async def dashboard(request: Request, path: str = ""):
        await _require_local_admin_auth(request)
        return HTMLResponse(get_dashboard_html(prefer_react=True))
    @app.post("/admin/config/flags")
    async def update_config_flags(request: Request):
        """Update live intelligence layer feature flags at runtime."""
        await _require_local_admin_auth(request)
        payload = await request.json()

        if "cache" in payload:
            config.cache_enabled = bool(payload["cache"])
        if "ccr" in payload:
            ccr_enabled = bool(payload["ccr"])
            config.ccr_context_tracking = ccr_enabled
            config.ccr_handle_responses = ccr_enabled
        if "memory" in payload:
            config.episodic_memory_enabled = bool(payload["memory"])
            if config.episodic_memory_enabled and getattr(proxy, "episodic_tracker", None) is None:
                try:
                    from cutctx.intelligence_pipeline import IntelligencePipeline
                    from cutctx.memory.session_tracker import EpisodicSessionTracker
                    from cutctx.memory.store import EpisodicMemoryStore

                    store = EpisodicMemoryStore()
                    intel = IntelligencePipeline(config)
                    proxy.episodic_tracker = EpisodicSessionTracker(store, intel, proxy.logger)
                except ImportError as exc:
                    logger.warning("Could not load memory dependencies: %s", exc)
        if "firewall" in payload:
            config.firewall_enabled = bool(payload["firewall"])
        if "rate_limiter" in payload:
            config.rate_limit_enabled = bool(payload["rate_limiter"])
        if "orchestrator" in payload:
            config.orchestrator_enabled = bool(payload["orchestrator"])
            if hasattr(proxy, "_model_router") and proxy._model_router is not None:
                proxy._model_router.config.enabled = bool(payload["orchestrator"])

        logger.info("Runtime configuration updated: %s", payload)
        return {
            "status": "success",
            "config": {
                "cache": bool(getattr(config, "cache_enabled", False)),
                "ccr": bool(getattr(config, "ccr_context_tracking", False)),
                "memory": bool(getattr(config, "episodic_memory_enabled", False)),
                "firewall": bool(getattr(config, "firewall_enabled", False)),
                "rate_limiter": bool(getattr(config, "rate_limit_enabled", False)),
                "orchestrator": bool(getattr(config, "orchestrator_enabled", False)),
            },
            "payload": payload,
        }

    try:
        from cutctx.proxy.routes import create_admin_router
        from cutctx.proxy.routes.airgap import create_airgap_router
        from cutctx.proxy.routes.audit import create_audit_router
        from cutctx.proxy.routes.dsr import create_dsr_router
        from cutctx.proxy.routes.memory import create_memory_router
        from cutctx.proxy.routes.policy import create_policy_router
        from cutctx.proxy.routes.rate_limit import create_rate_limit_router
        from cutctx.proxy.routes.rbac import create_rbac_router
        from cutctx.proxy.routes.residency import create_residency_router
        from cutctx.proxy.routes.secrets import create_secrets_router
        from cutctx.proxy.routes.spend import create_spend_router
        from cutctx.proxy.routes.sso import create_sso_router
        from cutctx.proxy.routes.license_validation import create_license_validation_router

        admin_dep = _require_local_admin_auth
        rbac_dep = _runtime_require_rbac_permission
        entitlement_dep = _runtime_require_entitlement

        app.include_router(
            create_admin_router(
                proxy,
                config,
                require_admin_auth=admin_dep,
                require_rbac_permission=rbac_dep,
                require_entitlement=entitlement_dep,
                firewall_scanner=_firewall_scanner,
            )
        )
        app.include_router(create_airgap_router(require_admin_auth=admin_dep, require_rbac_permission=rbac_dep))
        app.include_router(create_rate_limit_router(require_admin_auth=admin_dep, require_rbac_permission=rbac_dep))
        app.include_router(create_rbac_router(require_admin_auth=admin_dep, require_rbac_permission=rbac_dep))
        app.include_router(create_secrets_router(require_admin_auth=admin_dep, require_rbac_permission=rbac_dep))
        app.include_router(create_sso_router(require_admin_auth=admin_dep, require_rbac_permission=rbac_dep))
        app.include_router(create_audit_router(require_admin_auth=admin_dep, require_rbac_permission=rbac_dep))
        app.include_router(create_spend_router(require_admin_auth=admin_dep, require_rbac_permission=rbac_dep))
        app.include_router(create_policy_router(require_admin_auth=admin_dep, require_rbac_permission=rbac_dep))
        app.include_router(create_memory_router(require_admin_auth=admin_dep, require_rbac_permission=rbac_dep))
        app.include_router(
            create_dsr_router(
                proxy=proxy,
                require_admin_auth=admin_dep,
                require_rbac_permission=rbac_dep,
            )
        )
        app.include_router(create_residency_router(require_admin_auth=admin_dep, require_rbac_permission=rbac_dep))
        app.include_router(create_license_validation_router(require_admin_auth=admin_dep, require_rbac_permission=rbac_dep))
    except ImportError:
        pass

    try:
        from cutctx.proxy.routes.mfa import create_mfa_router

        app.include_router(
            create_mfa_router(
                require_admin_auth=_require_local_admin_auth,
                require_rbac_permission=_runtime_require_rbac_permission,
            )
        )
    except ImportError:
        pass

    register_provider_routes(app, proxy)
    return app

def create_app_from_env() -> FastAPI:
    return create_app(_proxy_config_from_env())


def _get_code_aware_banner_status(config: ProxyConfig) -> str:
    """Get code-aware compression status line for banner."""
    if config.code_aware_enabled:
        if is_tree_sitter_available():
            return "ENABLED  (AST-based)"
        else:
            return "NOT INSTALLED (pip install cutctx-ai[code])"
    else:
        if is_tree_sitter_available():
            return "DISABLED (--code-aware or CUTCTX_CODE_AWARE_ENABLED=1 to enable)"
        return "DISABLED  (install cutctx-ai[code] to enable)"


def run_server(
    config: ProxyConfig | None = None,
    workers: int = 1,
    limit_concurrency: int = 1000,
    print_banner: bool = True,
):
    """Run the proxy server.

    Args:
        config: Proxy configuration
        workers: Number of worker processes (use N for multi-core scaling)
        limit_concurrency: Max concurrent connections before 503 response
        print_banner: When False, skip the legacy ASCII banner. The
            Click CLI (`cutctx proxy`) prints its own startup banner
            before calling this — printing a second banner here is the
            "dual banner" UX issue. Direct `python -m cutctx.proxy.server`
            still gets the banner since it has no other startup output.
    """
    if not FASTAPI_AVAILABLE:
        print("ERROR: FastAPI required. Install: pip install fastapi uvicorn httpx")
        sys.exit(1)

    config = config or ProxyConfig()
    code_aware_status = _get_code_aware_banner_status(config)

    # Format connection pool info
    pool_info = f"max={config.max_connections}, keepalive={config.max_keepalive_connections}"
    http2_status = "ENABLED" if config.http2 else "DISABLED"

    backend_status = format_backend_status(
        backend=config.backend,
        anyllm_provider=config.anyllm_provider,
        bedrock_region=config.bedrock_region,
    )

    # Resolve upstream API targets for display in the banner (#583).
    api_targets = resolve_api_targets(config.provider_api_overrides)

    if print_banner:
        print(f"""
╔══════════════════════════════════════════════════════════════════════╗
║                      CUTCTX PROXY SERVER                           ║
╠══════════════════════════════════════════════════════════════════════╣
║  Version: 1.0.0                                                      ║
║  Listening: http://{config.host}:{config.port:<5}                                      ║
║  Workers: {workers:<3}  Concurrency Limit: {limit_concurrency:<5}                          ║
║  Backend: {backend_status:<59}║
╠══════════════════════════════════════════════════════════════════════╣
║  UPSTREAM TARGETS:                                                   ║
║    Anthropic:  {api_targets.anthropic:<57}║
║    OpenAI:     {api_targets.openai:<57}║
║    Gemini:     {api_targets.gemini:<57}║
║    Cloud Code: {api_targets.cloudcode:<57}║
║    Vertex AI:  {api_targets.vertex:<57}║
╠══════════════════════════════════════════════════════════════════════╣
║  FEATURES:                                                           ║
║    Optimization:    {"ENABLED " if config.optimize else "DISABLED"}                                       ║
║    Caching:         {"ENABLED " if config.cache_enabled else "DISABLED"}   (TTL: {config.cache_ttl_seconds}s)                          ║
║    Rate Limiting:   {"ENABLED " if config.rate_limit_enabled else "DISABLED"}   ({config.rate_limit_requests_per_minute} req/min, {config.rate_limit_tokens_per_minute:,} tok/min)       ║
║    Retry:           {"ENABLED " if config.retry_enabled else "DISABLED"}   (max {config.retry_max_attempts} attempts)                       ║
║    Cost Tracking:   {"ENABLED " if config.cost_tracking_enabled else "DISABLED"}   (budget: {"$" + str(config.budget_limit_usd) + "/" + config.budget_period if config.budget_limit_usd else "unlimited"})          ║
║    Code-Aware:      {code_aware_status:<52}║
║    HTTP/2:          {http2_status:<52}║
║    Conn Pool:       {pool_info:<52}║
╠══════════════════════════════════════════════════════════════════════╣
║  USAGE:                                                              ║
║    Claude Code:   ANTHROPIC_BASE_URL=http://{config.host}:{config.port} claude     ║
║    Cursor:        Set base URL in settings                           ║
╠══════════════════════════════════════════════════════════════════════╣
║  ENDPOINTS:                                                          ║
║    /livez                   Process liveness                         ║
║    /readyz                  Traffic readiness                        ║
║    /health                  Aggregate health                         ║
║    /stats                   Detailed statistics                      ║
║    /metrics                 Prometheus metrics                       ║
║    /cache/clear             Clear response cache                     ║
║    /v1/retrieve             CCR: Retrieve compressed content         ║
║    /v1/retrieve/stats       CCR: Compression store stats             ║
║    /v1/retrieve/tool_call   CCR: Handle LLM tool calls               ║
║    /v1/feedback             CCR: Feedback loop stats & patterns      ║
║    /v1/feedback/{{tool}}    CCR: Compression hints for a tool        ║
║    /v1/telemetry            Data flywheel: Telemetry stats           ║
║    /v1/telemetry/export     Data flywheel: Export for aggregation    ║
║    /v1/telemetry/tools      Data flywheel: Per-tool stats            ║
║    /v1/toin/stats           TOIN: Overall intelligence stats         ║
║    /v1/toin/patterns        TOIN: List learned patterns              ║
║    /v1/toin/pattern/{{hash}} TOIN: Pattern details by hash            ║
╚══════════════════════════════════════════════════════════════════════╝
""")

    app_target: Any
    uvicorn_kwargs: dict[str, Any] = {}
    if workers > 1:
        # CompressionCache and PrefixTracker are always per-worker instance vars.
        # Python CompressionStore defaults to InMemoryBackend (per-process), so
        # CCR markers written on worker A are invisible to worker B unless a
        # cross-worker backend is configured via CUTCTX_CCR_BACKEND.
        # See RUST_DEV.md -> "Multi-worker deployment -- CCR fragmentation".
        if os.environ.get("CUTCTX_CCR_BACKEND", "").strip():
            logger.warning(
                "Cutctx is running with workers=%d. Compression cache, "
                "prefix tracker, TOIN state, and CostTracker are all per-process; "
                "multi-worker deployments produce avoidable cache busts and an "
                "unstable dashboard 'Proxy $ Saved' hero tile (each /stats poll "
                "hits a different worker's partial total) when sessions land on "
                "different workers. Run --workers 1 or place a sticky-session load "
                "balancer in front of multiple --workers 1 processes. "
                "See RUST_DEV.md -> 'Multi-worker deployment -- CCR fragmentation'.",
                workers,
            )
        else:
            logger.warning(
                "Cutctx is running with workers=%d. The in-memory CCR store, "
                "compression cache, prefix tracker, TOIN state, and CostTracker are all "
                "per-process; multi-worker deployments produce silent CCR retrieval "
                "failures, avoidable cache busts, and an unstable dashboard 'Proxy $ Saved' "
                "hero tile (each /stats poll hits a different worker's partial total) when "
                "sessions land on different workers. Set CUTCTX_CCR_BACKEND=sqlite for a "
                "persistent cross-worker CCR store, run --workers 1, or place a "
                "sticky-session load balancer in front of multiple --workers 1 processes. "
                "See RUST_DEV.md -> 'Multi-worker deployment -- CCR fragmentation'.",
                workers,
            )
        os.environ[_MULTI_WORKER_CONFIG_ENV] = json.dumps(_proxy_config_payload(config))
        app_target = "cutctx.proxy.server:create_app_from_env"
        uvicorn_kwargs["factory"] = True
    else:
        app_target = create_app(config)

    if config.tls_cert and config.tls_key:
        uvicorn_kwargs["ssl_certfile"] = config.tls_cert
        uvicorn_kwargs["ssl_keyfile"] = config.tls_key

    uvicorn.run(
        app_target,
        host=config.host,
        port=config.port,
        log_level="warning",
        workers=workers if workers > 1 else None,  # None = single process (default)
        limit_concurrency=limit_concurrency,
        # Defense-in-depth: the loopback guard for /debug/* endpoints trusts
        # request.client.host. uvicorn's ProxyHeadersMiddleware rewrites that
        # from X-Forwarded-For when FORWARDED_ALLOW_IPS is broader than the
        # default. Disabling proxy_headers here guarantees the guard sees the
        # real peer address regardless of env.
        proxy_headers=False,
        # uvicorn defaults to ws_ping_interval=20s / ws_ping_timeout=20s.
        # Codex's WS session (/v1/responses) stays open across an entire
        # agent turn, including local tool calls that can run for minutes
        # (a shell command, a test suite) before the client sends anything
        # else on the socket. A 20s pong timeout is well inside that window,
        # so uvicorn was closing the connection server-side mid-turn —
        # surfacing to the user as "stream disconnected before completion"
        # followed by reconnect attempts that fail with "Bad Request" since
        # a fresh WS can't resume the prior turn's pending tool-call state.
        # 10 minutes comfortably covers long local tool calls without
        # masking a genuinely dead peer for an unreasonable amount of time.
        ws_ping_interval=600,
        ws_ping_timeout=600,
        **uvicorn_kwargs,
    )


def _get_env_bool(name: str, default: bool) -> bool:
    """Get boolean from environment variable."""
    val = os.environ.get(name)
    if val is None:
        return default
    return val.lower() in ("true", "1", "yes", "on")


def _get_env_int(name: str, default: int) -> int:
    """Get integer from environment variable."""
    val = os.environ.get(name)
    if val is None:
        return default
    try:
        return int(val)
    except ValueError:
        return default


def _get_env_float(name: str, default: float) -> float:
    """Get float from environment variable."""
    val = os.environ.get(name)
    if val is None:
        return default
    try:
        return float(val)
    except ValueError:
        return default


def _get_env_str(name: str, default: str) -> str:
    """Get string from environment variable."""
    return os.environ.get(name, default)


def _parse_exclude_tools(cli_excludes: str | None) -> set[str]:
    """Parse extra never-compress tool names from CLI args and env var.

    Both --exclude-tools and CUTCTX_EXCLUDE_TOOLS are comma-separated
    (e.g. "WebSearch,WebFetch"). Each name is added in both original and
    lowercase form for case-insensitive matching, mirroring
    DEFAULT_EXCLUDE_TOOLS. Unset/empty -> empty set (DEFAULT_EXCLUDE_TOOLS
    used unchanged).
    """
    raw = ",".join(s for s in (cli_excludes, os.environ.get("CUTCTX_EXCLUDE_TOOLS")) if s)
    names: set[str] = set()
    for entry in raw.split(","):
        name = entry.strip()
        if name:
            names.add(name)
            names.add(name.lower())
    return names


def _parse_tool_profiles(cli_profiles: list[str]) -> dict[str, Any]:
    """Parse tool profiles from CLI args and CUTCTX_TOOL_PROFILES env var.

    Format: ToolName:level (e.g., Grep:conservative, Bash:moderate)
    Env var format: comma-separated (e.g., "Grep:conservative,Bash:moderate")

    Returns:
        Dict mapping tool names to CompressionProfile instances.
    """
    from cutctx.config import PROFILE_PRESETS, CompressionProfile

    profiles: dict[str, CompressionProfile] = {}
    raw_entries: list[str] = list(cli_profiles)

    # Also check env var
    env_val = os.environ.get("CUTCTX_TOOL_PROFILES", "")
    if env_val:
        raw_entries.extend(e.strip() for e in env_val.split(",") if e.strip())

    for entry in raw_entries:
        if ":" not in entry:
            logger.warning("Invalid tool profile format (expected ToolName:level): %s", entry)
            continue
        tool_name, level = entry.split(":", 1)
        tool_name = tool_name.strip()
        level = level.strip().lower()

        if level in PROFILE_PRESETS:
            profiles[tool_name] = PROFILE_PRESETS[level]
        else:
            logger.warning(
                "Unknown profile level '%s' for tool '%s'. Use: conservative, moderate, aggressive",
                level,
                tool_name,
            )

    return profiles


def _parse_sso_role_mapping(raw: str | None) -> dict[str, str]:
    """Parse SSO role mapping from a comma-separated claim=role string."""
    mapping: dict[str, str] = {}
    if not raw:
        return mapping
    for pair in raw.split(","):
        entry = pair.strip()
        if not entry or "=" not in entry:
            continue
        claim, role = entry.split("=", 1)
        claim = claim.strip()
        role = role.strip()
        if claim and role:
            mapping[claim] = role
    return mapping


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Cutctx Proxy Server")

    # Server
    parser.add_argument("--host", default="127.0.0.1")
    parser.add_argument("--port", type=int, default=8787)
    parser.add_argument(
        "--openai-api-url", help=f"Custom OpenAI API URL (default: {DEFAULT_OPENAI_API_URL})"
    )
    parser.add_argument(
        "--anthropic-api-url",
        help=f"Custom Anthropic API URL (default: {DEFAULT_ANTHROPIC_API_URL})",
    )
    parser.add_argument(
        "--vertex-api-url",
        help=f"Custom Vertex AI regional API URL (default: {DEFAULT_VERTEX_API_URL})",
    )

    # Backend (anthropic direct, bedrock, openrouter, anyllm, or litellm-<provider>)
    parser.add_argument(
        "--backend",
        default="anthropic",
        help=(
            "Backend: 'anthropic' (direct), 'bedrock' (AWS), 'openrouter', "
            "'anyllm' (any-llm), or 'litellm-<provider>' (e.g., litellm-hosted_vllm, litellm-vertex)"
        ),
    )
    parser.add_argument(
        "--bedrock-region",
        default="us-west-2",
        help="AWS region for Bedrock backend (default: us-west-2)",
    )
    parser.add_argument(
        "--bedrock-profile",
        help="AWS profile for Bedrock backend (default: use default credentials)",
    )
    parser.add_argument(
        "--openrouter-api-key",
        help="OpenRouter API key (or set OPENROUTER_API_KEY env var)",
    )
    parser.add_argument(
        "--anyllm-provider",
        default="openai",
        help="any-llm provider: openai, anthropic, mistral, groq, ollama, bedrock, etc. (default: openai)",
    )

    # Connection pool (scalability)
    parser.add_argument(
        "--max-connections",
        type=int,
        default=500,
        help="Max connections to upstream APIs (default: 500)",
    )
    parser.add_argument(
        "--max-keepalive", type=int, default=100, help="Max keepalive connections (default: 100)"
    )
    parser.add_argument(
        "--no-http2",
        action="store_true",
        help="Disable HTTP/2 (enabled by default for better throughput)",
    )
    parser.add_argument(
        "--workers",
        type=int,
        default=1,
        help="Number of worker processes (default: 1, use N for multi-core)",
    )
    parser.add_argument(
        "--limit-concurrency",
        type=int,
        default=1000,
        help="Max concurrent connections before 503 (default: 1000)",
    )

    # Optimization
    parser.add_argument("--no-optimize", action="store_true", help="Disable optimization")
    parser.add_argument("--min-tokens", type=int, default=500, help="Min tokens to crush")
    parser.add_argument("--max-items", type=int, default=50, help="Max items after crush")
    parser.add_argument(
        "--tool-profile",
        action="append",
        default=[],
        help="Per-tool compression profile: ToolName:level (e.g., Grep:conservative, Bash:moderate, WebFetch:aggressive). "
        "Can be specified multiple times. Also settable via CUTCTX_TOOL_PROFILES env var.",
    )
    parser.add_argument(
        "--compress-user-messages",
        action="store_true",
        help=(
            "Opt in to compressing `user` role messages. Default is off because "
            "user content is typically the subject of the request and is part of "
            "the prefix-cache zone. Enable this for OpenAI/Azure chat workloads "
            "where the bulk of input lives in user messages (pasted content, "
            "RAG context, etc.) and you want the router to consider it eligible. "
            "Also settable via CUTCTX_COMPRESS_USER_MESSAGES=1."
        ),
    )
    parser.add_argument(
        "--disable-kompress",
        action="store_true",
        help=(
            "Disable Kompress ML compression while keeping structural compression enabled. "
            "Also settable via CUTCTX_DISABLE_KOMPRESS=1."
        ),
    )
    parser.add_argument(
        "--exclude-tools",
        default=None,
        help="Comma-separated tool names whose output is never compressed, "
        "merged with the built-in defaults (e.g., WebSearch,WebFetch). "
        "Also settable via CUTCTX_EXCLUDE_TOOLS env var.",
    )

    # Caching
    parser.add_argument("--no-cache", action="store_true", help="Disable caching")
    parser.add_argument("--cache-ttl", type=int, default=3600, help="Cache TTL seconds")

    # Security & admin
    parser.add_argument(
        "--admin-api-key",
        default=None,
        help="Admin API key for /dashboard, /stats, /stats-reset, /transformations/feed. "
        "Also settable via CUTCTX_ADMIN_API_KEY env var.",
    )
    parser.add_argument(
        "--cors-origins",
        default=None,
        help="Comma-separated CORS allowed origins. Empty = closed. '*' = open. "
        "Also settable via CUTCTX_CORS_ORIGINS env var.",
    )
    parser.add_argument(
        "--max-body-mb",
        type=int,
        default=50,
        help="Maximum request body size in MB for compression (default: 50). "
        "Bodies larger are forwarded unchanged. Also settable via CUTCTX_MAX_BODY_MB.",
    )

    # Entitlements & enterprise
    parser.add_argument(
        "--entitlement-tier",
        default=None,
        help="Override entitlement tier (builder, team, business, enterprise). "
        "Auto-detected from license when set. Also settable via CUTCTX_ENTITLEMENT_TIER.",
    )
    parser.add_argument(
        "--audit-db-path",
        default=None,
        help="Path to audit log SQLite database. Default: ~/.cutctx/audit.db. "
        "Also settable via CUTCTX_AUDIT_DB_PATH.",
    )
    parser.add_argument(
        "--no-audit",
        action="store_true",
        help="Disable audit logging (enabled by default).",
    )
    parser.add_argument(
        "--org-db-path",
        default=None,
        help="Path to org/workspace/project SQLite database. Default: ~/.cutctx/org.db. "
        "Also settable via CUTCTX_ORG_DB_PATH.",
    )
    parser.add_argument(
        "--no-org",
        action="store_true",
        help="Disable org store (enabled by default).",
    )
    parser.add_argument(
        "--fleet-db-path",
        default=None,
        help="Path to fleet registry SQLite database. Default: ~/.cutctx/fleet.db. "
        "Also settable via CUTCTX_FLEET_DB_PATH.",
    )
    parser.add_argument(
        "--no-fleet",
        action="store_true",
        help="Disable fleet registry (enabled by default).",
    )
    parser.add_argument(
        "--scim-db-path",
        default=None,
        help="Path to SCIM provisioning SQLite database. Default: ~/.cutctx/scim.db. "
        "Also settable via CUTCTX_SCIM_DB_PATH.",
    )
    parser.add_argument(
        "--no-scim",
        action="store_true",
        help="Disable SCIM provisioning store (enabled by default).",
    )
    parser.add_argument(
        "--sso-provider-type",
        default=None,
        help="SSO provider type: oidc, jwt, or introspect. "
        "Also settable via CUTCTX_SSO_PROVIDER_TYPE.",
    )
    parser.add_argument(
        "--sso-discovery-url",
        default=None,
        help="OIDC discovery URL. Also settable via CUTCTX_SSO_DISCOVERY_URL.",
    )
    parser.add_argument(
        "--sso-jwks-uri",
        default=None,
        help="JWKS URI for JWT validation. Also settable via CUTCTX_SSO_JWKS_URI.",
    )
    parser.add_argument(
        "--sso-issuer",
        default=None,
        help="Expected SSO token issuer. Also settable via CUTCTX_SSO_ISSUER.",
    )
    parser.add_argument(
        "--sso-audience",
        default=None,
        help="Expected SSO token audience. Also settable via CUTCTX_SSO_AUDIENCE.",
    )
    parser.add_argument(
        "--sso-introspection-url",
        default=None,
        help="Token introspection URL. Also settable via CUTCTX_SSO_INTROSPECTION_URL.",
    )
    parser.add_argument(
        "--sso-role-mapping",
        default=None,
        help="Comma-separated claim=role mappings for SSO. "
        "Also settable via CUTCTX_SSO_ROLE_MAPPING.",
    )
    parser.add_argument(
        "--sso-default-role",
        default=None,
        help="Default role for authenticated SSO users. "
        "Also settable via CUTCTX_SSO_DEFAULT_ROLE.",
    )

    # LLM Firewall
    parser.add_argument(
        "--firewall",
        action="store_true",
        help="Enable LLM firewall (prompt injection + PII detection). "
        "Also settable via CUTCTX_FIREWALL_ENABLED=1.",
    )
    parser.add_argument(
        "--no-firewall",
        action="store_true",
        help="Explicitly disable LLM firewall.",
    )

    # Structured Output
    parser.add_argument(
        "--no-structured-output",
        action="store_true",
        help="Disable structured output validation (enabled by default when jsonschema is installed).",
    )
    parser.add_argument(
        "--structured-output-max-retries",
        type=int,
        default=3,
        help="Max retries for structured output validation (default: 3).",
    )

    # Multi-Model Ensemble
    parser.add_argument(
        "--ensemble",
        action="store_true",
        help="Enable multi-model ensemble execution. "
        "Also settable via CUTCTX_ENSEMBLE_ENABLED=1.",
    )
    parser.add_argument(
        "--ensemble-evaluator-model",
        default=None,
        help="Model to use for ensemble evaluation (default: claude-3-haiku-20240307).",
    )

    # Budget Cut-offs
    parser.add_argument(
        "--budget-cut-off",
        action="store_true",
        help="Enable streaming budget cut-offs. "
        "Also settable via CUTCTX_BUDGET_ENABLED=1.",
    )
    parser.add_argument(
        "--budget-default-tokens",
        type=int,
        default=100000,
        help="Default per-request token budget (default: 100000).",
    )

    # Rate limiting
    parser.add_argument("--no-rate-limit", action="store_true", help="Disable rate limiting")
    parser.add_argument("--rpm", type=int, default=60, help="Requests per minute")
    parser.add_argument("--tpm", type=int, default=100000, help="Tokens per minute")

    # Cost
    parser.add_argument("--budget", type=float, help="Budget limit in USD")
    parser.add_argument("--budget-period", choices=["hourly", "daily", "monthly"], default="daily")

    # ── Intelligence Layer ───────────────────────────────────────────────
    parser.add_argument(
        "--task-aware", action="store_true",
        help="Enable task-aware compression (modulate by relevance to current task).",
    )
    parser.add_argument(
        "--dedup", action="store_true",
        help="Enable semantic deduplication (replace repeated content with CCR pointers).",
    )
    parser.add_argument(
        "--context-budget", action="store_true",
        help="Enable context budget controller (progressive compression as budget fills).",
    )
    parser.add_argument(
        "--context-budget-max-tokens", type=int, default=100_000,
        help="Max token budget for context budget controller (default: 100000).",
    )
    parser.add_argument(
        "--context-budget-policy",
        choices=["conservative", "balanced", "aggressive"],
        default="balanced",
        help="Context budget compression policy (default: balanced).",
    )
    parser.add_argument(
        "--profiles", action="store_true",
        help="Enable cross-session compression profiles (learn patterns per workspace).",
    )
    parser.add_argument(
        "--shared-context", action="store_true",
        help="Enable multi-agent shared compression state.",
    )
    parser.add_argument(
        "--cost-forecast", action="store_true",
        help="Enable cost forecasting + policy engine.",
    )

    # Logging
    parser.add_argument("--log-file", help="Log file path")
    parser.add_argument("--log-messages", action="store_true", help="Log full messages")

    # Code-aware compression
    parser.add_argument(
        "--code-aware",
        action="store_true",
        help="Enable AST-based code compression (requires: pip install cutctx-ai[code])",
    )
    parser.add_argument(
        "--no-code-aware",
        action="store_true",
        help="Disable code-aware compression",
    )

    args = parser.parse_args()

    # Environment variable defaults (CUTCTX_* prefix)
    # CLI args override env vars, env vars override ProxyConfig defaults
    env_code_aware = _get_env_bool("CUTCTX_CODE_AWARE_ENABLED", True)
    env_optimize = _get_env_bool("CUTCTX_OPTIMIZE", True)
    env_cache = _get_env_bool("CUTCTX_CACHE_ENABLED", True)
    env_rate_limit = _get_env_bool("CUTCTX_RATE_LIMIT_ENABLED", True)

    # Determine settings: CLI flags override env vars
    # --no-X explicitly disables, --X explicitly enables, neither uses env var
    code_aware_enabled = (
        env_code_aware
        if not (args.code_aware or args.no_code_aware)
        else (args.code_aware or not args.no_code_aware)
    )
    optimize = env_optimize if not args.no_optimize else False
    cache_enabled = env_cache if not args.no_cache else False
    rate_limit_enabled = env_rate_limit if not args.no_rate_limit else False
    disable_kompress = args.disable_kompress or _get_env_bool("CUTCTX_DISABLE_KOMPRESS", False)

    # Set OpenRouter API key from CLI if provided
    if hasattr(args, "openrouter_api_key") and args.openrouter_api_key:
        os.environ["OPENROUTER_API_KEY"] = args.openrouter_api_key

    # Parse per-tool compression profiles from CLI and env var
    tool_profiles = _parse_tool_profiles(args.tool_profile)
    # Parse extra never-compress tools from CLI and env var
    exclude_tools = _parse_exclude_tools(args.exclude_tools)

    # Parse CORS origins from CLI or env
    _cors_raw = args.cors_origins or os.environ.get("CUTCTX_CORS_ORIGINS", "")
    _cors_origins_list = [o.strip() for o in _cors_raw.split(",") if o.strip()] if _cors_raw else []
    _sso_role_mapping = _parse_sso_role_mapping(
        args.sso_role_mapping or os.environ.get("CUTCTX_SSO_ROLE_MAPPING")
    )

    config = ProxyConfig(
        host=_get_env_str("CUTCTX_HOST", args.host),
        port=_get_env_int("CUTCTX_PORT", args.port),
        openai_api_url=_get_env_str("OPENAI_TARGET_API_URL", args.openai_api_url),
        anthropic_api_url=_get_env_str("ANTHROPIC_TARGET_API_URL", args.anthropic_api_url),
        vertex_api_url=_get_env_str("VERTEX_TARGET_API_URL", args.vertex_api_url),
        # Backend settings
        backend=_get_env_str("CUTCTX_BACKEND", args.backend),  # type: ignore[arg-type]
        bedrock_region=_get_env_str("CUTCTX_BEDROCK_REGION", args.bedrock_region),
        bedrock_profile=args.bedrock_profile or os.environ.get("AWS_PROFILE"),
        anyllm_provider=_get_env_str("CUTCTX_ANYLLM_PROVIDER", args.anyllm_provider),
        optimize=optimize,
        min_tokens_to_crush=_get_env_int("CUTCTX_MIN_TOKENS", args.min_tokens),
        max_items_after_crush=_get_env_int("CUTCTX_MAX_ITEMS", args.max_items),
        cache_enabled=cache_enabled,
        cache_ttl_seconds=_get_env_int("CUTCTX_CACHE_TTL", args.cache_ttl),
        rate_limit_enabled=rate_limit_enabled,
        rate_limit_requests_per_minute=_get_env_int("CUTCTX_RPM", args.rpm),
        rate_limit_tokens_per_minute=_get_env_int("CUTCTX_TPM", args.tpm),
        budget_limit_usd=args.budget,
        budget_period=args.budget_period,
        log_file=_get_env_str("CUTCTX_LOG_FILE", args.log_file)
        if args.log_file
        else os.environ.get("CUTCTX_LOG_FILE"),
        log_full_messages=args.log_messages or _get_env_bool("CUTCTX_LOG_MESSAGES", False),
        code_aware_enabled=code_aware_enabled,
        disable_kompress=disable_kompress,
        # Connection pool settings
        max_connections=_get_env_int("CUTCTX_MAX_CONNECTIONS", args.max_connections),
        max_keepalive_connections=_get_env_int("CUTCTX_MAX_KEEPALIVE", args.max_keepalive),
        http2=not args.no_http2 and _get_env_bool("CUTCTX_HTTP2", True),
        tool_profiles=tool_profiles if tool_profiles else None,
        exclude_tools=exclude_tools if exclude_tools else None,
        mode=normalize_proxy_mode(_get_env_str("CUTCTX_MODE", PROXY_MODE_TOKEN)),
        compress_user_messages=args.compress_user_messages
        or _get_env_bool("CUTCTX_COMPRESS_USER_MESSAGES", False),
        # Security
        admin_api_key=args.admin_api_key or os.environ.get("CUTCTX_ADMIN_API_KEY"),
        cors_origins=_cors_origins_list,
        max_body_mb=_get_env_int("CUTCTX_MAX_BODY_MB", args.max_body_mb),
        # Enterprise
        entitlement_tier=args.entitlement_tier
        or os.environ.get("CUTCTX_ENTITLEMENT_TIER"),
        audit_enabled=not args.no_audit
        and not _get_env_bool("CUTCTX_AUDIT_DISABLED", False),
        audit_db_path=args.audit_db_path
        or os.environ.get("CUTCTX_AUDIT_DB_PATH"),
        org_enabled=not args.no_org
        and not _get_env_bool("CUTCTX_ORG_DISABLED", False),
        org_db_path=args.org_db_path
        or os.environ.get("CUTCTX_ORG_DB_PATH"),
        fleet_enabled=not args.no_fleet
        and not _get_env_bool("CUTCTX_FLEET_DISABLED", False),
        fleet_db_path=args.fleet_db_path
        or os.environ.get("CUTCTX_FLEET_DB_PATH"),
        scim_enabled=not args.no_scim
        and not _get_env_bool("CUTCTX_SCIM_DISABLED", False),
        scim_db_path=args.scim_db_path
        or os.environ.get("CUTCTX_SCIM_DB_PATH"),
        sso_provider_type=args.sso_provider_type
        or os.environ.get("CUTCTX_SSO_PROVIDER_TYPE", "oidc"),
        sso_discovery_url=args.sso_discovery_url
        or os.environ.get("CUTCTX_SSO_DISCOVERY_URL"),
        sso_jwks_uri=args.sso_jwks_uri
        or os.environ.get("CUTCTX_SSO_JWKS_URI"),
        sso_issuer=args.sso_issuer or os.environ.get("CUTCTX_SSO_ISSUER"),
        sso_audience=args.sso_audience
        or os.environ.get("CUTCTX_SSO_AUDIENCE"),
        sso_introspection_url=args.sso_introspection_url
        or os.environ.get("CUTCTX_SSO_INTROSPECTION_URL"),
        sso_role_mapping=_sso_role_mapping,
        sso_default_role=args.sso_default_role
        or os.environ.get("CUTCTX_SSO_DEFAULT_ROLE", "viewer"),
        # LLM Firewall
        firewall_enabled=(
            args.firewall
            or _get_env_bool("CUTCTX_FIREWALL_ENABLED", False)
        ) and not args.no_firewall,
        firewall_block_pii=not _get_env_bool("CUTCTX_FIREWALL_NO_BLOCK_PII", False),
        firewall_block_injection=not _get_env_bool("CUTCTX_FIREWALL_NO_BLOCK_INJECTION", False),
        firewall_block_jailbreak=not _get_env_bool("CUTCTX_FIREWALL_NO_BLOCK_JAILBREAK", False),
        firewall_redact_streaming=not _get_env_bool("CUTCTX_FIREWALL_NO_REDACT_STREAMING", False),
        # Structured Output
        structured_output_enabled=not args.no_structured_output
        and not _get_env_bool("CUTCTX_STRUCTURED_OUTPUT_DISABLED", False),
        structured_output_max_retries=args.structured_output_max_retries,
        # Multi-Model Ensemble
        ensemble_enabled=(
            args.ensemble
            or _get_env_bool("CUTCTX_ENSEMBLE_ENABLED", False)
        ),
        ensemble_evaluator_model=args.ensemble_evaluator_model
        or _get_env_str("CUTCTX_ENSEMBLE_EVALUATOR_MODEL", "claude-3-haiku-20240307"),
        ensemble_timeout_seconds=_get_env_float("CUTCTX_ENSEMBLE_TIMEOUT", 120.0),
        # Budget Cut-offs
        budget_cut_off_enabled=(
            args.budget_cut_off
            or _get_env_bool("CUTCTX_BUDGET_ENABLED", False)
        ),
        budget_default_tokens=_get_env_int("CUTCTX_BUDGET_TOKENS", args.budget_default_tokens),
        budget_default_usd=_get_env_float("CUTCTX_BUDGET_USD", 10.0),
        # ── Intelligence Layer ───────────────────────────────────────────
        task_aware_enabled=(
            args.task_aware or _get_env_bool("CUTCTX_TASK_AWARE_ENABLED", False)
        ),
        dedup_enabled=(
            args.dedup or _get_env_bool("CUTCTX_DEDUP_ENABLED", False)
        ),
        context_budget_enabled=(
            args.context_budget or _get_env_bool("CUTCTX_CONTEXT_BUDGET_ENABLED", False)
        ),
        context_budget_max_tokens=_get_env_int("CUTCTX_CONTEXT_BUDGET_MAX_TOKENS", args.context_budget_max_tokens),
        context_budget_policy=os.environ.get("CUTCTX_CONTEXT_BUDGET_POLICY", args.context_budget_policy),
        profiles_enabled=(
            args.profiles or _get_env_bool("CUTCTX_PROFILES_ENABLED", False)
        ),
        shared_context_enabled=(
            args.shared_context or _get_env_bool("CUTCTX_SHARED_CONTEXT_ENABLED", False)
        ),
        cost_forecast_enabled=(
            args.cost_forecast or _get_env_bool("CUTCTX_COST_FORECAST_ENABLED", False)
        ),
    )

    # Get worker and concurrency settings
    workers = _get_env_int("CUTCTX_WORKERS", args.workers)
    limit_concurrency = _get_env_int("CUTCTX_LIMIT_CONCURRENCY", args.limit_concurrency)

    run_server(config, workers=workers, limit_concurrency=limit_concurrency)


def _policies_summary() -> dict[str, object]:
    """Build a lightweight summary of learned policies for the /stats endpoint.

    This is intentionally not a SavingsSource — WS18 learned policies tune
    compression behavior rather than producing independent savings. The
    dashboard panel shows visibility into what's been learned.
    """
    try:
        from cutctx.policy_learning import default_policy_db_path, load_policies

        db_path = default_policy_db_path()
        if not db_path.exists():
            return {"count": 0, "enabled": False}

        policies = load_policies(db_path)
        by_aggressiveness: dict[str, int] = {}
        by_algorithm: dict[str, int] = {}
        total_samples = 0
        for policy in policies:
            by_aggressiveness[policy.aggressiveness] = (
                by_aggressiveness.get(policy.aggressiveness, 0) + 1
            )
            by_algorithm[policy.algorithm_hint] = (
                by_algorithm.get(policy.algorithm_hint, 0) + 1
            )
            total_samples += policy.samples

        return {
            "count": len(policies),
            "enabled": len(policies) > 0,
            "total_samples": total_samples,
            "by_aggressiveness": dict(sorted(by_aggressiveness.items())),
            "by_algorithm_hint": dict(sorted(by_algorithm.items())),
        }
    except Exception:
        return {"count": 0, "enabled": False}
