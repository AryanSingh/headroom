"""Data models for the Cutctx proxy.

Contains configuration and data classes used across the proxy modules.
Extracted from server.py to keep the codebase maintainable.
"""

from __future__ import annotations

from dataclasses import InitVar, dataclass, field
from datetime import datetime
import os
from typing import Any, Literal

from headroom.memory import qdrant_env
from headroom.providers.registry import ProviderApiOverrides

_DEFAULT_LICENSE_API_URL = (
    os.environ.get("PITCHTOSHIP_URL")
    or os.environ.get("HEADROOM_LICENSE_API_URL")
    or "https://pitchtoship.com"
)

# =============================================================================
# Data Models
# =============================================================================


@dataclass
class RequestLog:
    """Complete log of a single request."""

    request_id: str
    timestamp: str
    provider: str
    model: str

    # Tokens
    input_tokens_original: int
    input_tokens_optimized: int
    output_tokens: int | None
    tokens_saved: int
    savings_percent: float

    # Performance
    optimization_latency_ms: float
    total_latency_ms: float | None

    # Metadata
    tags: dict[str, str]
    cache_hit: bool
    transforms_applied: list[str]

    # Waste signals detected in original messages
    waste_signals: dict[str, int] | None = None

    # Request/Response (optional, for debugging)
    request_messages: list[dict] | None = None
    # Messages after compression, as actually sent upstream. Paired with
    # `request_messages` (the pre-compression snapshot) so consumers can diff
    # the two sides of the compression. Governed by the same
    # `log_full_messages` gate as `request_messages`.
    compressed_messages: list[dict] | None = None
    response_content: str | None = None
    error: str | None = None

    # Groups every agent-loop API call from one user prompt into a single turn.
    # See ``headroom.proxy.helpers.compute_turn_id`` for the derivation. None
    # when no user-text message is present in the request.
    turn_id: str | None = None

    # NOTE (Unit 2 follow-up): stage timings and session_id were briefly
    # added here but are now emitted exclusively through
    # ``emit_stage_timings_log`` (structured log line) and Prometheus.
    # They were never populated on ``RequestLog`` instances, so the
    # fields were removed to avoid confusing readers who expect
    # them to be set. If a JSONL consumer needs them, have the consumer
    # merge ``stage_timings`` log lines by ``request_id``.


@dataclass
class CacheEntry:
    """Cached response entry."""

    response_body: bytes
    response_headers: dict[str, str]
    created_at: datetime
    ttl_seconds: int
    hit_count: int = 0
    tokens_saved_per_hit: int = 0


@dataclass
class RateLimitState:
    """Token bucket rate limiter state."""

    tokens: float
    last_update: float


@dataclass
class ProxyConfig:
    """Proxy configuration."""

    # Server
    host: str = "127.0.0.1"
    port: int = 8787
    anthropic_api_url: str | None = None  # Custom Anthropic API URL override
    openai_api_url: str | None = None  # Custom OpenAI API URL override
    gemini_api_url: str | None = None  # Custom Gemini API URL override
    cloudcode_api_url: str | None = None  # Custom Cloud Code Assist API URL override
    vertex_api_url: str | None = None  # Custom Vertex AI regional API URL override

    # Backend: "anthropic" (direct API), "litellm-*" (via LiteLLM), or "anyllm" (via any-llm)
    backend: str = "anthropic"
    bedrock_region: str = "us-west-2"
    bedrock_profile: str | None = None
    anyllm_provider: str = "openai"

    # Optimization mode: "token" (rewrite for max compression) or
    # "cache" (freeze prior turns for prefix-cache stability).
    mode: str = "token"

    # Optimization
    optimize: bool = True
    image_optimize: bool = True
    min_tokens_to_crush: int = 500
    max_items_after_crush: int = 50
    smart_crusher_with_compaction: bool | None = None
    keep_last_turns: int = 4

    # CCR Tool Injection
    ccr_inject_tool: bool = True
    ccr_inject_system_instructions: bool = False
    # Proxy-level mirror of ContentRouterConfig.ccr_inject_marker, so retrieval
    # markers can be toggled from the CLI (--no-ccr-marker). Threaded into the
    # router in server.py; default preserves current behavior.
    ccr_inject_marker: bool = True

    # CCR Response Handling
    ccr_handle_responses: bool = True
    ccr_max_retrieval_rounds: int = 3

    # CCR Context Tracking
    ccr_context_tracking: bool = True
    ccr_proactive_expansion: bool = True
    ccr_max_proactive_expansions: int = 2

    # CCR store TTL: how long originals are retained for retrieval.
    # 0 = never expire. Default 1800s (30 min) balances memory vs long agent runs.
    # CLI: --ccr-ttl-seconds; env: HEADROOM_CCR_TTL_SECONDS.
    ccr_store_ttl_seconds: int = 1800

    # Code-aware compression (disabled by default — use code graph tools instead)
    code_aware_enabled: bool = False

    # Disable Kompress ML compression while keeping structural compressors
    # such as SmartCrusher, log/search/diff, and schema compaction enabled.
    # CLI: --disable-kompress; env: HEADROOM_DISABLE_KOMPRESS=1.
    disable_kompress: bool = False

    # Use LLMLingua-2 for plain-text compression instead of Kompress.
    # Requires: pip install cutctx-ai[llmlingua]
    # CLI: --llmlingua; env: HEADROOM_USE_LLMLINGUA=1.
    use_llmlingua: bool = False

    # Query-aware compression: adapt protect_recent and min_tokens_to_crush
    # based on the detected task type from the last user message.
    # CODE/DEBUG tasks protect more context; SUMMARIZE/LIST tasks compress harder.
    # CLI: --query-aware; env: HEADROOM_QUERY_AWARE=1.
    query_aware_compression: bool = False

    # Selective context filter: drop low-relevance messages before compression.
    # Scores each turn against the most recent user query; turns below
    # selective_filter_threshold are removed entirely. Disabled by default.
    # CLI: --selective-filter; env: HEADROOM_SELECTIVE_FILTER=1.
    selective_filter: bool = False
    selective_filter_threshold: float = 0.15

    # Code graph live watcher (triggers incremental reindex on file changes)
    code_graph_watcher: bool = False

    # Per-tool compression profiles
    tool_profiles: dict[str, Any] | None = None

    # Opt in to compressing `user` role messages. Off by default because user
    # content is typically the subject of the request and is part of the
    # prefix-cache zone. Enable for OpenAI/Azure chat workloads where the bulk
    # of input lives in user messages (pasted code/text, RAG context) and the
    # router would otherwise have nothing eligible to compress.
    # CLI: --compress-user-messages; env: HEADROOM_COMPRESS_USER_MESSAGES=1.
    compress_user_messages: bool = False
    # Named savings policy shared across Claude/Codex/Cursor proxy handlers.
    # CLI/env: HEADROOM_SAVINGS_PROFILE=agent-90.
    savings_profile: str | None = None
    target_ratio: float | None = None
    compress_system_messages: bool | None = None
    protect_recent: int | None = None
    protect_analysis_context: bool | None = None
    accuracy_guard: str | None = None

    # Extra tool names whose outputs are never compressed, merged with the
    # built-in DEFAULT_EXCLUDE_TOOLS. None means built-in defaults only.
    # CLI: --exclude-tools <name1,name2>; env: HEADROOM_EXCLUDE_TOOLS=<name1,name2>
    exclude_tools: set[str] | None = None

    # Read lifecycle management
    read_lifecycle: bool = True

    # Deprecated compatibility argument. ContentRouter is always active in
    # the Python proxy; accepting this avoids breaking old config constructors
    # while keeping it out of runtime state.
    smart_routing: InitVar[bool | None] = None

    # Caching
    cache_enabled: bool = True
    cache_ttl_seconds: int = 3600
    cache_max_entries: int = 1000

    # Rate limiting
    rate_limit_enabled: bool = True
    rate_limit_requests_per_minute: int = 60
    rate_limit_tokens_per_minute: int = 100000

    # Retry
    retry_enabled: bool = True
    retry_max_attempts: int = 3
    retry_base_delay_ms: int = 1000
    retry_max_delay_ms: int = 30000

    # Prefix freeze
    prefix_freeze_enabled: bool = True
    prefix_freeze_session_ttl: int = 600

    # Cost tracking
    cost_tracking_enabled: bool = True
    budget_limit_usd: float | None = None
    budget_period: Literal["hourly", "daily", "monthly"] = "daily"

    # Logging
    log_requests: bool = True
    log_file: str | None = None
    log_full_messages: bool = False

    # Third-party proxy extensions (opt-in only). List of entry-point names
    # to enable from the `headroom.proxy_extension` group, or `["*"]` for
    # wildcard. Empty/None means no extensions run, even if installed.
    # CLI: --proxy-extension <name1,name2>; env: HEADROOM_PROXY_EXTENSIONS.
    proxy_extensions: list[str] | None = None

    # Fallback
    fallback_enabled: bool = False
    fallback_provider: str | None = None

    # Timeouts
    request_timeout_seconds: int = 300
    connect_timeout_seconds: int = 10

    # Connection pool
    max_connections: int = 500
    max_keepalive_connections: int = 100
    http2: bool = True

    # Memory System
    memory_enabled: bool = False
    memory_backend: Literal["local", "qdrant-neo4j"] = "local"
    memory_db_path: str = ""  # Empty = auto: {cwd}/.headroom/memory.db
    # Per-project memory routing (GH #462). ``project`` (the new default)
    # gives each resolved workspace its own SQLite DB so cross-project
    # bleed becomes structurally impossible. ``user`` partitions by
    # x-headroom-user-id only. ``global`` keeps the pre-fix single-DB
    # behaviour (existing memories remain reachable here).
    memory_storage_mode: Literal["project", "user", "global"] = "project"
    memory_project_root_override: str = ""
    memory_inject_tools: bool = True
    traffic_learning_enabled: bool = False
    traffic_learning_agent_type: str = "unknown"  # Which agent is being wrapped
    # Minimum evidence count before a learned pattern is persisted to memory.
    # Higher values reduce one-shot noise at the cost of slower learning.
    traffic_learning_min_evidence: int = 5
    memory_use_native_tool: bool = False
    memory_inject_context: bool = True
    memory_top_k: int = 10
    memory_min_similarity: float = 0.3
    # PR-B6: Memory injection mode. ``"auto_tail"`` (default) auto-appends
    # retrieved memory to the latest user message tail (live zone).
    # ``"tool"`` disables auto-injection — the model must call
    # ``memory_search`` to retrieve. See REALIGNMENT/04-phase-B-live-zone.md
    # PR-B6.
    memory_mode: Literal["auto_tail", "tool"] = "auto_tail"
    # Qdrant connection (defaults resolve from HEADROOM_QDRANT_* env vars)
    memory_qdrant_url: str | None = field(default_factory=qdrant_env.qdrant_env_url)
    memory_qdrant_host: str = field(default_factory=qdrant_env.qdrant_env_host)
    memory_qdrant_port: int = field(default_factory=qdrant_env.qdrant_env_port)
    memory_qdrant_api_key: str | None = field(default_factory=qdrant_env.qdrant_env_api_key)
    memory_neo4j_uri: str = "neo4j://localhost:7687"
    memory_neo4j_user: str = "neo4j"
    memory_neo4j_password: str = ""
    memory_bridge_enabled: bool = False
    memory_bridge_md_paths: list[str] = field(default_factory=list)
    memory_bridge_md_format: str = "auto"
    memory_bridge_auto_import: bool = False
    memory_bridge_export_path: str = ""

    # Episodic Memory (file-backed cross-session memory)
    # Extracts insights from completed sessions and injects them into
    # new sessions. Gated on HEADROOM_EPISODIC_MEMORY_ENABLED=1.
    episodic_memory_enabled: bool = False
    episodic_idle_timeout_seconds: int = 300  # 5 min idle before extraction
    episodic_extraction_model: str = "claude-3-haiku-20240307"

    # Phase 3.3: provider-aware savings policy.
    # Coarse workload class used by the strategy resolver. Values:
    # "coding_agent", "support_search", "long_doc_qa",
    # "repetitive_workflow", "unknown".
    workload_class: str = "coding_agent"
    # Optional user overrides for the policy resolver, as a JSON string.
    policy_overrides_json: str | None = None

    # License / Usage Reporting
    license_key: str | None = None
    license_cloud_url: str = field(default_factory=lambda: _DEFAULT_LICENSE_API_URL)
    license_report_interval: int = 300

    # Entitlement tier (auto-detected from license if set, or manual override).
    # Values: "builder" (free), "team", "business", "enterprise".
    # CLI: --entitlement-tier <tier>. Env: HEADROOM_ENTITLEMENT_TIER=<tier>.
    entitlement_tier: str | None = None

    # Admin API key — gates /dashboard, /stats, /stats-reset, /transformations/feed.
    # When set, requests must include `Authorization: Bearer <admin_api_key>` or
    # `X-Headroom-Admin-Key: <admin_api_key>` header. When None, these endpoints
    # are open (backward-compatible default). Env: HEADROOM_ADMIN_API_KEY.
    admin_api_key: str | None = None

    # CORS — comma-separated list of allowed origins. Defaults to empty list
    # (closed — no cross-origin requests allowed). Set to "*" to allow all
    # origins (not recommended for production). Env: HEADROOM_CORS_ORIGINS.
    # Examples:
    #   HEADROOM_CORS_ORIGINS="https://app.example.com,https://staging.example.com"
    #   HEADROOM_CORS_ORIGINS="*"  # open (dev only)
    cors_origins: list[str] = field(default_factory=list)

    # Maximum request body size in MB for the compression path.
    # Bodies larger than this are forwarded unchanged. Env: HEADROOM_MAX_BODY_MB.
    # Default: 50MB (reduced from 100MB for safer memory usage).
    max_body_mb: int = 50

    # Audit logging (enterprise compliance).
    # When enabled, all admin actions are logged to a SQLite database.
    # Env: HEADROOM_AUDIT_DISABLED=1 to disable.
    audit_enabled: bool = True
    audit_db_path: str | None = None  # None = ~/.headroom/audit.db

    # Org / workspace / project model (enterprise multi-tenant).
    # When enabled, org management endpoints are available.
    # Env: HEADROOM_ORG_DISABLED=1 to disable.
    org_enabled: bool = True
    org_db_path: str | None = None  # None = ~/.headroom/org.db

    # Fleet registry (enterprise deployment inventory).
    # Tracks deployment heartbeats and fleet health.
    fleet_enabled: bool = True
    fleet_db_path: str | None = None  # None = ~/.headroom/fleet.db

    # SCIM-like provisioning store (enterprise identity sync).
    # Stores provisioned users/groups for admin-plane integrations.
    scim_enabled: bool = True
    scim_db_path: str | None = None  # None = ~/.headroom/scim.db

    # LLM Firewall — prompt injection & PII detection
    # When enabled, all incoming messages are scanned for injections, PII,
    # and jailbreaks before reaching the upstream LLM.
    # Env: HEADROOM_FIREWALL_ENABLED=1
    firewall_enabled: bool = False
    firewall_block_pii: bool = True
    firewall_block_injection: bool = True
    firewall_block_jailbreak: bool = True
    firewall_redact_streaming: bool = True

    # Structured Output Enforcement — JSON schema validation + auto-retry
    # When enabled, responses to json_schema requests are validated and
    # retried up to N times if the LLM produces invalid JSON.
    # Env: HEADROOM_STRUCTURED_OUTPUT_ENABLED=1
    structured_output_enabled: bool = True
    structured_output_max_retries: int = 3

    # Multi-Model Ensemble — fan-out to multiple models + evaluator
    # When enabled, requests to headroom-ensemble-v1 are fanned out.
    # Env: HEADROOM_ENSEMBLE_ENABLED=1
    ensemble_enabled: bool = False
    ensemble_evaluator_model: str = "claude-3-haiku-20240307"
    ensemble_timeout_seconds: float = 120.0

    # Budget Cut-offs — terminate streams when token budget exceeded
    # When enabled, streaming responses are truncated with a system message.
    # Env: HEADROOM_BUDGET_ENABLED=1
    budget_cut_off_enabled: bool = False
    budget_default_tokens: int = 100_000
    budget_default_usd: float = 10.0

    # ── Intelligence Layer ───────────────────────────────────────────────
    # Task-Aware Compression — modulate compression based on extracted task.
    # Env: HEADROOM_TASK_AWARE_ENABLED=1
    task_aware_enabled: bool = False

    # Semantic Deduplication — replace repeated content with CCR pointers.
    # Env: HEADROOM_DEDUP_ENABLED=1
    dedup_enabled: bool = False

    # Context Budget — progressive compression as token budget fills.
    # Env: HEADROOM_CONTEXT_BUDGET_ENABLED=1
    context_budget_enabled: bool = False
    context_budget_max_tokens: int = 100_000
    context_budget_policy: str = "balanced"  # conservative / balanced / aggressive

    # Cross-Session Profiles — learn compression patterns per workspace.
    # Env: HEADROOM_PROFILES_ENABLED=1
    profiles_enabled: bool = False

    # Multi-Agent Shared State — shared compression cache across agents.
    # Env: HEADROOM_SHARED_CONTEXT_ENABLED=1
    shared_context_enabled: bool = False

    # Cost Forecasting + Policy Engine — pre-task cost estimation + policy rules.
    # Env: HEADROOM_COST_FORECAST_ENABLED=1
    cost_forecast_enabled: bool = False

    # Compression Hooks
    hooks: Any = None
    pipeline_extensions: list[Any] = field(default_factory=list)
    discover_pipeline_extensions: bool = True

    # SSO / OIDC (enterprise IdP authentication).
    # When enabled, Bearer tokens are validated against the configured IdP.
    # Env: HEADROOM_SSO_DISCOVERY_URL, HEADROOM_SSO_JWKS_URI, etc.
    sso_enabled: bool = False
    sso_provider_type: str = "oidc"  # "oidc", "jwt", "introspect"
    sso_discovery_url: str | None = None
    sso_jwks_uri: str | None = None
    sso_issuer: str | None = None
    sso_audience: str | None = None
    sso_introspection_url: str | None = None
    sso_role_mapping: dict[str, str] = field(default_factory=dict)
    sso_default_role: str = "viewer"

    # Subscription Window Tracking (Anthropic OAuth accounts)
    subscription_tracking_enabled: bool = True
    subscription_poll_interval_s: int = 300
    subscription_active_window_s: int = 60

    # Stateless mode — disable all filesystem writes for read-only / container deployments
    stateless: bool = False

    # Unit 4: Bounded pre-upstream concurrency for Anthropic replay storms.
    #
    # Caps the number of simultaneous requests allowed to run the
    # pre-upstream phase of ``handle_anthropic_messages`` (request JSON
    # read → deep-copy → first compression stage → memory-context lookup
    # → first upstream connect). Prevents cold-start replay storms from
    # monopolising the event loop / thread pool and starving ``/livez``,
    # ``/readyz``, and new Codex WS opens. Compression stays on.
    #
    # ``None`` (default) -> auto-compute ``max(2, min(8, os.cpu_count() or 4))``.
    # ``0`` or negative  -> disables the semaphore (unbounded); useful for
    # the Unit 6 counter-factual and for deliberately reproducing the
    # original starvation. Any positive integer is honored verbatim.
    #
    # CLI: ``--anthropic-pre-upstream-concurrency``.
    # Env: ``HEADROOM_ANTHROPIC_PRE_UPSTREAM_CONCURRENCY``.
    # Precedence: CLI > env > auto-compute.
    anthropic_pre_upstream_concurrency: int | None = None
    # Upper bound for waiting on the Anthropic pre-upstream semaphore
    # before failing fast with a 503 + Retry-After. Keeps the queue bounded
    # when all pre-upstream slots are occupied by slow/hung work.
    anthropic_pre_upstream_acquire_timeout_seconds: float = 15.0
    # Fail-open timeout for Anthropic memory-context lookup while the request
    # is still holding a pre-upstream slot. Compression already has its own
    # COMPRESSION_TIMEOUT_SECONDS guard; this bounds the memory leg too.
    anthropic_pre_upstream_memory_context_timeout_seconds: float = 2.0

    # Bound the dedicated compression threadpool. CPU-bound Rust work runs
    # here; the pool is separate from asyncio's default executor so other
    # ``asyncio.to_thread`` callers (file IO, etc.) are not contended by
    # compression bursts. ``None`` resolves to ``min(32, (cpu_count or 1) * 4)``,
    # matching asyncio's default executor sizing today. Lower the cap to
    # tighten resource use on multi-tenant hosts; raise it to handle larger
    # bursts. CLI: ``--compression-max-workers``. Env:
    # ``HEADROOM_COMPRESSION_MAX_WORKERS``.
    #
    # Background: ``asyncio.wait_for`` cancellation does NOT propagate into
    # the threadpool worker that's running Rust code — once the worker has
    # picked up the task, ``concurrent.futures.Future.cancel()`` returns
    # ``False`` and the thread runs to completion. A bounded pool lets us
    # observe the worst case (max queue depth, "leaked" threads that
    # finished post-deadline) and fail fast under contention rather than
    # piling unboundedly on the default executor. See
    # ``HeadroomProxy._run_compression_in_executor``.
    compression_max_workers: int | None = None

    def __post_init__(self, smart_routing: bool | None = None) -> None:
        if self.retry_enabled and self.retry_max_attempts < 1:
            raise ValueError("retry_max_attempts must be >= 1 when retry_enabled=True")

    @property
    def provider_api_overrides(self) -> ProviderApiOverrides:
        """Return provider API URL overrides as a dedicated provider config object."""
        return ProviderApiOverrides(
            anthropic=self.anthropic_api_url,
            openai=self.openai_api_url,
            gemini=self.gemini_api_url,
            cloudcode=self.cloudcode_api_url,
            vertex=self.vertex_api_url,
        )
