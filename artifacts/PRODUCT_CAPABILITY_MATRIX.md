# Cutctx — Corrected Product Capability & Gap Analysis

**Corrected after deep codebase audit. Previous analysis had stale claims about CLI, dashboard, and MCP.**

---

## WHAT ACTUALLY EXISTS

### 1. CLI (`cutctx` — Python Click CLI via `pyproject.toml`)

Entry point: `cutctx = "cutctx.cli:main"` (Python Click, 13 subcommand groups)

| Command | Module | Lines | What It Does |
|---------|--------|-------|-------------|
| `cutctx proxy` | `cli/proxy.py` | 1,118 | Start proxy server with full config |
| `cutctx wrap <agent>` | `cli/wrap.py` | 4,315 | Wrap claude/copilot/codex/aider/cursor/openclaw through proxy |
| `cutctx memory list/stats/search/add/update/delete/import/export` | `cli/memory.py` | 895 | Full memory management (optional: numpy/hnswlib) |
| `cutctx savings report/timeline/export/open` | `cli/savings.py` | 595 | Token savings reporting + analytics |
| `cutctx billing checkout/portal` | `cli/billing.py` | 120 | Open checkout/portal in browser |
| `cutctx license activate/status/upgrade` | `cli/license.py` | 434 | License key management |
| `cutctx evals memory/memory-v2` | `cli/evals.py` | 697 | Run LoCoMo memory evaluations |
| `cutctx install/uninstall/status` | `cli/install.py` | 333 | Persistent install + runtime management |
| `cutctx init` | `cli/init.py` | 943 | Durable agent initialization |
| `cutctx tools install/doctor/list` | `cli/tools.py` | 238 | Bundled tools (ast-grep, difftastic, scc) |
| `cutctx agent-savings` | `cli/agent_savings.py` | 230 | Agent token-savings profiles |
| `cutctx capture network-diff` | `cli/capture.py` | 81 | Network capture + differential reports |
| `cutctx learn` | `cli/learn.py` | 263 | Offline failure learning |
| `cutctx mcp serve/install/status` | `cli/mcp.py` | ~200 | MCP server management |

**Total CLI: ~10,000+ lines across 14 subcommand groups.**

### 2. Dashboard (`GET /dashboard` — 2,273-line HTML template)

- Real-time monitoring with Tailwind CSS + htmx + Alpine.js
- Token savings overview, compression ratios, cost tracking
- Transformation feed (live compression log)
- Dark/light theme toggle
- HTMX-powered auto-refresh

### 3. MCP Server (`cutctx/mcp_server.py` — 253 lines)

3 tools exposed:
- `cutctx_retrieve` — retrieve original content from CCR markers (with BM25 query filtering)
- `cutctx_status` — check proxy health + compression stats
- `cutctx_proxy_start` — auto-start proxy if not running

### 4. MCP Registry (`cutctx/mcp_registry/` — 8 files)

- `ClaudeRegistrar` — registers MCP in `~/.claude.json`
- `CodexRegistrar` — registers MCP in Codex TOML config
- `install_everywhere()` — auto-detect + register across all agents
- `ServerSpec` — universal server description

### 5. Proxy Routes (80+ endpoints)

**server.py (11 routes):**
- `/livez`, `/readyz`, `/health` — health probes
- `/debug/tasks`, `/debug/ws-sessions`, `/debug/warmup` — debug (loopback only)
- `/dashboard` — monitoring UI
- `/stats`, `/stats/reset`, `/stats-history`, `/transformations/feed` — stats

**routes/admin.py (69 routes):**
- `/entitlements` — feature gating status
- `/audit/events`, `/audit/export` — audit log query + export
- `/orgs` CRUD, `/orgs/{id}/workspaces`, `/workspaces/{id}/projects` — org model
- `/license-status` — license info
- `/reports/savings`, `/reports/usage` — CSV/JSON reports
- `/retention/stats`, `/retention/cleanup` — data retention
- `/rbac/roles` CRUD — role-based access
- `/fleet/*` — fleet management
- `/scim/v2/*` — SCIM provisioning (14 endpoints)
- `/firewall/status`, `/firewall/scan` — LLM firewall
- `/structured-output/status`, `/structured-output/validate` — structured output
- `/ensemble/status`, `/budget/status` — ensemble + budget
- `/intelligence/*/status` (6 endpoints) — intelligence layer
- `/subscription-window`, `/quota`, `/metrics` — subscription + metrics
- `/cache/clear` — cache management
- `/v1/retrieve/*`, `/v1/feedback/*`, `/v1/telemetry/*`, `/v1/toin/*` — data APIs
- `/v1/compress` — direct compression
- `/analytics/dashboard`, `/analytics/projects` — analytics

**Rust proxy routes:**
- `/healthz`, `/healthz/upstream` — health
- `/metrics` — Prometheus
- `/v1/chat/completions`, `/v1/responses` — OpenAI endpoints
- `/v1/messages` — Anthropic endpoint (catch-all)
- `/v1beta1/projects/:p/locations/:l/publishers/anthropic/models/:m` — Vertex
- `/model/:id/invoke`, `/model/:id/converse`, `/model/:id/invoke-with-response-stream` — Bedrock
- `/v1/conversations/*` — Conversations API passthrough

### 6. Python Proxy CLI Args (61 flags)

Core: `--host`, `--port`, `--backend`, `--workers`, `--limit-concurrency`
Providers: `--openai-api-url`, `--anthropic-api-url`, `--vertex-api-url`, `--bedrock-region`, `--bedrock-profile`, `--openrouter-api-key`, `--anyllm-provider`
Compression: `--no-optimize`, `--min-tokens`, `--max-items`, `--tool-profile`, `--compress-user-messages`, `--disable-kompress`, `--exclude-tools`, `--code-aware`
Cache: `--no-cache`, `--cache-ttl`
Security: `--admin-api-key`, `--cors-origins`, `--max-body-mb`
Enterprise: `--entitlement-tier`, `--audit-db-path`, `--no-audit`, `--org-db-path`, `--no-org`, `--fleet-db-path`, `--no-fleet`, `--scim-db-path`, `--no-scim`
SSO: `--sso-provider-type`, `--sso-discovery-url`, `--sso-jwks-uri`, `--sso-issuer`, `--sso-audience`, `--sso-introspection-url`, `--sso-role-mapping`, `--sso-default-role`
Features: `--firewall`, `--no-structured-output`, `--ensemble`, `--budget-cut-off`, `--budget-default-tokens`
Intelligence: `--task-aware`, `--dedup`, `--context-budget`, `--context-budget-max-tokens`, `--context-budget-policy`, `--profiles`, `--shared-context`, `--cost-forecast`
Rate limiting: `--no-rate-limit`, `--rpm`, `--tpm`
Cost: `--budget`, `--budget-period`
Connection: `--max-connections`, `--max-keepalive`, `--no-http2`
Logging: `--log-file`, `--log-messages`

### 7. SDKs

- **Go SDK** (`sdk/go/`): Client with Compress, Retrieve, Stats methods
- **TypeScript SDK** (`sdk/typescript/`): client.ts, compress.ts, hooks.ts, shared-context.ts, adapters/

### 8. Plugins

- `plugins/claude-code/` — Claude Code MCP integration
- `plugins/codex/` — Codex plugin
- `plugins/cutctx-plugin/` — Claude.ai web plugin
- `plugins/cutctx-agent-hooks/` — Agent hooks
- `plugins/cutctx-oauth2/` — OAuth2 client-credentials
- `plugins/hermes/` — Hermes integration
- `plugins/openclaw/` — OpenClaw integration

### 9. Deployment

- Docker (multi-stage, distroless)
- Docker Compose
- Kubernetes (9 manifests)
- Helm chart (12 files)

---

## ACTUAL GAPS (corrected)

### 🔴 CRITICAL — Buyer can't complete core workflows without help

| # | Gap | What exists | What's missing | Impact |
|---|-----|-------------|---------------|--------|
| 1 | **No unified "install + verify" flow** | `cutctx init`, `cutctx wrap`, `cutctx install` exist but are scattered | No single `cutctx setup` that does: install → detect agents → register MCP → start proxy → verify savings | Buyer needs founder help to get started |
| 2 | **Dashboard doesn't show enterprise admin state** | Dashboard shows compression stats | No RBAC viewer, no org management, no audit log viewer, no SSO status, no retention config, no fleet view | Enterprise buyer can't see governance controls |
| 3 | **No ROI proof path** | `cutctx savings report` exists, `/reports/savings` API exists | No end-to-end "install → use for 7 days → show savings report" workflow documented or automated | Buyer can't prove value before paying |
| 4 | **MCP server is thin** | 3 tools (retrieve, status, proxy_start) | No `cutctx_compress` (the memo claims it exists but it doesn't), no `cutctx_scan` (firewall), no admin tools | Claude Code users can't access most features via MCP |
| 5 | **No pricing page or activation flow** | `cutctx billing checkout` opens browser, `cutctx license activate` exists | No in-product pricing comparison, no tier selection, no trial-to-paid conversion flow | Buyer doesn't know what to pay for |

### 🟡 HIGH — Enterprise workflows are API-first only

| # | Gap | What exists | What's missing |
|---|-----|-------------|---------------|
| 6 | **RBAC has no UI** | API: `/rbac/roles` GET/POST/DELETE | No dashboard view, no CLI command, no visual role assignment |
| 7 | **Org management has no UI** | API: `/orgs` CRUD | No dashboard view, no CLI command (`cutctx orgs list`) |
| 8 | **Audit logs have no UI** | API: `/audit/events`, `/audit/export` | No dashboard viewer, no CLI command (`cutctx audit list`) |
| 9 | **SSO config has no validation** | 8 CLI flags + env vars | No `cutctx sso test` to validate config before startup |
| 10 | **Fleet management has no UI** | API: `/fleet/*` | No dashboard view, no CLI command |
| 11 | **SCIM has no setup wizard** | API: `/scim/v2/*` (14 endpoints) | No IdP integration guide, no test tool |
| 12 | **Retention has no UI** | API: `/retention/stats`, `/retention/cleanup` | No dashboard config, no CLI command |
| 13 | **Reports have no scheduled export** | API: `/reports/savings`, `/reports/usage` (CSV/JSON) | No cron/scheduled reports, no email delivery |
| 14 | **Analytics has no dashboard** | API: `/analytics/dashboard`, `/analytics/projects` | No visual analytics page |
| 15 | **Subscription/quota has no UI** | API: `/subscription-window`, `/quota` | No dashboard view |

### 🟢 MEDIUM — Polish and completeness

| # | Gap | What exists | What's missing |
|---|-----|-------------|---------------|
| 16 | **Intelligence layer is invisible** | 6 features wired into pipeline, status endpoints exist | No dashboard showing dedup hits, budget zones, task relevance scores, cost forecasts |
| 17 | **Firewall has no scan history** | `/firewall/scan` endpoint | Results not stored, no history, no dashboard |
| 18 | **CCR has no content browser** | `/v1/retrieve` by hash | No browse/search UI, no stats on stored content |
| 19 | **No config validation** | 61 CLI flags | No `cutctx config check` to validate before starting |
| 20 | **No benchmark CLI** | Benchmarks in `benchmarks/` dir | No `cutctx bench` subcommand |
| 21 | **Go SDK missing shared-context** | TypeScript SDK has it | Go SDK doesn't expose shared-context |
| 22 | **No Python SDK** | Go + TypeScript SDKs exist | Python users must use proxy directly or CLI |
| 23 | **`docs/admin-dashboard.html` not served** | 400+ line admin dashboard HTML | Static file, not mounted on any route |

---

## CORRECTED SCORE

| Category | Features | CLI | API | Dashboard | Score |
|----------|----------|-----|-----|-----------|-------|
| Compression | 9 | 7/9 | 9/9 | 1/9 | 🟡 Good |
| CLI Tools | 14 groups | 14/14 | N/A | N/A | ✅ Strong |
| Intelligence | 6 | 6/6 | 6/6 | 0/6 | 🟡 |
| Security | 6 | 3/6 | 6/6 | 0/6 | 🟡 |
| Enterprise | 8 | 2/8 | 8/8 | 0/8 | 🔴 |
| Dashboard | 1 | N/A | N/A | 1/1 | ✅ Exists |
| MCP | 3 tools | 3/3 | N/A | N/A | 🟡 Thin |
| SDKs | 2 | N/A | N/A | N/A | 🟡 No Python |
| Deployment | 4 | N/A | N/A | N/A | ✅ Complete |
| **TOTAL** | **53** | **35/44** | **29/29** | **2/24** | **Enterprise UI is the gap** |

## BOTTOM LINE

**The CLI is actually strong** (14 subcommand groups, 10K+ lines). The **dashboard exists** and is functional. The **real gap is enterprise admin UI** — 29 API endpoints have no corresponding dashboard or CLI commands. The product works from the terminal but enterprise buyers need visual governance controls.

The memo's recommendation stands: **Add dashboard views for RBAC, orgs, audit, analytics, and retention.** That's the commercialization blocker, not missing functionality.
