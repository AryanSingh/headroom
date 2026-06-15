# CutCtx Product Capability Matrix

Full inventory of every feature, how it's accessed, and gaps.

---

## 1. COMPRESSION ALGORITHMS (8 algorithms)

| Algorithm | Module | How to Access | CLI | API | Dashboard | Pipeline | Gap |
|-----------|--------|--------------|-----|-----|-----------|----------|-----|
| SmartCrusher | `transforms/smart_crusher.py` | Auto (proxy) | ✅ Default | ✅ Auto | ✅ Stats | ✅ Wired | — |
| CodeCompressor | `transforms/code_compressor.py` | `--code-aware` flag | ✅ | ✅ | ✅ Stats | ✅ Wired | — |
| DiffCompressor | `transforms/diff_compressor.py` | Auto (proxy) | ✅ Default | ✅ Auto | ✅ Stats | ✅ Wired | — |
| LogCompressor | `transforms/log_compressor.py` | Auto (proxy) | ✅ Default | ✅ Auto | ✅ Stats | ✅ Wired | — |
| SearchCompressor | `transforms/search_compressor.py` | Auto (proxy) | ✅ Default | ✅ Auto | ✅ Stats | ✅ Wired | — |
| CacheAligner | `transforms/cache_aligner.py` | Auto (proxy) | ✅ Default | ✅ Auto | ✅ Stats | ✅ Wired | — |
| Kompress (ML) | `transforms/kompress_compressor.py` | Auto (proxy) | `--disable-kompress` to turn off | ✅ Auto | ✅ Stats | ✅ Wired | — |
| ImageCompressor | `transforms/image_compressor.py` | Auto (proxy) | N/A | ✅ Auto | ❌ No stats | ✅ Wired | No image-specific stats |
| AudioCompressor | `transforms/audio_compressor.py` | Auto (proxy) | N/A | ✅ Auto | ❌ No stats | ✅ Wired | No audio-specific stats |

## 2. INTELLIGENCE LAYER (6 features)

| Feature | Module | How to Access | CLI | API | Dashboard | Pipeline | Gap |
|---------|--------|--------------|-----|-----|-----------|----------|-----|
| Task-Aware Compression | `compression/task_aware.py` | `--task-aware` | ✅ | ✅ Status | ❌ | ✅ Wired | **No dashboard** |
| Semantic Dedup | `dedup.py` | `--dedup` | ✅ | ✅ Status | ❌ | ✅ Wired | **No dashboard** |
| Context Budget | `context_budget.py` | `--context-budget` | ✅ | ✅ Status | ❌ | ✅ Wired | **No dashboard** |
| Cross-Session Profiles | `profiles.py` | `--profiles` | ✅ | ✅ Status | ❌ | ✅ Wired | **No dashboard** |
| Multi-Agent Shared State | `shared_context.py` | `--shared-context` | ✅ | ✅ Status | ❌ | ✅ Wired | **No dashboard** |
| Cost Forecasting + Policy | `cost_forecast.py` | `--cost-forecast` | ✅ | ✅ Status | ❌ | ✅ Wired | **No dashboard** |

## 3. SECURITY & ACCESS CONTROL (6 features)

| Feature | Module | How to Access | CLI | API | Dashboard | Gap |
|---------|--------|--------------|-----|-----|-----------|-----|
| Admin Auth | `server.py` | `--admin-api-key` | ✅ | ✅ Auto-gen | ❌ | **No key rotation UI** |
| RBAC | `rbac.py` | `/rbac/roles` | N/A | ✅ REST | ❌ | **No dashboard** |
| SSO/OAuth2 | `sso.py` | `--sso-*` flags | ✅ | ✅ Config | ❌ | **No dashboard, no IdP test tool** |
| Audit Logging | `audit.py` | `/audit/events`, `/audit/export` | N/A | ✅ REST | ❌ | **No dashboard** |
| LLM Firewall | `security/firewall.py` | `--firewall` | ✅ | ✅ `/firewall/scan` | ❌ | **No dashboard, no scan history** |
| Entitlements | `entitlements.py` | `/entitlements` | `--entitlement-tier` | ✅ REST | ❌ | **No dashboard** |

## 4. ENTERPRISE FEATURES (8 features)

| Feature | Module | How to Access | CLI | API | Dashboard | Gap |
|---------|--------|--------------|-----|-----|-----------|-----|
| Org Model | `org.py` | `/orgs` CRUD | N/A | ✅ REST | ❌ | **No dashboard** |
| Fleet Management | `fleet.py` | `/fleet/*` | `--fleet-db-path` | ✅ REST | ❌ | **No dashboard** |
| SCIM Provisioning | `scim.py` | `/scim/v2/*` | `--scim-db-path` | ✅ SCIM v2 | ❌ | **No IdP integration wizard** |
| Retention Controls | `retention.py` | `/retention/*` | `--retention-*` | ✅ REST | ❌ | **No dashboard** |
| License Management | `usage_reporter.py` | `/license-status` | `--license-key` | ✅ REST | ❌ | **No license activation UI** |
| Reports | `server.py` | `/reports/*` | N/A | ✅ CSV/JSON | ❌ | **No dashboard** |
| Analytics | `server.py` | `/analytics/*` | N/A | ✅ REST | ❌ | **No dashboard** |
| Subscription/Quota | `subscription.py` | `/subscription-window`, `/quota` | N/A | ✅ REST | ❌ | **No dashboard** |

## 5. PRODUCT CAPABILITIES (4 features)

| Feature | Module | How to Access | CLI | API | Dashboard | Pipeline | Gap |
|---------|--------|--------------|-----|-----|-----------|----------|-----|
| Structured Output | `proxy/structured_output.py` | `--no-structured-output` | ✅ | ✅ `/structured-output/*` | ❌ | Status only | **Not auto-triggered by request** |
| Multi-Model Ensemble | `proxy/ensemble.py` | `--ensemble` + header | ✅ | ✅ `/ensemble/status` | ❌ | Header-triggered | **No dashboard** |
| Budget Cut-offs | `proxy/budget.py` | `--budget-cut-off` | ✅ | ✅ `/budget/status` | ❌ | ✅ Wired | **No dashboard** |
| CCR (Cache Compression) | `ccr/` | `--ccr-backend` | ✅ | ✅ `/v1/retrieve` | ❌ | ✅ Wired | **No retrieval dashboard** |

## 6. DEPLOYMENT & INTEGRATION (8 access points)

| Integration | Location | How to Install | Features Exposed | Gap |
|------------|----------|---------------|-----------------|-----|
| CLI Binary | `cutctx` (Rust) | `pip install headroom-ai` | proxy, compress, stats, retrieve | **Only 4 subcommands** |
| Python Proxy | `server.py` | `python -m headroom.proxy.server` | All 80+ routes | ✅ Complete |
| Rust Proxy | `headroom-proxy` binary | `cargo build --release` | Compression + CCR | ✅ Complete |
| MCP Server | `mcp_server.py` | `cutctx mcp serve` | 3 tools (retrieve, status, proxy_start) | **Only 3 tools** |
| Claude Code Plugin | `plugins/claude-code/` | `install.sh` | MCP integration | ✅ Complete |
| Codex Plugin | `plugins/codex/` | `install.sh` | MCP integration | ✅ Complete |
| Claude.ai Web Plugin | `plugins/cutctx-plugin/` | ZIP upload | Skill (compression commands) | **No auto-start, no tool** |
| Go SDK | `sdk/go/` | `go get` | Compress, Retrieve, Stats | ✅ Complete |
| TypeScript SDK | `sdk/typescript/` | `npm install` | Compress, hooks, shared-context | ✅ Complete |
| Docker | `Dockerfile` | `docker build` | Full proxy | ✅ Complete |
| Kubernetes | `k8s/` | `kubectl apply` | Full proxy + HPA + PDB | ✅ Complete |
| Helm | `helm/cutctx/` | `helm install` | Full proxy + all enterprise | ✅ Complete |

## 7. OBSERVABILITY (4 features)

| Feature | Module | How to Access | Gap |
|---------|--------|--------------|-----|
| Dashboard (HTML) | `dashboard/` | `GET /dashboard` | ✅ Exists — token savings, compression stats |
| Prometheus Metrics | `observability/` | `GET /metrics` | ✅ Exists — 20+ metrics |
| Stats API | `server.py` | `GET /stats` | ✅ Exists — request/token/cost breakdowns |
| Transformations Feed | `server.py` | `GET /transformations/feed` | ✅ Exists — live compression log |
| OTel Tracing | `observability/` | Env vars | ✅ Exists — Langfuse + OTel |
| Admin Dashboard UI | `docs/admin-dashboard.html` | Open in browser | **NOT SERVED — static file only** |

---

## ACCESS GAP ANALYSIS

### 🔴 CRITICAL GAPS (Features exist but have NO discoverable interface)

| # | Gap | Impact | Fix |
|---|-----|--------|-----|
| 1 | **No CLI subcommands** — `cutctx` binary only runs the proxy. No `cutctx compress`, `cutctx stats`, `cutctx orgs`, `cutctx audit`, etc. | Users can't use compression or management from terminal | Add subcommands to Rust CLI |
| 2 | **80+ API endpoints with NO UI** — Enterprise features (RBAC, audit, orgs, SSO, retention, fleet, SCIM, reports, analytics) are raw REST only | Enterprise admins can't use the product without writing scripts | Build admin dashboard or CLI |
| 3 | **Admin Dashboard HTML not served** — `docs/admin-dashboard.html` exists but is a static file, not mounted on the proxy | Nobody can access it | Mount on `/admin` route |
| 4 | **Intelligence layer has no dashboard** — 6 features (task-aware, dedup, budget, profiles, shared-context, cost-forecast) have status endpoints but no visual | Operators can't see intelligence layer activity | Add to dashboard |
| 5 | **MCP server only exposes 3 tools** — `headroom_retrieve`, `cutctx_status`, `cutctx_proxy_start`. Missing: compress, scan (firewall), validate (structured output), org management | Claude Code users can't access most features | Expand MCP tool set |

### 🟡 HIGH GAPS (Features exist but access is awkward)

| # | Gap | Impact | Fix |
|---|-----|--------|-----|
| 6 | **No `cutctx compress` CLI** — Compression only works through the proxy, not standalone | Can't compress files from terminal | Add compress subcommand |
| 7 | **No `cutctx stats` CLI** — Stats only via API | Can't check savings from terminal | Add stats subcommand |
| 8 | **No license activation flow** — `--license-key` flag exists but no interactive setup | Users don't know how to activate | Add `cutctx license activate` |
| 9 | **No RBAC role management UI** — Can assign roles via API but no visual | Admins can't see who has what access | Add to admin dashboard |
| 10 | **No SSO configuration wizard** — 9 env vars to set, no validation tool | Hard to set up SSO | Add `cutctx sso test` |
| 11 | **No firewall scan history** — Can scan but results aren't stored | Can't audit what was blocked | Add scan log |
| 12 | **No structured output auto-trigger** — Status endpoint exists but it's not wired into the request pipeline automatically | Feature is dormant unless manually configured | Wire into middleware |
| 13 | **No CCR retrieval dashboard** — Can retrieve by hash but can't browse stored content | Can't see what's in CCR store | Add retrieval browser |

### 🟢 MEDIUM GAPS (Nice to have)

| # | Gap | Impact | Fix |
|---|-----|--------|-----|
| 14 | **No `cutctx dashboard` CLI** — Can't open dashboard from terminal | Minor UX | Add subcommand |
| 15 | **No health check CLI** — Can't verify proxy is running from terminal | Minor UX | Add `cutctx status` |
| 16 | **No config validation** — Can't test config before starting proxy | Bad configs fail at runtime | Add `cutctx config check` |
| 17 | **No benchmark CLI** — Benchmarks exist in `benchmarks/` but no `cutctx bench` | Can't measure performance | Add subcommand |
| 18 | **Go SDK missing shared-context** — TypeScript SDK has it, Go doesn't | Incomplete parity | Add to Go SDK |
| 19 | **No Python SDK** — Only Go and TypeScript | Python users must use proxy directly | Add Python SDK |

---

## CLI SUBCOMMAND GAP (most critical)

Current `cutctx` binary (Rust) exposes:
```
cutctx          # runs the proxy (only command)
```

Users expect:
```
cutctx proxy              # start proxy (✅ exists as default)
cutctx compress < file    # compress from terminal
cutctx stats              # show compression stats
cutctx retrieve <hash>    # retrieve original from CCR
cutctx status             # check if proxy is running
cutctx dashboard          # open dashboard in browser
cutctx license activate   # activate license key
cutctx license status     # show license status
cutctx orgs list          # list organizations
cutctx orgs create <name> # create organization
cutctx audit --since 7d   # show audit logs
cutctx rbac list          # show role assignments
cutctx rbac assign <user> <role>  # assign role
cutctx sso test           # test SSO configuration
cutctx config check       # validate configuration
cutctx firewall scan <text>  # scan text for violations
cutctx bench              # run benchmarks
cutctx mcp serve          # start MCP server (Python)
```

---

## DASHBOARD GAP (second most critical)

Current dashboard (`GET /dashboard`):
- ✅ Token savings overview
- ✅ Compression ratio by strategy
- ✅ Request count over time
- ✅ Cost savings

Missing from dashboard:
- ❌ Intelligence layer activity (task-aware, dedup, budget)
- ❌ Audit log viewer
- ❌ RBAC role management
- ❌ Org/workspace/project management
- ❌ SSO configuration status
- ❌ Firewall scan history
- ❌ CCR content browser
- ❌ Fleet deployment status
- ❌ License activation
- ❌ Analytics (per-project, per-org)
- ❌ Report generation (CSV/JSON export)
- ❌ Retention policy configuration
- ❌ SCIM provisioning status
- ❌ Subscription/quota overview

---

## SUMMARY

| Category | Total Features | With CLI | With API | With Dashboard | Gap Score |
|----------|---------------|----------|----------|---------------|-----------|
| Compression | 9 | 7/9 | 9/9 | 1/9 | 🟡 |
| Intelligence | 6 | 6/6 | 6/6 | 0/6 | 🔴 |
| Security | 6 | 3/6 | 6/6 | 0/6 | 🔴 |
| Enterprise | 8 | 2/8 | 8/8 | 0/8 | 🔴 |
| Product | 4 | 3/4 | 4/4 | 0/4 | 🔴 |
| Deployment | 11 | 2/11 | N/A | N/A | 🟡 |
| Observability | 5 | 0/5 | 5/5 | 1/5 | 🟡 |
| **TOTAL** | **49** | **23/49** | **38/49** | **2/49** | **🔴** |

**Key finding:** 38 features have API endpoints but only 2 have dashboard UI, and only 23 have CLI access. The product is API-rich but interface-poor.
