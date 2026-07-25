# CUTCTX Environment Variables Reference

This reference documents environment variables that are **grounded in actual code** where they are read or used.

**Total variables documented: 205**

- 190 confirmed environment variable reads (via os.environ, env::var, etc.)
- 47 variables defined in .env.example (11 fabricated/unread vars removed)
- 32 variables overlap between the two lists

## Configuration Priority

Environment variable configuration follows this precedence:

```
CLI flag > Environment variable > Default value
```

When a variable is unset, the proxy uses the default value listed below. All defaults are verified against the actual codebase.

## Security-Sensitive Variables

These variables have security implications and should be reviewed carefully:

Review every row before exposing a deployment to a network. The first entry
changes the deployment's network egress boundary and is the one most likely to
be set without understanding the consequence.

| Variable | Risk Level | Impact |
|----------|-----------|--------|
| `CUTCTX_ALLOW_PRIVATE_UPSTREAM` | **HIGH** | **Relaxes the SSRF boundary.** Normally the proxy refuses to forward to private/link-local/loopback addresses; setting this permits them, so a crafted upstream target can reach internal services (cloud metadata endpoints, internal admin panels) from the proxy's network position. Leave unset unless you deliberately run an upstream on a private address. |
| `CUTCTX_ADMIN_API_KEY` | **CRITICAL** | Gates `/dashboard`, `/stats`, `/stats-reset` and the admin routes. A non-loopback deployment must set this (or configure full SSO via `CUTCTX_SSO_ENABLED` + JWKS/issuer/audience) — the deployment-security check reports `admin_auth_required` otherwise. See `cutctx/proxy/deployment_security.py`. |
| `CUTCTX_PROXY_API_KEY` | **CRITICAL** | Credential clients must present (`X-Cutctx-Proxy-Key`) to use provider passthrough. When unset on a non-loopback host, provider routes reject every request with `ProxyClientAuthError` rather than serving unauthenticated LLM calls — verified: `POST /v1/messages` returns 401. See `cutctx/proxy/client_auth.py`. |
| `CUTCTX_AUDIT_SECRET_KEY` | **CRITICAL** | HMAC secret for the tamper-evident audit chain. If unset or rotated carelessly, audit-log integrity cannot be proven. |
| `CUTCTX_LICENSE_KEY` | **CRITICAL** | Enterprise license key. Treat as a secret; do not commit. |
| `CUTCTX_LICENSE_HMAC_SECRET` | **CRITICAL** | HMAC secret used in license verification (enterprise). |
| `CUTCTX_ALLOW_DEV_AUDIT_KEY` | **HIGH** | Permits a weak development-mode audit key instead of a real secret. Never set in production — it defeats audit-chain tamper evidence. |
| `CUTCTX_ALLOW_ROLE_HEADER` | **HIGH** | Lets callers assert their RBAC role via a request header. Only safe when a trusted upstream sets that header and strips client-supplied copies. |
| `CUTCTX_ALLOW_DEBUG` | **HIGH** | Allows execution under an attached debugger (dev-only). |
| `CUTCTX_CORS_ORIGINS` | **MEDIUM** | Allowed browser origins. `*` disables credentialed CORS; a permissive list exposes admin surfaces to hostile pages. |
| `CUTCTX_SKIP_UPSTREAM_CHECK` | **MEDIUM** | Skips the startup upstream connectivity check, so a misconfigured upstream is not caught until request time. |
| `CUTCTX_FIREWALL_ENABLED` | **MEDIUM** | Enables prompt-injection, jailbreak, and PII detection. Off by default — turning it on is a security improvement, not a risk. |

### Cost-sensitive variables

Misconfiguring these changes spend, not security.

| Variable | Impact |
|----------|--------|
| `CUTCTX_BUDGET_HARD_LIMIT` | Enforces a hard spend ceiling. Unset means no ceiling. |
| `CUTCTX_BUDGET_USD` / `CUTCTX_BUDGET_TOKENS` | Cost and token limits across requests. |
| `CUTCTX_COMPRESSION_MODE` | `off` is byte-preserving, `safe` is conservative, `aggressive` compresses harder — affects both spend and fidelity. |

### Authentication

| Variable | Default | Description |
|----------|---------|-------------|
| `CUTCTX_ADMIN_API_KEY` | unset | Gates /dashboard, /stats, /stats-reset endpoints |
| `CUTCTX_API_KEY` | unset | API key for accessing Cutctx Cloud API |
| `CUTCTX_API_URL` | `https://api.cutctx.com` | Base URL for Cutctx Cloud API |
| `CUTCTX_CLIENT_API_KEY` | unset | Client API key for proxied requests |
| `CUTCTX_PROXY_API_KEY` | unset | Dedicated credential for provider-facing proxy traffic |

### Budget & Spend Control

| Variable | Default | Description |
|----------|---------|-------------|
| `CUTCTX_BUDGET_ENABLED` | `0` | Enable budget enforcement |
| `CUTCTX_BUDGET_GREEN` | unset | Green budget threshold (safe) |
| `CUTCTX_BUDGET_HARD_LIMIT` | `1` | Hard spend limit enforcement |
| `CUTCTX_BUDGET_RED` | unset | Red budget threshold (critical) |
| `CUTCTX_BUDGET_TOKENS` | unset | Token budget limit |
| `CUTCTX_BUDGET_USD` | unset | USD budget limit |
| `CUTCTX_BUDGET_YELLOW` | unset | Yellow budget threshold (warning) |

### Compression & Algorithms

| Variable | Default | Description |
|----------|---------|-------------|
| `CUTCTX_CCR_BACKEND` | `sqlite` | Backend for compression store (sqlite, redis) |
| `CUTCTX_COMPRESSION_MODE` | unset | Compression algorithm selection |
| `CUTCTX_COMPRESS_WORKERS` | unset | Number of parallel compression workers |
| `CUTCTX_ENABLE_KOMPRESS` | `0` | Enable ML-based text compression (Kompress) |
| `CUTCTX_HOSTED_COMPRESSION_ENABLED` | `0` | Enable hosted compression API endpoint |

### Core Proxy

| Variable | Default | Description |
|----------|---------|-------------|
| `CUTCTX_BACKEND` | unset | Backend implementation selection |
| `CUTCTX_MODE` | `optimize` | Operating mode: audit, optimize, or simulate |
| `CUTCTX_OFFLINE_MODE` | `0` | Run without external network access (air-gap mode) |
| `CUTCTX_PROVIDER` | `anthropic` | Default upstream provider (anthropic, openai, google, bedrock) |

### Identity & SSO

| Variable | Default | Description |
|----------|---------|-------------|
| `CUTCTX_SSO_AUDIENCE` | unset | OIDC audience identifier |
| `CUTCTX_SSO_DISCOVERY_URL` | unset | OIDC discovery URL |
| `CUTCTX_SSO_ENABLED` | `0` | Enable OIDC/SSO authentication |
| `CUTCTX_SSO_ISSUER` | unset | OIDC issuer URL |
| `CUTCTX_SSO_JWKS_URI` | unset | OIDC JWKS endpoint for key retrieval |
| `CUTCTX_SSO_PROVIDER_TYPE` | `oidc` | SSO provider type (oidc or okta) |

### Licensing & Entitlements

| Variable | Default | Description |
|----------|---------|-------------|
| `CUTCTX_ENTITLEMENT_TIER` | unset | Entitlement tier (builder, team, business, enterprise) |
| `CUTCTX_LICENSE_HMAC_SECRET` | unset | HMAC secret for offline license validation |
| `CUTCTX_LICENSE_KEY` | unset | Enterprise license key |
| `CUTCTX_LICENSE_KID` | unset | License key ID (Ed25519) |
| `CUTCTX_LICENSE_PRIVATE_KEY` | unset | License signing private key (Ed25519) |
| `CUTCTX_LICENSE_PUBLIC_KEY` | unset | License validation public key (Ed25519) |
| `CUTCTX_LICENSE_PUBLIC_KEYS` | unset | Comma-separated public keys for license validation |

### Memory & Storage

| Variable | Default | Description |
|----------|---------|-------------|
| `CUTCTX_AUDIT_DB_PATH` | `~/.cutctx/audit.db` | Path to audit log database |
| `CUTCTX_AUDIT_SECRET_KEY` | unset | HMAC secret for tamper-evident audit chain |
| `CUTCTX_FLEET_DB_PATH` | unset | Path to fleet tracking database |
| `CUTCTX_ORG_DB_PATH` | unset | Path to organization database (EE) |
| `CUTCTX_RBAC_DB_PATH` | unset | Path to RBAC assignments database (EE) |
| `CUTCTX_REDIS_URL` | unset | Redis connection URL |
| `CUTCTX_SCIM_DB_PATH` | unset | Path to SCIM identity database (EE) |

### Model Routing & Selection

| Variable | Default | Description |
|----------|---------|-------------|
| `CUTCTX_MODEL_LIMITS` | unset | Custom model configuration (JSON or file path) |
| `CUTCTX_MODEL_ROUTING` | unset | Per-model routing policy (JSON config) |
| `CUTCTX_MODEL_ROUTING_PRESET` | unset | Named preset for model routing behavior |
| `CUTCTX_MODEL_ROUTING_SCORER_ARTIFACT` | unset | Path to model routing scorer artifact |

### Observability & Monitoring

| Variable | Default | Description |
|----------|---------|-------------|
| `CUTCTX_LANGFUSE_ENABLED` | `0` | Enable Langfuse tracing integration |
| `CUTCTX_LOG_FORMAT` | `text` | Log format (text or json) |
| `CUTCTX_LOG_MESSAGES` | `0` | Log full request/response messages (PII risk — dev only) |
| `CUTCTX_OTEL_METRICS_ENABLED` | `0` | Enable OpenTelemetry metrics export |
| `CUTCTX_SENTRY_DSN` | unset | Sentry-compatible DSN for error tracking. **Nothing is transmitted unless this is set** and the `sentry` extra is installed (`pip install 'cutctx-ai[sentry]'`); otherwise error tracking is a no-op. Request bodies, cookies, credential headers, and stack-frame locals are scrubbed before send — compressed payloads are customer code and prompts. Read at `cutctx/observability/error_tracking.py`. |
| `CUTCTX_SENTRY_ENVIRONMENT` | falls back to `CUTCTX_DEPLOYMENT_PROFILE`, then `unknown` | Environment label for grouping errors |
| `CUTCTX_SENTRY_TRACES_SAMPLE_RATE` | `0` | Performance-trace sample rate, clamped to 0–1. Defaults to 0 (errors only) — tracing every request on a latency-sensitive proxy should be a deliberate choice. |
| `CUTCTX_TELEMETRY` | `1` | Enable telemetry beacon |
| `CUTCTX_TELEMETRY_DISABLED` | unset | Disable telemetry (alternative flag) |

### Other

| Variable | Default | Description |
|----------|---------|-------------|
| `CUTCTX_ACCURACY_GUARD` | unset | `strict\|balanced\|off`. Enforces log-severity fidelity for log-shaped payloads (pytest, npm, cargo, jest, make, generic). `off` (default): no checking. `balanced`: check, log WARNING on violation, forward compressed payload. `strict`: check, forward ORIGINAL payload on violation (fail-safe), log WARNING. Scope: log compression only; no overhead for other content types. |
| `CUTCTX_ADMIN_AUTH_FAILURES_PER_MINUTE` | `10` |  |
| `CUTCTX_AGENT_TYPE` | unset |  |
| `CUTCTX_ANYLLM_PROVIDER` | unset |  |
| `CUTCTX_AUTO_START` | unset |  |
| `CUTCTX_BILLING_STRICT_MODE` | `1` |  |
| `CUTCTX_BINARIES_CACHE` | unset |  |
| `CUTCTX_BINARIES_MIRROR` | unset |  |
| `CUTCTX_BINARIES_OFFLINE` | unset |  |
| `CUTCTX_BUDGET_WINDOW_RED` | unset |  |
| `CUTCTX_BUDGET_WINDOW_YELLOW` | unset |  |
| `CUTCTX_CBM_SHA256` | unset |  |
| `CUTCTX_CCR_TENANT_PREFIX` | unset |  |
| `CUTCTX_CLI_PATH` | unset |  |
| `CUTCTX_CODEX_WIRE_DEBUG` | unset |  |
| `CUTCTX_CODEX_WIRE_DEBUG_DIR` | unset |  |
| `CUTCTX_CODE_AWARE_ENABLED` | unset |  |
| `CUTCTX_COMPRESSION_STABLE_AFTER_TURN` | unset |  |
| `CUTCTX_CONTEXT_POLICY` | unset |  |
| `CUTCTX_CONTEXT_TOOL_STATS_TTL_SECONDS` | unset |  |
| `CUTCTX_CORS_ORIGINS` | unset |  |
| `CUTCTX_DEPLOYMENT_PRESET` | unset |  |
| `CUTCTX_DEPLOYMENT_PROFILE` | unset |  |
| `CUTCTX_DEPLOYMENT_RUNTIME` | unset |  |
| `CUTCTX_DEPLOYMENT_SCOPE` | unset |  |
| `CUTCTX_DEPLOYMENT_SUPERVISOR` | unset |  |
| `CUTCTX_DEV_ALLOW_INSECURE_WEBHOOK_HTTP` | unset |  |
| `CUTCTX_DIFFTASTIC_BINARY` | unset |  |
| `CUTCTX_DIFFTASTIC_CONTEXT_LINES` | unset |  |
| `CUTCTX_EGRESS_POLICY` | unset |  |
| `CUTCTX_EMBEDDER_RUNTIME` | unset |  |
| `CUTCTX_EMBEDDING_SERVER_SOCKET` | unset |  |
| `CUTCTX_ENSEMBLE_ENABLED` | unset |  |
| `CUTCTX_ENSEMBLE_REQUIRE_ALL` | unset |  |
| `CUTCTX_ENSEMBLE_TIMEOUT` | unset |  |
| `CUTCTX_EPISODES_DB` | unset |  |
| `CUTCTX_EPISODIC_MEMORY_DIR` | unset |  |
| `CUTCTX_EXCLUDE_TOOLS` | unset |  |
| `CUTCTX_EXPERIMENTAL` | unset |  |
| `CUTCTX_FIREWALL_BUFFER_TIMEOUT_MS` | unset |  |
| `CUTCTX_FIREWALL_MAX_BUFFER_TOKENS` | unset |  |
| `CUTCTX_FIREWALL_NO_REDACT_STREAMING` | `0` |  |
| `CUTCTX_FIREWALL_REDACT_STREAMING` | unset |  |
| `CUTCTX_HOSTED_API_KEY` | unset |  |
| `CUTCTX_HOSTED_BASE_URL` | unset |  |
| `CUTCTX_INTERCEPT_ENABLED` | unset |  |
| `CUTCTX_INTERCEPT_READ_MIN_CHARS` | unset |  |
| `CUTCTX_LANGFUSE_RESOURCE_ATTRIBUTES` | unset |  |
| `CUTCTX_LEAN_CTX_SHA256` | unset |  |
| `CUTCTX_LEAN_CTX_TARGET` | unset |  |
| `CUTCTX_LEARN_CLI` | unset |  |
| `CUTCTX_LEARN_SHARE` | unset |  |
| `CUTCTX_LICENSE_API_URL` | unset |  |
| `CUTCTX_LICENSE_SERVICE_API_KEY` | unset |  |
| `CUTCTX_LICENSE_STRICT_MODE` | unset |  |
| `CUTCTX_LOG_FILE` | unset |  |
| `CUTCTX_MANIFEST_PATH` | unset |  |
| `CUTCTX_MARKETPLACE_SOURCE` | unset |  |
| `CUTCTX_MAX_BODY_MB` | unset |  |
| `CUTCTX_MCP_READ` | `off` |  |
| `CUTCTX_MEMORY_DB_PATH` | `~/.cutctx/memory.db` |  |
| `CUTCTX_MFA_ENFORCE` | unset |  |
| `CUTCTX_ORCHESTRATION_AUDIT_KEY` | unset |  |
| `CUTCTX_ORCHESTRATION_CONFIG` | unset |  |
| `CUTCTX_ORCHESTRATION_DIR` | unset |  |
| `CUTCTX_ORCHESTRATION_DIRECT_EXECUTION` | unset |  |
| `CUTCTX_ORCHESTRATION_MASTER_KEY` | unset |  |
| `CUTCTX_ORCHESTRATION_REDIS_URL` | unset |  |
| `CUTCTX_OTEL_METRICS_ENDPOINT` | unset |  |
| `CUTCTX_OTEL_METRICS_EXPORTER` | unset |  |
| `CUTCTX_OTEL_METRICS_EXPORT_INTERVAL_MS` | unset |  |
| `CUTCTX_OTEL_METRICS_HEADERS` | unset |  |
| `CUTCTX_OTEL_RESOURCE_ATTRIBUTES` | unset |  |
| `CUTCTX_OTEL_SERVICE_NAME` | unset |  |
| `CUTCTX_POLICY_KID` | unset |  |
| `CUTCTX_POLICY_PRIVATE_KEY` | unset |  |
| `CUTCTX_POLICY_PUBLIC_KEYS` | unset |  |
| `CUTCTX_PREFIX_TRACKER_DB_PATH` | unset |  |
| `CUTCTX_PROXY_PORT` | `8787` |  |
| `CUTCTX_PROXY_URL` | `http://127.0.0.1:8787` |  |
| `CUTCTX_QDRANT_API_KEY` | unset |  |
| `CUTCTX_QDRANT_URL` | unset |  |
| `CUTCTX_RATE_LIMIT_ENABLED` | unset |  |
| `CUTCTX_REGION` | unset |  |
| `CUTCTX_REPLAY` | unset |  |
| `CUTCTX_REPLAY_DB_PATH` | unset |  |
| `CUTCTX_REPLAY_RETENTION_DAYS` | unset |  |
| `CUTCTX_RESPONSES_ML_TOOL_OUTPUT_MAX_BYTES` | `4096` |  |
| `CUTCTX_RTK_SHA256` | unset |  |
| `CUTCTX_RTK_TARGET` | unset |  |
| `CUTCTX_SAFE_SAVINGS_EXPERIENCE` | unset |  |
| `CUTCTX_SAVINGS_CANARY_ALLOW_NON_STICKY` | `0` |  |
| `CUTCTX_SAVINGS_CANARY_ENABLED` | `0` |  |
| `CUTCTX_SAVINGS_CANARY_EVALUATOR` | unset |  |
| `CUTCTX_SAVINGS_CANARY_EVAL_ARM` | unset |  |
| `CUTCTX_SAVINGS_CANARY_EVAL_RUN_ID` | unset |  |
| `CUTCTX_SAVINGS_CANARY_FEEDBACK_URL` | unset |  |
| `CUTCTX_SAVINGS_CANARY_MIN_SAMPLES` | `100` |  |
| `CUTCTX_SAVINGS_CANARY_PERCENT` | `10` |  |
| `CUTCTX_SAVINGS_CANARY_REGRESSION_LIMIT` | `0.01` |  |
| `CUTCTX_SAVINGS_CANARY_SALT` | unset |  |
| `CUTCTX_SAVINGS_PROFILE` | unset |  |
| `CUTCTX_SDK` | unset |  |
| `CUTCTX_SECRETS_KEY` | unset |  |
| `CUTCTX_SENTENCE_TRANSFORMER` | unset |  |
| `CUTCTX_SHADOW_MODE` | unset |  |
| `CUTCTX_SHADOW_SAMPLE_RATE` | unset |  |
| `CUTCTX_SIGLIP` | unset |  |
| `CUTCTX_SKIP_UPSTREAM_CHECK` | unset |  |
| `CUTCTX_SPACY` | unset |  |
| `CUTCTX_SPEND_DB_URL` | unset |  |
| `CUTCTX_SSO_CLOCK_SKEW_TOLERANCE` | unset |  |
| `CUTCTX_SSO_DEFAULT_ROLE` | `viewer` |  |
| `CUTCTX_SSO_HTTP_TIMEOUT` | unset |  |
| `CUTCTX_SSO_INTROSPECTION_CLIENT_ID` | unset |  |
| `CUTCTX_SSO_INTROSPECTION_CLIENT_SECRET` | unset |  |
| `CUTCTX_SSO_INTROSPECTION_URL` | unset |  |
| `CUTCTX_SSO_JWKS_CACHE_TTL` | unset |  |
| `CUTCTX_SSO_REQUIRED_SCOPES` | unset |  |
| `CUTCTX_SSO_ROLE_MAPPING` | unset |  |
| `CUTCTX_STACK` | unset |  |
| `CUTCTX_STAGED_DASHBOARD_URL` | unset |  |
| `CUTCTX_STAGED_PROXY_ADMIN_API_KEY` | unset |  |
| `CUTCTX_STAGED_PROXY_BASE_URL` | unset |  |
| `CUTCTX_STAGED_SCENARIO_FILE` | unset |  |
| `CUTCTX_STALE_READ_COMPRESS_AFTER_TURNS` | unset |  |
| `CUTCTX_STATELESS` | unset |  |
| `CUTCTX_STRUCTURED_OUTPUT_ENABLED` | unset |  |
| `CUTCTX_STRUCTURED_OUTPUT_MAX_RETRIES` | unset |  |
| `CUTCTX_STRUCTURED_OUTPUT_STRICT` | unset |  |
| `CUTCTX_SYNC_VERSIONS` | unset |  |
| `CUTCTX_TELEMETRY_EGRESS` | unset |  |
| `CUTCTX_TELEMETRY_WARN` | unset |  |
| `CUTCTX_TEST_REDIS_URL` | unset |  |
| `CUTCTX_TOIN_BACKEND` | unset |  |
| `CUTCTX_TOIN_TENANT_PREFIX` | unset |  |
| `CUTCTX_TOIN_URL` | unset |  |
| `CUTCTX_TOOL_PROFILES` | unset |  |
| `CUTCTX_UPSTREAM_ANTHROPIC_API_KEY` | unset |  |
| `CUTCTX_UPSTREAM_BEDROCK_API_KEY` | unset |  |
| `CUTCTX_UPSTREAM_GOOGLE_API_KEY` | unset |  |
| `CUTCTX_UPSTREAM_OPENAI_API_KEY` | unset |  |
| `CUTCTX_USER_ID` | unset |  |
| `CUTCTX_USER_TOKEN_HMAC_SECRET` | unset |  |
| `CUTCTX_WEBHOOKS_IN_MEMORY` | unset |  |
| `CUTCTX_WEBHOOK_SECRET` | unset |  |
| `CUTCTX_WEBHOOK_URL` | unset |  |

### Security & Governance

| Variable | Default | Description |
|----------|---------|-------------|
| `CUTCTX_ALLOW_DEBUG` | `0` | Allow execution under debugger attachment (dev-only) |
| `CUTCTX_ALLOW_PRIVATE_UPSTREAM` | `0` | Relaxes SSRF boundary — allow connections to private IP ranges |
| `CUTCTX_ALLOW_ROLE_HEADER` | `0` | Allow role information to be passed via headers |
| `CUTCTX_FIREWALL_BLOCK_INJECTION` | `1` | Block prompt injection attempts |
| `CUTCTX_FIREWALL_BLOCK_JAILBREAK` | `1` | Block jailbreak attempts |
| `CUTCTX_FIREWALL_BLOCK_PII` | `1` | Block PII detection |
| `CUTCTX_FIREWALL_ENABLED` | `0` | Enable prompt-injection and PII firewall |
