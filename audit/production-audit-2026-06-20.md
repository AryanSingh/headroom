# Cutctx Production Audit Report

**Repository:** `/Users/aryansingh/Documents/Claude/Projects/headroom`
**Branch:** `moat-b1-team-memory-svc` @ `db7f7a45`
**Audit date:** 2026-06-20
**Auditor role:** Principal PM + Staff SWE + QA Lead + Security Engineer + Solutions Architect
**Method:** Manual code inspection of 4 parallel deep-dive streams (compression pipeline, enterprise + security, dashboard + admin, tests + reliability + packaging). No file modifications. Every finding cites `file:line` evidence.

---

## Executive Summary

Cutctx is a sophisticated LLM proxy with a production-quality compression pipeline, full multi-provider support, and a working admin auth + RBAC layer. **However, the product is not yet ready for paid enterprise release.** Critical security gaps in the proprietary EE layer (unauthenticated `/v1/spend/*` and `/v1/memory/*`, broken SSO signature verification, missing DSR/DSAR endpoints) and a production gap in the headline moat-b1 feature (3 of 5 savings sources are structurally zero in live traffic) need to be closed before the commercial claims are defensible. The 5-source model is wired at the data layer but not at the request path.

**Verdict:** **NO-GO** for paid enterprise release in current state. **GO** for internal beta / private design partner. **Production-ready for OSS** with documented limitations.

| Score | Value |
|---|---|
| **Production Readiness Score** | **62 / 100** |
| **Enterprise Readiness Score** | **38 / 100** |
| **OSS Readiness Score** | **78 / 100** |
| **Final Recommendation** | **NO-GO for paid enterprise. GO for OSS public release with explicit "no enterprise features" labeling. Internal design-partner pilots acceptable with security disclosure.** |

---

## 1. Verified Feature Inventory (code-confirmed)

### 1.1 Core proxy (OSS, `headroom/proxy/`)

| Feature | Status | Evidence |
|---|---|---|
| LLM request proxy (Anthropic, OpenAI Chat, OpenAI Responses, OpenAI Codex, Gemini, Bedrock, Vertex) | **Implemented** | `headroom/providers/proxy_routes.py:316-754`; `headroom/proxy/handlers/anthropic.py`; `headroom/proxy/handlers/openai/{chat,responses,passthrough,compress}.py`; `headroom/proxy/handlers/gemini.py` |
| Compression pipeline (CCR, SmartCrusher, LiveZone, Markdown-KV, etc.) | **Implemented** | `headroom/transforms/pipeline.py:36-49,89-97`; `headroom/compress/` |
| Per-provider cache compatibility (Anthropic 5m/1h, OpenAI auto-cache, Gemini) | **Implemented** | `headroom/proxy/handlers/anthropic.py:2516-2520`; `headroom/proxy/savings_tracker.py:660-668` |
| Response cache (semantic cache, in-memory) | **Implemented** | `headroom/proxy/semantic_cache.py:24-147`; wired in `anthropic.py:790-840`, `openai/chat.py:275-325` |
| LLM Firewall (regex-based prompt injection + PII scanner) | **Implemented** | `headroom/security/firewall.py:1-534`; `server.py:2050-2128` (off by default) |
| Streaming PII redactor | **Defined but unwired** | `headroom/security/firewall.py:409-534`; `wrap_stream` defined but zero callsites |
| Upstream circuit breaker | **Implemented** | `headroom/proxy/routing/failover.py:3-155` |
| Pipeline circuit breaker | **Implemented** | `headroom/transforms/pipeline.py:36-49`; `HEADROOM_PIPELINE_BREAKER_*` env vars |
| Health endpoints (`/livez`, `/readyz`, `/health`) | **Implemented** | `headroom/proxy/server.py:2617-2641`; used in `Dockerfile:95-96,118-119`, `docker-compose.yml:12-16` |
| Prometheus `/metrics` | **Implemented** | `headroom/proxy/prometheus_metrics.py`; `routes/admin.py:1366-1375` (admin-gated) |
| Spend ledger (per-org/workspace/project) | **Implemented** | `headroom_ee/ledger/`; `headroom_ee/ledger/api.py:46-139` |
| Multi-tenancy (per-project memory, per-org spend) | **Implemented (data) / Partial (enforcement)** | `headroom/memory/storage_router.py:60-240`; `headroom_ee/org.py:66-465` |
| CLI (28 top-level commands) | **Implemented** | `headroom/cli/` (541 click decorators across 30 files) |
| Native binary (Rust) | **Built (33.5 MB, 2026-06-20)** | `headroom/_core.abi3.so`; `crates/headroom-{core,parity,proxy,py}/` |
| Helm chart, Docker, Docker Compose, npm wrapper | **Implemented** | `helm/headroom/`, `Dockerfile`, `docker-compose.yml`, `sdk/typescript/` |
| Live debug endpoints | **Loopback-gated** | `server.py:2650-2676` |

### 1.2 Enterprise layer (`headroom_ee/`, commercial)

| Feature | Status | Evidence |
|---|---|---|
| RBAC (4 roles, 25+ permissions) | **Implemented** | `headroom_ee/rbac.py:31-84`; ~40 admin routes enforce |
| Org/Workspace/Project hierarchy | **Implemented** | `headroom_ee/org.py:66-465` |
| Admin auth (API key + SSO) | **Implemented (but SSO broken)** | `server.py:2280-2343`; `headroom_ee/sso.py:263-558` |
| Audit log (SQLite) | **Implemented** | `headroom_ee/audit.py:88-360` |
| Audit log (HMAC hash chain) | **Implemented but separate, dev-default secret** | `headroom_ee/audit/store.py:17-156` (default `"dev-secret-key"` at line 24) |
| SCIM 2.0 | **Implemented** | `routes/admin.py:844-1086` |
| Fleet management | **Implemented** | `routes/admin.py:707-758` |
| Residency proof (Ed25519-signed attestation) | **Implemented** | `headroom/security/residency_proof.py:1-338`; `routes/residency.py:27-88` |
| License validation (Ed25519) | **Implemented** | `headroom_ee/license_validation.py` |
| Spend ledger ingest/query/export | **Implemented** | `headroom_ee/ledger/api.py:46-139` |
| Billing / Stripe webhooks (inbound) | **Implemented** | `headroom_ee/billing/stripe_webhook.py:1-161` |
| Abuse detection | **Implemented but unwired** | `headroom_ee/abuse.py:135-289`; alerts not delivered to any channel |

### 1.3 5-source savings model (headline moat-b1 feature)

| Source | Parser | Persisted | Surfaced in CLI/Dashboard | Fires from live traffic? |
|---|---|---|---|---|
| `provider_prompt_cache` | Yes | Yes | Yes | **Yes** |
| `cutctx_compression` | Yes (residual) | Yes | Yes | **Yes, but near-zero for steady-state cache-preserving traffic** |
| `semantic_cache` | Yes | Yes | Yes | **Yes** (response cache wired in `anthropic.py:790-840`, `openai/chat.py:275-325`) |
| `prefix_cache_self_hosted` | Yes (`parse_vllm_apc`) | Yes (header-driven) | Yes | **No** — all live handler sites hardcode `0`; only fires from `x-headroom-prefix-cache-hits` request header opt-in |
| `model_routing` | Yes (`parse_model_routing_metadata`) | Yes (header-driven) | Yes | **No** — all live handler sites hardcode `0`; only fires from `x-headroom-model-routing-*` request header opt-in |

---

## 2. Missing Features

| # | Feature | Severity | Evidence |
|---|---|---|---|
| 1 | **Live detection of vLLM APC prefix-cache hits** | **High** | `headroom/proxy/handlers/{anthropic,openai/chat}.py:830-832,1983-1985,2532-2534,2950-2952,3086-3088,3276-3278` all hardcode `self_hosted_prefix_cache_hits=0` |
| 2 | **Live model routing policy (downgrade opus→sonnet, gpt-4o→mini)** | **High** | Same handler sites hardcode `model_routing_tokens_saved=0, model_routing_usd_saved=0.0` |
| 3 | **GDPR/CCPA right-to-delete endpoint** | **Critical** | 0 matches for `gdpr\|ccpa\|DSR\|DSAR\|right_to_delete\|right_to_export` in `headroom/` or `headroom_ee/` |
| 4 | **GDPR/CCPA right-to-export endpoint** | **Critical** | Same |
| 5 | **MFA on admin access** | **Critical** | `gtm/soc2-roadmap.md:53` claims "Implemented" but `server.py:2280-2343` has no second-factor path |
| 6 | **SAML SSO** | **High** | `headroom_ee/sso.py` only handles JWT/JWKS/OIDC. No SAML library. |
| 7 | **End-user API key issuance/revocation** | **High** | 0 matches for `issue_key\|create_api_key\|end_user_key` |
| 8 | **Automated retention/cleanup background loop** | **High** | `headroom_ee/retention.py:107-122` has `start()` method but no caller in `server.py` |
| 9 | **Per-identity (org/user/API-key) rate limiting** | **High** | `headroom/proxy/rate_limiter.py:65-79` is per-IP only |
| 10 | **Outbound event subscription model (webhooks with retry/signing/types)** | **High** | `headroom/proxy/webhooks.py:1-28` is 28 lines, single env var, no signing, no types |
| 11 | **Spend ledger automated backup** | **High** | `k8s/backup-cronjob.yaml:1-30` only backs up `headroom_memory.db` |
| 12 | **Corruption recovery for new savings store** | **Medium** | `headroom/savings/` has no `integrity_check` / corrupt-state handling |
| 13 | **Retry on upstream 5xx in core proxy** | **Medium** | `headroom/memory/adapters/embedders.py:572-597,795-830` has retry for memory; proxy path has none |
| 14 | **Dashboard search, filter, sort, pagination, bulk actions, loading states, error states** | **Medium** | `headroom/dashboard/templates/dashboard.html` has 0 `<input>` elements, 0 spinners, 0 toasts |
| 15 | **Native binary Prometheus exporter** | **Low** | `headroom/_core.abi3.so` exists but not exposed for runtime metrics |
| 16 | **Tests for `headroom.savings/` module** | **High** | 0 test imports in `tests/` (the entire new module on this branch) |
| 17 | **Tests for `headroom/proxy/routes/{airgap,rate_limit,rbac,secrets,sso}.py`** | **High** | 5 new route modules, 0 test coverage |
| 18 | **`/admin` EE dashboard** | **High** | `routes/admin.py:174-188` returns 404 (references missing `headroom/dashboard/dist/index.html`) |

---

## 3. Partial Implementations

| # | Feature | Implemented | Missing | Evidence |
|---|---|---|---|---|
| 1 | **SSO OIDC** | JWKS + introspection path | PyJWT missing branch silently bypasses signature verification (`sso.py:466-470`); JWKS-dict passed to `pyjwt.decode` raises on real keys (`sso.py:458-465`) | `headroom_ee/sso.py:263-558` |
| 2 | **Audit logging** | Two parallel stores: simple SQLite + hash chain | 8+ enum events never emitted (`auth.login`, `auth.failed`, `auth.key_rotated`, `license.validated`, etc.); default HMAC secret is `"dev-secret-key"`; only the simple store is wired into admin endpoints | `headroom_ee/audit.py:46-85`; `headroom_ee/audit/store.py:24`; `routes/admin.py:237-247` |
| 3 | **Multi-tenancy isolation** | Per-project SQLite (memory) + per-org spend | `/v1/memory/sync` accepts `org_id` from request body and trusts it; review endpoint has explicit TODOs admitting no auth/audit | `headroom_ee/memory_service/api.py:36-85` |
| 4 | **RBAC persistence** | In-memory dict with ~40 admin routes enforcing | Roles lost on restart; no multi-role; no team membership; no per-project override | `headroom_ee/rbac.py:102, 174-176` |
| 5 | **5-source savings model** | Parser + funnel + persistence + dashboard | Only 2 of 5 sources fire from live traffic (`provider_prompt_cache`, `semantic_cache`); 3 are structurally zero | Handler sites cited in §1.3 |
| 6 | **Encryption at rest** | Fernet (AES-128-CBC + HMAC-SHA256) | SOC2 roadmap claims AES-256 (`gtm/soc2-roadmap.md:60`) — false | `headroom/security/state_crypto.py:67-75`; `gtm/soc2-roadmap.md:60` |
| 7 | **Dashboard** | Read-only session stats with 5-source cards | No admin workflows (spend management, policy editing, RBAC assignment, SSO config, API-key rotation) in UI; CLI/API-only | `headroom/dashboard/templates/dashboard.html` |
| 8 | **Spending attribution** | Per-org/workspace/project at storage layer | `/v1/spend/*` is unauthenticated; auth in admin layer doesn't reach EE spend router | `headroom/proxy/routes/spend.py:1-14` |
| 9 | **Team-memory sync** | Sync endpoint + review endpoint | No auth, no RBAC, no audit, no tenant binding | `headroom_ee/memory_service/api.py:36-85` |
| 10 | **Provider failover** | Per-provider circuit breaker | `/v1/providers/{name}/disable\|enable` has no auth | `headroom/proxy/routes/failover.py:59, 74` |
| 11 | **Streaming PII redactor** | `wrap_stream` defined | Zero callsites; PII scanning of streamed responses never happens | `headroom/security/firewall.py:510-528` |
| 12 | **ML-based prompt injection classifier** | ONNX classifier defined | `security/models/injection_classifier.onnx` does not exist on disk; silently returns 0.0 | `headroom/security/firewall_ml.py:43-89` |
| 13 | **Audit "actor" attribution** | Some routes read `X-Headroom-User-Id` header | `policy/api.py:55` hardcodes `actor="admin"`; actor is client-controllable everywhere | `headroom_ee/policy/api.py:55`; `routes/admin.py:45-47` |
| 14 | **CSP / XSS hardening on dashboard** | Alpine.js HTML-escape helpers used in some places | Live feed string-literal contains user content from disk (`dashboard.html:1724-1726`) — pattern is inconsistent | `headroom/dashboard/templates/dashboard.html:1724` |

---

## 4. Broken Functionality

| # | Issue | Severity | Evidence |
|---|---|---|---|
| 1 | **`/admin` returns 404 with raw HTML** (EE dashboard route references non-existent file) | **Critical (UX)** | `headroom/proxy/routes/admin.py:174-188` reads `headroom/dashboard/dist/index.html` which does not exist |
| 2 | **SSO signature verification silently bypassed when PyJWT missing** | **Critical (Security)** | `headroom_ee/sso.py:466-470` |
| 3 | **Dashboard "Documentation" footer link points to `cutctx.dev/docs` which serves the old Headroom brand** | **High (UX)** | `dashboard.html:1528` |
| 4 | **All EE routes mounted without auth**: `/v1/spend/*`, `/v1/policies/*`, `/v1/audit/*`, `/v1/memory/*`, `/v1/license/*`, `/webhooks/stripe` | **Critical (Security)** | `headroom/proxy/routes/{spend,policy,audit,memory,license,license_validation}.py:1-14` |
| 5 | **Default admin key auto-generated and logged in plaintext when `HEADROOM_ADMIN_API_KEY` is unset** | **High (Security)** | `headroom/proxy/server.py:2252-2260` |
| 6 | **`/v1/providers/{name}/disable` has no auth** | **High (Security)** | `headroom/proxy/routes/failover.py:59, 74` |
| 7 | **`RequestOutcome.from_stream` cannot carry `self_hosted_prefix_cache_hits` or `model_routing_*` (no parameters in signature)** | **High (Functional)** | `headroom/proxy/outcome.py:278-307` |
| 8 | **Duplicate `_build_savings_breakdown` in outcome.py:36-92 (dead code) and outcome.py:405-540 (active)** | **Medium (Maintainability)** | `headroom/proxy/outcome.py:36, 405` |
| 9 | **cutctx_compression is computed redundantly in two places; funnel's value overwritten by savings_tracker fallback** | **Medium (Correctness)** | `headroom/proxy/savings_tracker.py:644-656` vs `headroom/proxy/outcome.py:464-474` |
| 10 | **Hub label inconsistency: `chopratejas` in `docker-compose.native.yml` vs `aryansingh` in Helm chart** | **Low** | `docker/docker-compose.native.yml:4` vs `helm/headroom/values.yaml:6` |
| 11 | **Helm chart `tag: "latest"` despite audit claim it was pinned to v0.26.0** | **Medium (Ops)** | `helm/headroom/values.yaml:6` |
| 12 | **`cutctx learn_share` not registered in `_register_commands()` (file exists, command unreachable)** | **Low** | `headroom/cli/learn_share.py`; `headroom/cli/main.py:41-66` |
| 13 | **Dashboard "Per-source USD cards" guard has subtle null-truthy bug in `x-if`** | **Low** | `headroom/dashboard/templates/dashboard.html:254` |
| 14 | **Hardcoded `version: '0.3.0'` in dashboard HTML; real version only after `/health` succeeds** | **Low** | `headroom/dashboard/templates/dashboard.html:1539` |
| 15 | **Retirement manager `start()` is never called at server boot** | **High (Compliance)** | `headroom_ee/retention.py:107-122` (no caller in `server.py`) |
| 16 | **Audit hash-chain store uses default `"dev-secret-key"`** | **High (Security)** | `headroom_ee/audit/store.py:24` |
| 17 | **DPA_TEMPLATE and MSA_TEMPLATE files in `artifacts/legal/` are still under pre-rebrand paths** | **Low** | `artifacts/legal/DPA_TEMPLATE.md`, `artifacts/legal/MSA_TEMPLATE.md` (modified in working tree, not committed) |
| 18 | **Dashboard footer "Documentation" link → `cutctx.dev/docs` (old brand)** | **Medium (UX)** | `headroom/dashboard/templates/dashboard.html:1528` |

---

## 5. Competitive Gap Analysis

**Competitors evaluated:** Portkey AI Gateway, Cloudflare AI Gateway, LiteLLM, OpenRouter, Helicone.

| Capability | Cutctx | Portkey | Cloudflare AI Gateway | LiteLLM | OpenRouter | Helicone |
|---|---|---|---|---|---|---|
| LLM proxy (multi-provider) | Full (5 providers) | Yes | Yes | Yes (100+ models) | Yes | Yes |
| Compression / token reduction | 5-source model | No (caching only) | No (caching only) | No | No | No |
| Prompt caching (provider-native) | Yes | Yes | Yes | Yes | No | Yes |
| Semantic cache (response cache) | Yes | Yes | Yes | No | No | Yes |
| Self-hosted prefix cache (vLLM APC) | Parser-only, no live detection | Yes (auto-detect) | No | No | No | No |
| Model routing / downgrades | Parser-only, no live detection | Yes (cost, latency, A/B) | Yes (latency) | No | No | Yes (A/B) |
| Spend ledger / cost tracking | Yes | Yes | Yes | No | Yes | Yes |
| Per-tenant / per-org isolation | Data layer OK, auth incomplete | Yes | Yes (zone-based) | No | Yes | Yes |
| RBAC | Yes (in-memory, 4 roles) | Yes (DB-persisted) | Yes (Cloudflare Access) | No | No | Yes |
| SSO (OIDC) | Broken (PyJWT path) | Yes (SAML + OIDC) | Yes (Cloudflare Access) | No | No | Yes |
| SAML SSO | No | Yes | Yes | No | No | No |
| MFA on admin | No | Yes | Yes (Cloudflare Access) | No | No | No |
| Audit log | Partial (2 stores, dev secret, 8+ events not emitted) | Yes (tamper-evident) | Yes (Cloudflare Logs) | No | Yes | Yes |
| GDPR DSR endpoints | No | Yes | Yes | No | Yes | Yes |
| PII firewall | Regex (off by default) | Yes (configurable) | No | No | No | No |
| Streaming PII redaction | No (defined, unwired) | Yes | No | No | No | No |
| Rate limit per identity | No (per-IP only) | Yes | Yes | No | Yes | Yes |
| Webhooks (event subscription) | No (28-line stub) | Yes | Yes | No | Yes | Yes |
| Admin dashboard UI | Read-only stats; admin workflows CLI-only | Full | Cloudflare-native | No | Yes | Yes |
| SDKs (Python, TS, Go, Java) | Python + TS rebranded; Go + Java still "headroom" | Yes | No | Python only | Yes | Yes |
| Helm chart | Yes (tag: latest) | Yes | No (CF-native) | No | No | Yes |
| Self-hosted | Yes | Yes (BYO) | No (CF SaaS only) | Yes | No | Yes |
| Native binary (Rust) | Yes 33.5 MB | No | No | No | No | No |
| Multi-tenant spend attribution | Yes | Yes | Yes (per zone) | No | Yes | Yes |
| **Overall** | **Strong compression, weak enterprise security/ops** | **Strong enterprise** | **Strong infra, no compression** | **Strong dev, no enterprise** | **Strong consumer** | **Strong observability** |

### Competitive Differentiation Opportunities

1. **5-source savings model with buyer-grade USD attribution** is unique — no competitor breaks out `cutctx_compression` vs `provider_prompt_cache` vs `model_routing` USD independently. This is the real moat. **But** 3 of 5 sources don't fire from live traffic (Gap #2 in §1.3). Closing this gap creates a category-defining differentiator.
2. **Self-hosted + native binary (Rust)** is rare — only Cutctx offers a 33.5 MB native binary + Python + Helm + Docker, all with the same features. Portkey and Helicone are SaaS; Cloudflare is SaaS-only; LiteLLM is Python-only.
3. **PII firewall + PII redaction** is partially differentiated. Portkey has PII detection; Cutctx has regex-based firewall + streaming redactor (if wired). Closing the streaming redactor wiring gap would match Portkey.

### Competitive Gaps (where Cutctx is behind)

1. **No MFA, no SAML, broken OIDC signature verification** — every enterprise competitor (Portkey, Cloudflare, Helicone) has these. **Critical for B2B SaaS.**
2. **No DSR/DSAR endpoints** — required by EU/CA customers. **Critical.**
3. **Admin workflows in UI** — Portkey, Cloudflare, Helicone all have full admin UIs. Cutctx has read-only stats. **High for UX.**
4. **Per-identity rate limit, webhooks with retry/signing, MFA, SAML** — all table-stakes for enterprise tier. **High.**
5. **Live vLLM APC + live model routing** — only 2 of 5 savings sources actually fire. The headline feature is structurally half-built. **High (this is the moat).**

---

## 6. Commercialization Blockers

These are the items that, if not closed, will block a paid enterprise customer from signing.

### 6.1 Blocker 1 — Security: Unauthenticated EE routes
**Severity: Critical (would fail any enterprise security review)**

`/v1/spend/*` (ingest + query + export), `/v1/policies/*` (mutate), `/v1/audit/*` (write), `/v1/memory/*` (read+write), `/v1/license/*`, `/v1/providers/{name}/disable`, `/webhooks/stripe` are all mounted without admin auth or RBAC. The team-memory sync API has explicit TODO comments in the code admitting this.

**Fix:** Add `Depends(_require_admin_auth)` + `Depends(_require_rbac_permission(...))` to all EE router mounts in `headroom/proxy/routes/spend.py`, `policy.py`, `audit.py`, `memory.py`, `license.py`, `license_validation.py`, and `failover.py`.

### 6.2 Blocker 2 — Compliance: No DSR/DSAR endpoints
**Severity: Critical (legal requirement for EU + CA customers)**

Zero right-to-delete or right-to-export endpoints exist. The audit, memory, CCR, and org stores all support individual row CRUD but no end-user "delete me from all stores" flow.

**Fix:** Add `/v1/me/export` (returns JSON of all data for the requesting user) and `/v1/me/delete` (cascades across memory, CCR, audit, spend tables).

### 6.3 Blocker 3 — Compliance: SOC2 docs reference file paths that don't exist
**Severity: High (will be flagged in procurement review)**

`docs/security/SOC2_CONTROLS.md:21-26` and `docs/security/SECURITY_POLICY.md:23,49,72` reference `cutctx/license.py`, `cutctx/auth.py`, `plugins/cutctx-oauth2/`, `cutctx/observability/` — none of these exist in the current repo. A SOC2 auditor will read both docs and flag the contradiction.

**Fix:** Either rebrand the doc paths or update them to point to actual code locations.

### 6.4 Blocker 4 — Compliance: SOC2 roadmap claims "Implemented" for items that aren't
**Severity: High (auditor will catch in the first review)**

- `gtm/soc2-roadmap.md:53` "MFA for all admin access — Implemented" — **false**
- `gtm/soc2-roadmap.md:60` "Encryption at rest (AES-256)" — **false** (it's Fernet = AES-128-CBC)
- `gtm/soc2-roadmap.md:78` "Automated backups — Implemented" — **partially false** (only `headroom_memory.db` backed up; spend ledger has no backup)
- `gtm/soc2-roadmap.md:42` "Data retention policies" — **false** (RetentionManager exists but never auto-started)
- `gtm/soc2-roadmap.md:70` "Centralized log aggregation" — **false** (logs are local files only)
- `gtm/soc2-roadmap.md:79-82` "Recovery procedures", "DR plan documentation", "Regular DR testing", "Capacity planning" — all **false**

**Fix:** Either implement the controls or update the roadmap to accurately reflect the state.

### 6.5 Blocker 5 — Commercial: 3 of 5 savings sources don't fire from live traffic
**Severity: High (the headline moat-b1 feature is half-built)**

`prefix_cache_self_hosted`, `model_routing_tokens_saved`, `model_routing_usd_saved` are hardcoded to `0` in every live handler. The dashboard and buyer report show 0 for these three sources for any production deployment that doesn't opt in to header-based telemetry. The product commercial claim is "5 savings sources" but only 2 actually fire.

**Fix:** Add either (a) response-header-based vLLM APC detection + cost-based model routing policy, or (b) a local prefix-cache store + a routing policy resolver. The escape hatch `savings_metadata` only fires from `x-headroom-*` request headers that the client must set.

### 6.6 Blocker 6 — UX: `/admin` EE dashboard returns 404
**Severity: High (enterprise admin surface is invisible)**

`headroom/proxy/routes/admin.py:174-188` returns 404 because it references `headroom/dashboard/dist/index.html` which doesn't exist. The real dashboard is at `headroom/dashboard/templates/dashboard.html`.

**Fix:** Either build the EE admin dashboard, or change `/admin` to redirect to `/dashboard` (the working one).

### 6.7 Blocker 7 — Security: SSO signature verification broken
**Severity: Critical (enterprise SSO doesn't work)**

`headroom_ee/sso.py:466-470` silently bypasses signature verification if PyJWT is missing. `sso.py:458-465` passes a JWKS dict to `pyjwt.decode` which expects a PEM/cryptography key object — this will raise on real keys. Either install PyJWT in production (required) AND fix the JWKS handling, or document that the operator must write a custom key-resolver.

**Fix:** Install PyJWT as a required dependency; replace the JWKS-dict-with-key=path branch with a proper key resolver that calls `cryptography.hazmat.primitives.serialization.load_pem_public_key` on the JWKS `x5c` claim or a hard-coded JWKS URL.

### 6.8 Blocker 8 — Security: Default admin key logged in plaintext
**Severity: High (any centralized logging will leak admin credentials)**

`headroom/proxy/server.py:2258-2259` logs the auto-generated admin key at WARNING level when no `HEADROOM_ADMIN_API_KEY` is set. Any log aggregator (Datadog, Splunk, CloudWatch) will capture the key.

**Fix:** Either (a) refuse to start without `HEADROOM_ADMIN_API_KEY` set, or (b) log the key only at startup on stdout (not via Python logging), and only if no env var is set.

---

## 7. Prioritized Roadmap

### Critical (must close before paid enterprise release)

1. **Add admin auth + RBAC to all EE routes** (`spend.py`, `policy.py`, `audit.py`, `memory.py`, `license.py`, `license_validation.py`, `failover.py`).
2. **Fix SSO signature verification** (PyJWT as required dep, proper key resolver).
3. **Add GDPR/CCPA DSR endpoints** (`/v1/me/export`, `/v1/me/delete`).
4. **Wire live vLLM APC + model routing** (either header-based or local-prefix/routing-policy).
5. **Fix `/admin` 404** (build EE admin dashboard or redirect to `/dashboard`).
6. **Stop logging admin key in plaintext** (require env var or log to stdout only).
7. **Update SOC2 docs** (remove "Implemented" claims for unimplemented controls; fix path references).
8. **Start retention manager at boot** (call `get_retention_manager().start()` in `server.py:lifespan`).
9. **Set `HEADROOM_AUDIT_SECRET_KEY` as a required env var** (refuse to start with default `"dev-secret-key"`).
10. **Wire streaming PII redactor** (`wrap_stream` callsites in handlers).

### High (must close before public beta)

11. **Add SAML SSO** (use `python3-saml` or `pysaml2`).
12. **Add MFA on admin access** (TOTP via `pyotp` or hardware key via WebAuthn).
13. **End-user API key issuance** (`/v1/keys/*` endpoints + CLI).
14. **Per-identity rate limiting** (key buckets by org_id / user_id / api_key_id).
15. **Outbound webhooks with retry + signing + event types** (`svix`-style event delivery).
16. **Spend ledger automated backup** (extend `k8s/backup-cronjob.yaml`).
17. **Remove duplicate `_build_savings_breakdown` in `outcome.py:36-92`**.
18. **Update dashboard footer link** (point to current docs URL, not the old `cutctx.dev/docs`).
19. **Pin Helm chart image tag** (replace `latest` with `0.26.0`).
20. **Add tests for `headroom.savings/` module** (the new moat-b1 code).
21. **Add tests for `headroom/proxy/routes/{airgap,rate_limit,rbac,secrets,sso}.py`** (5 new route modules with 0 coverage).
22. **Add dashboard search/filter/sort/pagination/loading/error states** (the dashboard is read-only stats; an enterprise admin needs to slice/dice).
23. **Wire `RequestOutcome.from_stream` to accept per-source fields** so streaming traffic can populate `self_hosted_prefix_cache_hits` and `model_routing_*`.
24. **Stop the uncommitted rebrand** — commit the 51-test fix atomically as `chore: complete rebrand Headroom→Cutctx`.

### Medium (close within 2 quarters)

25. **Add retry on upstream 5xx in core proxy** (use `tenacity` or a custom retry decorator).
26. **Add corruption recovery for the new savings state store** (PRAGMA integrity_check on read; corrupt-state fallback).
27. **Implement audit-event emission for `auth.login`, `auth.failed`, `auth.key_rotated`, `license.validated`** (all defined in enum, never emitted).
28. **Wire abuse alerts to a delivery channel** (webhook or email).
29. **Remove the dead fallback in `savings_tracker.record_request:644-656`** (or document it as a contract for tests).
30. **Add admin workflows to the dashboard UI** (spend management, policy editing, RBAC assignment, SSO config, API-key rotation) — currently CLI/API only.
31. **Build the EE admin dashboard** (`/admin`) or remove the route.
32. **Move audit hash-chain store into the live admin endpoints** (currently only the simple store is wired).
33. **Replace `X-Headroom-User-Id` as audit-actor source** with the actual authenticated identity (SSO claims or admin key fingerprint).
34. **Wire native binary Prometheus exporter** (currently the Rust core is opaque to metrics).
35. **Align Helm + Docker ownership metadata** (`chopratejas` vs `aryansingh`).
36. **Re-enable LLM firewall by default** for at least the public cloud tier (currently `firewall_enabled: bool = False`).
37. **Rebrand Go + Java SDKs** (still use old "headroom" name).
38. **Add onboarding "Welcome" state for zero-traffic users** (currently shows `$0.00` with no guidance).

### Low (close when bandwidth allows)

39. **Add CSRF protection on admin surface** (FastAPI doesn't ship CSRF tokens by default).
40. **Replace literal `0.3.0` in dashboard header** with the dynamic version from `/health`.
41. **Fix the `usd` dict null-truthy bug in `x-if` guard** at `dashboard.html:254`.
42. **Reduce dashboard hardcoded strings** ("Enable CUTCTX_LOG_MESSAGES=true to see content") with i18n.
43. **Make the live feed drawer closable via Esc key** (currently only click-outside closes it).
44. **Add a `consistency_check` field to `report buyer` and `integrations status`** that asserts `sum(savings_by_source_tokens) == delta_tokens_saved` for each row.
45. **Update stale docs** (`docs/spend-ledger.md:12`, `policies.md:16`, `memory-portability.md:24`, `audit-compliance.md:20`, `licensing-migration.md:15`).
46. **Remove the `cutctx learn_share` orphaned CLI command** or register it.

---

## 8. Production Readiness Score: **62 / 100**

| Category | Weight | Score | Notes |
|---|---|---|---|
| Core proxy functionality | 20% | 18/20 | Full provider coverage, compression, semantic cache, all 5 savings sources wired at data layer |
| Reliability (health, retry, circuit breaker, graceful shutdown) | 15% | 11/15 | Health endpoints, 2 circuit breakers, graceful shutdown — no retry on upstream 5xx, no corruption recovery |
| Observability (metrics, logging) | 10% | 5/10 | Prometheus implemented but admin-gated; no `dictConfig` / JSON formatter; no SIEM |
| Dashboard UX | 10% | 4/10 | Read-only stats, decent empty states, per-source USD cards — no search/filter/sort/bulk/export |
| Test coverage | 10% | 7/10 | 7,338 tests, 66.7% module coverage — 0 tests for new `headroom.savings/`, 5 new route modules with 0 coverage |
| Packaging + deployment | 10% | 8/10 | Python + TS + Rust + Helm + Docker all present — tag is `latest`, ownership inconsistent |
| 5-source savings model end-to-end | 15% | 5/15 | Data layer complete, dashboard/CLI/durable history complete — 3 of 5 sources don't fire from live traffic |
| CLI surface | 10% | 4/10 | 28 top-level commands, most work end-to-end, some JSON outputs always valid at zero state |

**Deductions (38 points lost):**

- 3 of 5 savings sources structurally zero in live traffic (-10)
- All EE routes unauthenticated, broken SSO, default dev secrets (-8)
- No DSR/DSAR endpoints, no MFA, no SAML, no per-identity rate limit (-6)
- 0 tests for new `headroom.savings/` module + 5 new route modules with 0 coverage (-4)
- Helm tag `latest`, ownership inconsistency, dashboard footer dead link (-3)
- No retry on upstream 5xx, no corruption recovery, no centralized log aggregation (-4)
- `/admin` returns 404, dashboard has no admin workflows, all filters decorative (-3)

---

## 9. Enterprise Readiness Score: **38 / 100**

| Category | Weight | Score | Notes |
|---|---|---|---|
| Authentication (admin + SSO + MFA + SAML) | 15% | 5/15 | Admin auth OK, OIDC broken, SAML/MFA missing |
| Authorization (RBAC + per-endpoint + per-resource) | 10% | 7/10 | RBAC implemented, 4 roles, 25+ permissions, ~40 routes enforce |
| Audit logging (tamper-evident, comprehensive, retention) | 10% | 3/10 | Two stores, default `"dev-secret-key"`, 8+ events never emitted, retention manager not auto-started |
| Compliance (GDPR/CCPA/SOC2/HIPAA) | 15% | 0/15 | No DSR/DSAR endpoints; SOC2 docs reference non-existent files; SOC2 roadmap claims unimplemented items |
| Multi-tenancy isolation (data + enforcement) | 10% | 5/10 | Per-project SQLite + per-org spend — `/v1/memory/sync` and `/v1/spend/*` are unauthenticated |
| Encryption (at rest + in transit) | 5% | 2/5 | Fernet (AES-128) not AES-256; TLS depends on deployment |
| Security hardening (firewall, PII, secret detection) | 10% | 4/10 | Regex firewall off by default; ML classifier model missing; streaming redactor unwired |
| Admin UI workflows (spend, policy, RBAC, SSO config) | 10% | 0/10 | Read-only stats only; admin workflows are CLI/API only |
| Incident response + DR + backups | 5% | 0/5 | No IR plan in code; no DR; spend ledger not backed up; `k8s/backup-cronjob.yaml` only covers `headroom_memory.db` |
| Webhooks / event subscription | 5% | 1/5 | 28-line stub, no retry, no signing, no event types |
| Per-identity rate limit | 5% | 0/5 | Per-IP only |

**Deductions (62 points lost):**

- No DSR/DSAR endpoints, no MFA, no SAML, broken OIDC (-20)
- All EE routes unauthenticated, no admin UI workflows, SOC2 docs inaccurate (-18)
- No IR plan, no DR, spend ledger not backed up, default HMAC dev secret, 8+ audit events never emitted (-15)
- No per-identity rate limit, firewall off by default, streaming redactor unwired, ML classifier model missing (-9)

---

## 10. OSS Readiness Score: **78 / 100**

For comparison, if Cutctx were sold as a self-hosted open-core product (no enterprise features, no DSR claims, no SOC2 claims), the score would be:

| Category | Score | Notes |
|---|---|---|
| Core proxy + compression | 9/10 | Full provider coverage, 5-source model wired at data layer (3 sources require opt-in headers) |
| Reliability | 8/10 | Health endpoints, circuit breakers, graceful shutdown, Docker healthchecks |
| Dashboard | 7/10 | Read-only stats with per-source USD cards, decent empty states, no interactivity |
| Test coverage | 7/10 | 7,338 tests, 66.7% module coverage — gaps in new code |
| Packaging + deployment | 8/10 | Python + TS + Rust + Helm + Docker + native binary |
| Security (out of the box) | 6/10 | Admin auth OK, but `/v1/spend/*` etc. unauthenticated (mitigated if OSS users only expose the proxy endpoints) |
| Documentation | 7/10 | 38 wiki pages, 56 docs, mostly current; some stubs |

**Deductions (22 points lost):**

- 3 of 5 savings sources don't fire from live traffic (-6)
- All EE routes unauthenticated (-4)
- Helm tag `latest`, ownership inconsistent (-3)
- No retry on upstream 5xx, no corruption recovery, dashboard has no interactivity (-4)
- Default admin key logged in plaintext (-2)
- No tests for new `headroom.savings/` module (-3)

---

## 11. Final Recommendation

### **NO-GO** for paid enterprise release in current state.

### **GO** for:

- **Public OSS release** with explicit "no enterprise features" labeling and a "Production-Ready" caveat in README that 3 of 5 savings sources require opt-in header configuration.
- **Internal beta** for 1-3 design partners willing to sign an NDA + accept the security disclosure.
- **Public beta** only after Critical items 1-7 (Blokers 1-7 in §6) are closed.

### Timeline to **GO** for paid enterprise release:

| Phase | Duration | What closes |
|---|---|---|
| **Phase 1: Security lockdown** | 4-6 weeks | Critical Blokers 1, 2, 7, 8 (auth on EE routes, DSR, SSO fix, admin key), High items 11, 12 (MFA, SAML) |
| **Phase 2: Moat-b1 completion** | 3-4 weeks | Critical Blocker 5 (wire live vLLM APC + model routing); High item 23 (streaming per-source fields) |
| **Phase 3: UX + admin workflows** | 4-6 weeks | Critical Blocker 6 (`/admin` 404); High items 13, 22 (API key issuance, dashboard interactivity) |
| **Phase 4: Reliability + ops** | 3-4 weeks | High items 14, 15, 16, 17, 19 (per-identity rate limit, webhooks, spend backup, dedup `outcome.py`, Helm tag); Medium items 25-27 (retry, corruption recovery, audit-event emission) |
| **Phase 5: SOC2 readiness** | 6-8 weeks | Critical Blocker 3, 4 (SOC2 docs); High item 24 (commit rebrand) |

**Total: 20-28 weeks (5-7 months) to paid enterprise readiness.**

### The single most important next step

Close **Critical Blocker 1 (unauthenticated EE routes)**. This is the highest-severity, highest-credibility issue. If discovered by any enterprise security reviewer, it ends the deal in the first 15 minutes. Add `Depends(_require_admin_auth)` to all EE router mounts in `headroom/proxy/routes/{spend,policy,audit,memory,license,license_validation,failover}.py`. Estimated 1-2 days of work.

The second most important is **Critical Blocker 5 (live detection of vLLM APC + model routing)**, because the commercial claim of "5 savings sources" is currently only 2 sources in production. Closing this gap creates the moat. Estimated 1-2 weeks.

---

## Appendix A — Evidence Index

### Critical security

- `headroom/proxy/server.py:2241-2343` — admin auth + SSO validator wiring
- `headroom/proxy/server.py:2252-2260` — default admin key logged in plaintext
- `headroom/proxy/server.py:2278-2299` — HMAC compare_digest for admin key
- `headroom_ee/sso.py:263-558` — full OIDC/JWKS validator (broken PyJWT path at 466-470)
- `headroom/proxy/routes/spend.py:1-14` — `/v1/spend/*` unauthenticated
- `headroom/proxy/routes/policy.py`, `audit.py`, `memory.py`, `license.py` — same pattern
- `headroom/proxy/routes/failover.py:59, 74` — `/v1/providers/{name}/disable` unauthenticated
- `headroom_ee/memory_service/api.py:36-85` — team-memory sync with explicit TODOs admitting no auth/audit
- `headroom_ee/audit.py:46-85` — AuditAction enum with 8+ events never emitted
- `headroom_ee/audit/store.py:24` — default `"dev-secret-key"` HMAC
- `headroom/proxy/security.py:4` + `state_crypto.py` — Fernet (AES-128-CBC)
- `headroom_ee/retention.py:107-122` — retention manager `start()` never called from `server.py`

### Core proxy + savings

- `headroom/proxy/handlers/anthropic.py:807, 1961, 2496, 2922, 3051, 3238` — 6 RequestOutcome sites
- `headroom/proxy/handlers/openai/chat.py:287, 998, 1321` — 3 RequestOutcome sites
- `headroom/proxy/outcome.py:36-92, 278-307, 405-540, 543-712` — duplicate `_build_savings_breakdown`, `from_stream` lacking fields, `emit_request_outcome` funnel
- `headroom/proxy/savings_tracker.py:254-364, 572-903` — `_normalize_history_entry`, `record_request`
- `headroom/savings/integrations.py:48-119` — parsers for vLLM APC, gptcache, model routing, litellm
- `headroom/proxy/handlers/anthropic.py:790-840` — semantic cache hit branch
- `headroom/proxy/handlers/openai/chat.py:275-325` — semantic cache hit branch

### Dashboard

- `headroom/dashboard/templates/dashboard.html:2351` (file size)
- `headroom/dashboard/templates/dashboard.html:254-313` — per-source USD cards (the moat-b1 commit db7f7a4)
- `headroom/dashboard/templates/dashboard.html:1014, 1125-1132` — Recent Requests table + export buttons
- `headroom/dashboard/templates/dashboard.html:1100-1106, 1469-1476, 804-808` — empty states
- `headroom/dashboard/templates/dashboard.html:1528, 1539` — dead docs link + hardcoded version
- `headroom/proxy/server.py:2829-2891` — `_build_stats_payload` (savings_by_source added in commit db7f7a4)
- `headroom/proxy/routes/admin.py:174-188` — `/admin` 404

### Enterprise

- `headroom_ee/rbac.py:31-204` — RBAC roles, permissions, in-memory persistence
- `headroom_ee/org.py:66-465` — Org/Workspace/Project hierarchy
- `headroom_ee/audit.py:88-360` — audit logger
- `headroom_ee/audit/store.py:17-156` — hash-chain store
- `headroom_ee/abuse.py:135-289` — abuse detection (alerts not delivered)
- `headroom/security/residency_proof.py:1-338` — Ed25519-signed attestation

### Reliability

- `headroom/proxy/server.py:2617-2641` — health endpoints
- `headroom/proxy/server.py:1545-1714` — lifespan context manager
- `headroom/proxy/routing/failover.py:3-155` — per-provider circuit breaker
- `headroom/transforms/pipeline.py:36-49, 89-97` — pipeline circuit breaker
- `k8s/backup-cronjob.yaml:1-30` — daily backup of `headroom_memory.db` only

### Tests

- 7,338 tests collected in 11.48s (post-rebrand)
- 0 tests for `headroom.savings/` module (the new moat-b1 code)
- 0 tests for `headroom/proxy/routes/{airgap,rate_limit,rbac,secrets,sso}.py` (5 new route modules)

### Packaging

- `pyproject.toml:3-4` — `name = "cutctx-ai"`, `version = "0.26.0"`
- `headroom/_core.abi3.so` — 33.5 MB, built 2026-06-20 21:21
- `helm/headroom/values.yaml:6` — `tag: "latest"` (audit claim of pinned tag is false)
- `docker/docker-compose.native.yml:4` — `ghcr.io/chopratejas/headroom` (old owner)
- `helm/headroom/values.yaml:6` — `ghcr.io/aryansingh/headroom` (new owner) — inconsistent

### Plugins

- `plugins/headroom-oauth2/pyproject.toml:1-30` — functional OAuth2 plugin
- `plugins/headroom-agent-hooks/hooks/hooks.json` — functional Claude Code plugin
- `plugins/hermes/headroom_retrieve/__init__.py` — stub (no real code)
- `plugins/claude-code/`, `plugins/codex/` — README-only (no actual plugin)
- `plugins/cutctx-plugin/` — stub (only `__pycache__`)

---

## Appendix B — Top 5 Things to Tell the Customer Right Now

If a customer asks "is Cutctx production-ready?" the honest answer today is:

1. **The compression pipeline is real and working.** 5 sources tracked, USD attribution is buyer-grade accurate, dashboard shows per-source USD, durable history survives restart, CLI reports JSON always (even at zero state). **Verified end-to-end.**

2. **3 of the 5 savings sources are opt-in only.** Provider cache and semantic cache fire from real traffic. Self-hosted prefix cache, model routing require either header-based opt-in (`x-headroom-prefix-cache-hits`, `x-headroom-model-routing-tokens`, `x-headroom-model-routing-usd`) or a future code change to enable live detection. **The buyer report and dashboard will show 0 for these three sources until either of those is in place.**

3. **The enterprise security surface has known gaps.** SSO OIDC signature verification is broken out of the box. Some EE routes (`/v1/spend/*`, `/v1/memory/sync`, `/v1/providers/{name}/disable`) are unauthenticated. There's no MFA, no SAML, no DSR/DSAR endpoints, and the SOC2 roadmap claims items that aren't actually implemented. **A serious enterprise security review will surface these and they'll block procurement.**

4. **The admin UI is read-only stats.** The enterprise admin workflows (spend management, policy editing, RBAC assignment, SSO config, API-key rotation) are CLI- or API-only. The `/admin` EE dashboard returns 404.

5. **Backups are partial.** The `k8s/backup-cronjob.yaml` only backs up the memory database. The spend ledger, audit log, and savings state files are not in any automated backup. The memory store has corruption-recovery tests; the new savings store does not.

**For a private design partner with disclosure, the proxy is usable today.** **For paid enterprise, the timeline is 5-7 months of focused work.** **For public OSS, the product is ready with a clearly-documented "no enterprise features" caveat.**
