# Cutctx Deep Manual Audit — Final Verdict

**Date:** 2026-06-21
**Branch:** `moat-b1-team-memory-svc`
**HEAD:** `fb73887b`
**Auditor role:** Principal PM + Staff SWE + QA Lead + Security Engineer + Solutions Architect
**Method:** Four parallel deep-dive verification lanes (security, core proxy, EE+commercial, dashboard+UX+deployment). Every finding cites `file:line` evidence. Live tests run via `.venv/bin/python -m pytest`. This audit **supersedes** the 2026-06-20 baseline and the 2026-06-21 reconciliation.

---

## Executive Summary

The remediation series (commits `db7f7a45`..`fb73887b`, ~20 commits) closed 19 of 46 audit items. The headline 5-source savings model is now wired end-to-end at the data layer, EE routes are gated, SSO is fixed, DSR endpoints exist, audit has actor hierarchy + secret-key enforcement, and the deployment artifacts are correctly branded. **However, deep verification uncovered three HIGH-severity commercial blockers that the previous audits missed or mis-classified:**

1. **Model router is dead code** — the entire `cutctx/proxy/model_router.py` (300 lines, the headline moat-b1 differentiator) is bound to `proxy._model_router` at server boot but **zero handlers call it**. The `model_routing_tokens_saved` and `model_routing_usd_saved` fields are hardcoded to 0 at all 9 live handler sites. The same is true for `self_hosted_prefix_cache_hits`. The 5-source savings model's two differentiating sources are structurally zero end-to-end.
2. **Residency `verify()` is broken** — the signer signs `SHA-256(payload).digest()` (`cutctx/security/residency_proof.py:319-324`); the verifier passes `payload` raw (line 226). The in-process `verify()` method returns `False` for an attestation the prover itself just produced. Third-party verifiers (per docs) work; the in-process path does not.
3. **Three "high-severity" EE modules are pure stubs** despite the audit-claimed factory-pattern fix:
   - `cutctx/proxy/routes/secrets.py` — `list_secrets()` returns `[]` (line 46); `create_secret()` returns success-without-storage (line 54). No vault/AWS/GCP integration.
   - `cutctx/proxy/routes/airgap.py` — `get_airgap_status()` returns hardcoded `{"status": "active", "limits_enforced": True}` (line 44). No actual egress enforcement; the airgap module (`cutctx/proxy/airgap.py:11-29`) only logs warnings and is never called from the proxy runtime.
   - `cutctx_ee/memory_service/api.py:65-75` — explicit TODO comments admitting no auth/audit are still in place. The review endpoint is dead code.

**Production readiness: 60/100** (down from the 80/100 claimed by the 2026-06-21 final-status doc, because the model-router dead code is a critical commercial-claim failure).

**Enterprise readiness: 45/100** (the dead-code stubs and broken verifier are deal-breakers for any security review).

**OSS readiness: 80/100** (the proxy + compression pipeline is solid; the moat-b1 claim is half-built).

**Final recommendation: NO-GO for paid enterprise release. GO for public OSS release with explicit "5 sources wired, 2 require additional integration" disclosure. GO for internal design partner with security disclosure.**

---

## 1. Verified Feature Inventory (code-confirmed)

### 1.1 Core proxy (OSS, `cutctx/proxy/`)

| Feature | Status | Evidence |
|---|---|---|
| LLM request proxy (Anthropic, OpenAI Chat, OpenAI Responses, OpenAI Codex, Gemini, Bedrock, Vertex) | **Implemented** | `cutctx/proxy/server.py` lifespan + `cutctx/proxy/handlers/{anthropic,openai,google,vertex,bedrock,codex}` |
| Compression pipeline (CCR, SmartCrusher, LiveZone, Markdown-KV, etc.) | **Implemented** | `cutctx/transforms/pipeline.py:36-49,89-97` |
| Per-provider cache compatibility | **Implemented** | `cutctx/proxy/handlers/anthropic.py:2516-2520` |
| Response cache (semantic cache, in-memory) | **Implemented** | `cutctx/proxy/semantic_cache.py`; wired in `anthropic.py`, `openai/chat.py` |
| LLM Firewall (regex-based prompt injection + PII scanner) | **Implemented** | `cutctx/security/firewall.py:1-534` |
| Streaming PII redactor | **Implemented (wired)** | `cutctx/proxy/handlers/streaming.py:1175-1180` calls `wrap_stream()`; `proxy._streaming_redactor` set at `server.py:2146` |
| Upstream circuit breaker | **Implemented** | `cutctx/proxy/routing/failover.py:78-204` |
| Pipeline circuit breaker | **Implemented** | `cutctx/transforms/pipeline.py:36-49` |
| Health endpoints (`/livez`, `/readyz`, `/health`) | **Implemented** | `cutctx/proxy/server.py` |
| Prometheus `/metrics` | **Implemented** | `cutctx/proxy/prometheus_metrics.py` |
| Spend ledger | **Implemented** | `cutctx_ee/ledger/` |
| CLI (20 top-level commands, not 28) | **Implemented** | `cutctx/cli/main.py:43-66` — 6 documented commands are unreachable (see §3) |
| Helm chart, Docker, Docker Compose, npm wrapper | **Implemented** | `helm/cutctx/`, `Dockerfile`, `docker-compose.yml`, `sdk/typescript/` |

### 1.2 Enterprise layer (`cutctx_ee/`)

| Feature | Status | Evidence |
|---|---|---|
| RBAC (4 roles, 38 permissions) | **Implemented (in-memory)** | `cutctx_ee/rbac.py:50-92` |
| Admin auth + RBAC on EE routes | **Implemented** | `cutctx/proxy/server.py:3486-3657` — 14 factory calls |
| SSO (OIDC + JWT) | **Implemented (after fb73887b fix)** | `cutctx_ee/sso.py:263-642` — class boundary restored, 27/27 tests pass |
| DSR endpoints | **Implemented** | `cutctx/proxy/routes/dsr.py` — `/v1/me/export`, `/v1/me/delete` |
| Audit log (SQLite) | **Implemented** | `cutctx_ee/audit.py:88-360` |
| Audit log (HMAC hash chain + /audit/verify) | **Implemented** | `cutctx_ee/audit/store.py:174-203`; `/audit/verify` at `routes/admin.py:472-509` |
| Audit secret key enforcement | **Implemented** | `cutctx_ee/audit/store.py:40-73` — refuses to start without `CUTCTX_AUDIT_SECRET_KEY` |
| Audit actor hierarchy | **Implemented** | `cutctx/proxy/routes/admin.py:59-82` — `sso: > key:fp > admin` |
| Admin key not logged in plaintext | **Implemented** | `cutctx/proxy/server.py` — admin key printed to stderr only |
| SCIM 2.0 | **Implemented** | `cutctx_ee/scim.py:42-264`; 14 endpoints in `routes/admin.py:1020-1310` |
| Webhook dispatcher (HMAC-signed, retried, 8 event types) | **Implemented** | `cutctx/proxy/webhooks.py:68-83, 355-366, 367-425`; 22 tests pass |
| Per-identity rate limit | **Implemented** | `cutctx/proxy/rate_limiter.py:35-79`; `server.py:2236-2248` |
| Model router (config-driven) | **BOUND BUT NEVER CALLED** | `cutctx/proxy/model_router.py` (300 lines); `server.py:1692-1703` binds it; **0 callsites in handlers** |
| Billing / Stripe webhooks | **Implemented (with gaps)** | `cutctx_ee/billing/stripe_webhook.py` |
| License validation (Ed25519) | **Implemented (with caveat)** | `cutctx_ee/billing/license_token.py` is Ed25519; `pitchtoship_client.py` is ECDSA P-256 — two systems coexist |
| Air-gap mode | **NOT IMPLEMENTED** | `cutctx/proxy/airgap.py:11-29` only logs warnings; `routes/airgap.py:38-44` returns hardcoded payload |
| Secrets management | **NOT IMPLEMENTED** | `cutctx/proxy/routes/secrets.py:46, 54` — pure stub |
| Memory service auth/audit (EE module) | **NOT IMPLEMENTED** | `cutctx_ee/memory_service/api.py:65-75` — explicit TODOs unchanged |
| Residency proof (Ed25519) | **PARTIALLY BROKEN** | Signer signs `SHA256(payload)`; verifier passes `payload` raw — `verify()` returns False for valid signatures |

### 1.3 5-source savings model

| Source | Parser | Persisted | Surfaced in CLI/Dashboard | Fires from live traffic? |
|---|---|---|---|---|
| `provider_prompt_cache` | Yes | Yes | Yes | **Yes** |
| `cutctx_compression` | Yes (residual) | Yes | Yes | **Yes** |
| `semantic_cache` | Yes | Yes | Yes | **Yes** |
| `prefix_cache_self_hosted` | Yes (`parse_vllm_apc`) | Yes | Yes (CLI) | **No** — hardcoded 0 at all 9 handler sites; dashboard has no per-source view |
| `model_routing` | Yes (`parse_model_routing_metadata`) | Yes | Yes (CLI) | **No** — ModelRouter exists but is dead code; fields hardcoded 0 at all 9 sites |

**This is the moat-b1 commercial claim, and only 3 of 5 sources actually fire.**

---

## 2. Missing Features (verified)

| # | Feature | Severity | Evidence |
|---|---|---|---|
| 1 | **Live detection of vLLM APC prefix-cache hits** | **Critical** | All 9 handler sites hardcode `self_hosted_prefix_cache_hits=0` (`anthropic.py:830/1983/2532/2950/3086/3276`, `openai/chat.py:309/1023/1359`). Only fires from `x-cutctx-prefix-cache-hits` request header opt-in. |
| 2 | **Live model routing policy (downgrade opus→sonnet)** | **Critical** | `cutctx/proxy/model_router.py` is bound at boot (`server.py:1692-1703`) but **0 handler calls it** (grep for `_model_router` in `handlers/` returns 0 results). All 9 sites hardcode `model_routing_tokens_saved=0, model_routing_usd_saved=0.0`. |
| 3 | **Residency proof `verify()` method works** | **Critical** | `cutctx/security/residency_proof.py:226` calls `public_key.verify(sig_bytes, payload)` but line 324 signs `SHA256(payload).digest()`. Verified in-process: prover.sign → prover.verify returns False. |
| 4 | **Air-gap mode actually enforced** | **Critical** | `cutctx/proxy/airgap.py:11-29` only logs warnings; never called from `server.py`. `/v1/airgap/status` returns hardcoded `{"status": "active", "limits_enforced": True}`. |
| 5 | **Secret management backend** | **Critical** | `cutctx/proxy/routes/secrets.py:46, 54` — `list_secrets()` returns `[]`; `create_secret()` returns success-without-storage. No vault/AWS/GCP. |
| 6 | **EE memory service auth + audit** | **High** | `cutctx_ee/memory_service/api.py:65-75` — explicit TODOs unchanged. The `/v1/memory/review` endpoint is dead code. |
| 7 | **SAML SSO** | **High** | `cutctx_ee/sso.py` only handles JWT/JWKS/OIDC. |
| 8 | **MFA on admin** | **High** | No second-factor path in `server.py:2280-2343`. |
| 9 | **Per-source savings dashboard UI** | **High** | `dashboard/src/pages/Overview.jsx:55-71` has hardcoded "Compression Savings: 68.4%". No `Savings.jsx` page. Per-source fields never read. |
| 10 | **Dashboard search/filter/sort/loading/error states** | **High** | Zero `<input>`, `<select>`, `<textarea>`, `spinner`, `toast` elements in `dashboard.html`. |
| 11 | **6 documented CLI commands are unreachable** | **High** | `audit, orgs, rbac, sso-test, config-check, bench` — `python -m cutctx.cli <cmd>` returns "No such command". Help text in `main.py:24-36` lies. |
| 12 | **Dashboard per-source savings cards in React** | **Medium** | SSR dashboard `dashboard.html:276-320` has them. React dashboard Overview.jsx does not. |
| 13 | **`.env.example` documentation** | **Medium** | 3 lines total (`NEO4J_AUTH=neo4j/CHANGEME`). Does not document any `CUTCTX_*` env var. |
| 14 | **Tests for streaming.py** | **Medium** | 3 streaming tests fail with connection errors. The streaming PII redactor wiring is unverified. |
| 15 | **Rebrand cleanup in working tree** | **Medium** | `cutctx/__init__.py:101-102` exports `CutctxConfig, CutctxMode` (renamed to Cutctx elsewhere); `cutctx/client.py:938` references `CutctxMode.AUDIT` which no longer exists; `dashboard/src/App.jsx:14` shows "Cutctx" branding. |

---

## 3. Partial Implementations (verified)

| # | Feature | Implemented | Missing | Evidence |
|---|---|---|---|---|
| 1 | **5-source savings model** | Parser + funnel + persistence + CLI surfacing | 2 of 5 sources (`prefix_cache_self_hosted`, `model_routing`) never fire from live traffic; dashboard has no per-source view | Handler sites (cited in §1.3); `dashboard/src/pages/` |
| 2 | **RBAC persistence** | 38 permissions, 4 roles, factory pattern enforced | In-memory only (`cutctx_ee/rbac.py:184`); default-ADMIN fail-open when no SSO configured | `rbac.py:114-160` |
| 3 | **Webhooks** | HMAC, retry, 8 event types, admin API | Subscriptions in-memory only (`webhooks.py:174`); no persistent dead-letter queue | `webhooks.py:43-47, 174, 419-425` |
| 4 | **Audit logging** | Hash chain, /audit/verify, actor hierarchy, secret key enforcement | 14 of 22 enum events never emitted; production code emits 11+ string literals not in enum (`retention.cleanup`, `rbac.*`, etc.) — contract drift | `cutctx_ee/audit.py` (enum) vs `cutctx/proxy/server.py`, `routes/admin.py` |
| 5 | **Model routing** | Config-driven router with workload classifier + LiteLLM cost lookup + negative-delta protection | Bound at boot but never invoked; commercial claim is structurally false | `cutctx/proxy/model_router.py`; `server.py:1692-1703`; 0 callsites in handlers |
| 6 | **License validation** | Ed25519 hrk1 tokens (`license_token.py`); ECDSA P-256 in `pitchtoship_client.py` | Two crypto systems coexist; new Ed25519 tokens not verified anywhere in runtime | `cutctx_ee/billing/license_token.py` vs `pitchtoship_client.py` |
| 7 | **Spend ledger tenant isolation** | Auth-gated, per-org/workspace/project filters | `?group_by=org_id` with no filter returns all orgs to any authenticated admin | `cutctx_ee/ledger/query.py:18-103` |
| 8 | **Air-gap mode** | `CUTCTX_OFFLINE_MODE` env var; `/v1/airgap/status` endpoint | No egress blocking, no firewall rule, no domain blocklist; status is hardcoded | `cutctx/proxy/airgap.py:11-29`; `routes/airgap.py:38-44` |
| 9 | **Secrets management** | RBAC-permissioned `/v1/secrets/*` endpoints | `list_secrets()` returns `[]`; `create_secret()` returns success without storage | `cutctx/proxy/routes/secrets.py:46, 54` |
| 10 | **Streaming PII redactor** | `wrap_stream` defined; `proxy._streaming_redactor` set; `streaming.py:1175-1180` calls it | 3 streaming tests fail; not verified end-to-end | `cutctx/proxy/handlers/streaming.py` |
| 11 | **Audit actor in `server.py:3401`** | Hierarchy hardened in `routes/admin.py:59-82` | `server.py:3401` still uses `request.headers.get("x-cutctx-user-id", "admin")` for `/stats/reset` | `cutctx/proxy/server.py:3401` |
| 12 | **License DB EE tests** | `cutctx_ee/tests/test_license_e2e.py` exists | 5 of 6 tests FAIL — they predate Blocker-1 auth gate and were not updated to send admin auth headers | `cutctx_ee/tests/test_license_e2e.py` |
| 13 | **CLI surface** | 20 top-level commands registered | 6 documented commands unreachable (`audit, orgs, rbac, sso-test, config-check, bench`) | `cutctx/cli/main.py:43-66` |
| 14 | **CRL revocation check** | License token verification via PitchToShip | CRL/activation/seat/trial checks fail-open on network errors — attacker who isolates the proxy bypasses revocation | `cutctx_ee/billing/client.py:26, 36, 53, 67, 85, 98` |
| 15 | **Stripe webhook signature** | HMAC-SHA256 with `hmac.compare_digest()` | Skips verification if `STRIPE_WEBHOOK_SECRET` is empty — production must set explicitly | `cutctx_ee/billing/stripe_webhook.py:201-203` |
| 16 | **SOC2 roadmap line 87** | Marks spend-ledger backup as `⚠️ Partial` | Claim is outdated: k8s/backup-cronjob.yaml now covers `spend_ledger.db` + `audit.db` | `gtm/soc2-roadmap.md:87` |

---

## 4. Broken Functionality (verified)

| # | Issue | Severity | Evidence |
|---|---|---|---|
| 1 | **Residency `verify()` returns False for valid signatures** | **Critical (Security)** | `residency_proof.py:319-324` signs `SHA256(payload).digest()`; `:226` verifier passes `payload` raw. In-process `prover.verify(prover.sign(attest))` returns False. |
| 2 | **Model router is dead code — moat-b1 claim is half-built** | **Critical (Commercial)** | `proxy._model_router` bound at `server.py:1695`; 0 callsites in handlers. All 9 handler sites hardcode `model_routing_*=0`. |
| 3 | **CLI help text lies — 6 commands documented but unreachable** | **High (UX)** | `cutctx/cli/main.py:24-36` lists `cutctx audit, orgs, rbac, sso-test, config-check, bench`. `python -m cutctx.cli audit` → `Error: No such command 'audit'`. |
| 4 | **`CutctxMode` NameError regression** | **High (Functional)** | `cutctx/__init__.py:101-102` exports `CutctxConfig, CutctxMode` (old names); `cutctx/client.py:938` references `CutctxMode.AUDIT` (the enum that no longer exists in `cutctx/config.py:13`, which now defines `CutctxMode`). Test fails: `NameError: name 'CutctxMode' is not defined`. |
| 5 | **`/admin` route serves static React mockup with hardcoded values** | **High (UX)** | The React dashboard pages (Overview.jsx, Firewall.jsx, Memory.jsx) have hardcoded mock data: "4,289 Requests / min", "68.4% Compression Savings", "27 Active Patterns", "143 Blocks Today". The SSR dashboard at `/dashboard` shows real data — `/admin` is now a soft regression. |
| 6 | **Reactor: `cutctx/proxy/server.py:3401` still uses client-controllable `X-Cutctx-User-Id` header** | **High (Security)** | The Medium-33 fix hardened `routes/admin.py:59-82` to use `sso: > key: > admin` hierarchy, but `server.py:3401` for `/stats/reset` still uses `request.headers.get("x-cutctx-user-id", "admin")`. |
| 7 | **K8s `deployment.yaml:42` uses `cutctx-proxy:v0.26.0` (local docker tag)** | **Medium (Ops)** | For production, image should be `ghcr.io/aryansingh/cutctx:0.26.0` to match Helm. |
| 8 | **K8s `backup-cronjob.yaml:22` uses `alpine:latest`** | **Medium (Ops)** | The backup cron job itself uses `:latest`. |
| 9 | **K8s `secret.yaml:11` references `hello@cutctx.dev`** | **Low (Branding)** | Pre-rebrand email. |
| 10 | **`savings_tracker.verify_integrity` is not exposed via CLI** | **Low** | Method exists (`savings_tracker.py:1135`) but `cutctx savings` has no `--verify-integrity` flag. Operators must write Python. |
| 11 | **Dashboard React pages are static mockups** | **High (UX)** | 3 of 4 pages (Overview, Firewall, Memory) have hardcoded data with no API integration. Only Playground has real client-side logic. |
| 12 | **Dashboard `dashboard.html` has no loading spinners / toast / error UI** | **Medium (UX)** | Zero `animate-spin`, `aria-busy`, `aria-live`, `toast` elements. Silent failures on poll errors. |
| 13 | **`.env.example` is 3 lines** | **Medium (Ops)** | Only documents `NEO4J_AUTH`. Operators have no way to discover required `CUTCTX_*` env vars. |
| 14 | **Dashboard `dashboard.html` has no search/filter/sort UI** | **Medium (UX)** | Zero `<input>`, `<select>`, `<textarea>` elements. The only `input` elements are in the React topbar and are decorative. |

---

## 5. Competitive Gap Analysis

| Capability | Cutctx | Portkey AI Gateway | Cloudflare AI Gateway | LiteLLM | OpenRouter | Helicone |
|---|---|---|---|---|---|---|
| LLM proxy (multi-provider) | Full (5 providers) | Yes | Yes | Yes (100+ models) | Yes | Yes |
| Compression / token reduction | 5-source model | No (caching only) | No | No | No | No |
| **Live vLLM APC detection** | **No (parser only)** | Yes (auto-detect) | No | No | No | No |
| **Live model routing** | **No (bound but dead code)** | Yes (cost, latency, A/B) | Yes (latency) | No | No | Yes (A/B) |
| Prompt caching (provider-native) | Yes | Yes | Yes | Yes | No | Yes |
| Semantic cache | Yes | Yes | Yes | No | No | Yes |
| Spend ledger | Yes | Yes | Yes | No | Yes | Yes |
| Per-tenant isolation | Data OK, auth complete (after Blocker-1) | Yes | Yes (zone-based) | No | Yes | Yes |
| RBAC | Yes (in-memory) | Yes (DB) | Yes (CF Access) | No | No | Yes |
| SSO (OIDC) | Yes (after Blocker-4 fix) | Yes | Yes | No | No | Yes |
| SAML SSO | No | Yes | Yes | No | No | No |
| MFA on admin | No | Yes | Yes (CF Access) | No | No | No |
| Audit log (tamper-evident) | Partial (chain + verify endpoint) | Yes | Yes (CF Logs) | No | Yes | Yes |
| DSR/DSAR endpoints | Yes (after Blocker-2) | Yes | Yes | No | Yes | Yes |
| PII firewall | Yes (regex, off by default) | Yes | No | No | No | No |
| Streaming PII redaction | Yes (wired, unverified) | Yes | No | No | No | No |
| Per-identity rate limit | Yes (after High-14) | Yes | Yes | No | Yes | Yes |
| Webhooks (event subscription) | Yes (after High-15) | Yes | Yes | No | Yes | Yes |
| **Residency proof** | **Broken verifier** | No | No | No | No | No |
| **Air-gap mode** | **Not implemented** | No | No | No | No | No |
| **Secrets management** | **Stub only** | Yes | No | No | No | No |
| Admin dashboard UI | **Static mockups** | Full | Cloudflare-native | No | Yes | Yes |
| SDKs | Python + TS | Yes | No | Python only | Yes | Yes |
| Helm chart | Yes (tag pinned) | Yes | No | No | No | Yes |
| Self-hosted | Yes | Yes (BYO) | No (CF SaaS) | Yes | No | Yes |
| Native binary (Rust) | Yes 33.5 MB | No | No | No | No | No |
| Multi-tenant spend attribution | Yes (with caveat — see §3.7) | Yes | Yes (per zone) | No | Yes | Yes |
| **Overall** | **Strong compression+deployment, broken moat-b1 + residency + air-gap + secrets** | **Strong enterprise** | **Strong infra, no compression** | **Strong dev, no enterprise** | **Strong consumer** | **Strong observability** |

### Differentiation opportunities

1. **5-source savings model** is unique if completed. No competitor breaks out `cutctx_compression` vs `provider_prompt_cache` vs `model_routing` USD independently. **But** 2 of 5 sources don't fire from live traffic. Closing this gap creates a category-defining differentiator. **Currently the claim is over-promised.**
2. **Self-hosted + native binary (Rust)** is rare. Only Cutctx offers a 33.5 MB native binary + Python + Helm + Docker.
3. **Streaming PII redaction** is differentiated. Portkey has PII detection; Cutctx has regex firewall + streaming redactor (if wired). The wiring is now there (after Blocker-10 fix) but unverified in tests.

### Competitive gaps (where Cutctx is behind)

1. **Residency `verify()` broken** — a security reviewer at Portkey, Cloudflare, or Helicone would flag this in the first hour. **Critical.**
2. **Model routing dead code** — commercial claim of "5 sources" is only 3 in production. **Critical.**
3. **Air-gap mode unimplemented** — every regulated-industry customer (gov, finance, healthcare) requires real air-gap. **Critical.**
4. **Secrets management stub** — every enterprise has Vault/AWS Secrets Manager. **Critical.**
5. **No MFA, no SAML** — every enterprise competitor has these. **High.**
6. **Admin UI static mockups** — Portkey, Cloudflare, Helicone have full admin UIs. **High.**
7. **Dashboard has no interactivity (search/filter/sort/loading/error)** — table-stakes for any UI. **High.**

---

## 6. Commercialization Blockers

These items will block a paid enterprise customer from signing.

### 6.1 Blocker 1 — Model router is dead code (moat-b1 claim is half-built)

**Severity: Critical (will fail commercial due-diligence on the headline feature)**

`cutctx/proxy/model_router.py` (300 lines, config-driven, with workload classifier, LiteLLM cost lookup, negative-delta protection, 16 passing tests) is bound to `proxy._model_router` at server boot (`server.py:1692-1703`) but **zero handlers call it**. The 9 live handler sites hardcode `model_routing_tokens_saved=0, model_routing_usd_saved=0.0`. The 5-source savings dashboard will show zero for the `model_routing` source for any production deployment that doesn't opt in to header-based telemetry. **The commercial claim of "5 savings sources" is only 3 sources in production.**

**Same issue applies to `self_hosted_prefix_cache_hits`** — also hardcoded 0 at all 9 sites.

**Fix:**
- Option A: Wire `proxy._model_router.maybe_route(model, request)` into the request path at the earliest point (after the cache miss, before the upstream call). Update the model name in-place if the router says downgrade.
- Option B: Add a real vLLM APC integration that reads upstream response headers (`x-cutctx-prefix-cache-hits` or similar from the vLLM sidecar) and populates `self_hosted_prefix_cache_hits`.
- Option C: Remove the `prefix_cache_self_hosted` and `model_routing` sources from the funnel until they're real.

### 6.2 Blocker 2 — Residency `verify()` is broken

**Severity: Critical (will fail any enterprise security review)**

`cutctx/security/residency_proof.py:319-324` (signer) signs `SHA-256(canonical_payload).digest()`. Line 226 (verifier) calls `public_key.verify(sig_bytes, payload)` — passing `payload` raw, not the digest. **In-process `prover.verify(prover.sign(attest))` returns False even for a signature the prover just produced.**

The documentation at `docs/data-residency.md` describes the digest-hash protocol (which matches the signer), so a third-party verifier reading the docs would work — but the in-process verify() function does not match.

**Fix:** Change `residency_proof.py:226` from `public_key.verify(sig_bytes, payload)` to `public_key.verify(sig_bytes, hashlib.sha256(payload).digest())`.

### 6.3 Blocker 3 — Air-gap, secrets, and EE memory service are stubs

**Severity: Critical (regulated-industry customers cannot deploy)**

- `cutctx/proxy/airgap.py:11-29` — only logs warnings; never called from `server.py`. `/v1/airgap/status` returns hardcoded payload (`routes/airgap.py:38-44`).
- `cutctx/proxy/routes/secrets.py:46, 54` — `list_secrets()` returns `[]`; `create_secret()` returns success-without-storage. No vault/AWS/GCP integration.
- `cutctx_ee/memory_service/api.py:65-75` — explicit TODOs unchanged. The `/v1/memory/review` endpoint is dead code.

**Fix:** Either implement these (significant work) or remove the routes and update the marketing/documentation to not claim these features.

### 6.4 Blocker 4 — Dashboard has no interactivity and React pages are static mockups

**Severity: High (enterprise admin needs to slice/dice data, not see hardcoded numbers)**

- `dashboard.html` — 0 `<input>`, 0 `<select>`, 0 spinner, 0 toast, 0 error UI. The only interactivity is Session/Historical toggle, Live Feed button, Theme toggle.
- `dashboard/src/pages/Overview.jsx:55-71` — hardcoded "4,289 Requests / min, 68.4% Compression Savings, $14.20/hr Budget Burn Rate". No API integration.
- `dashboard/src/pages/{Firewall,Memory}.jsx` — same pattern, hardcoded mockups.
- `dashboard/src/pages/Playground.jsx` — only page with real client-side logic.
- `/admin` route serves the static React mockup. An enterprise admin logging in would see "4,289 Requests / min" with no connection to the actual proxy state.

**Fix:** Either (a) make the React pages call real APIs and remove the hardcoded values, or (b) redirect `/admin` → `/dashboard` (the SSR dashboard which has real data), or (c) remove the React dashboard from the EE admin surface.

### 6.5 Blocker 5 — 6 documented CLI commands are unreachable

**Severity: High (operators following the help text get "No such command")**

`cutctx/cli/main.py:24-36` documents `cutctx audit, orgs, rbac, sso-test, config-check, bench` as top-level commands. `python -m cutctx.cli audit` returns `Error: No such command 'audit'`. The 6 files have orphan click decorators (`@click.group()` or `@click.command(...)` without `@main.group()`).

**Fix:** Add `@main.group()` to the top-level decorator in each of: `cutctx/cli/audit.py:24`, `orgs.py:23`, `rbac.py:23`, `sso_test.py:9`, `config_check.py:32`, `bench.py:70`.

### 6.6 Blocker 6 — Audit actor regression in `server.py:3401`

**Severity: High (audit attribution can still be forged)**

The Medium-33 fix (`54e6bb03`) hardened `cutctx/proxy/routes/admin.py:59-82` to use the `sso: > key: > admin` hierarchy, but `cutctx/proxy/server.py:3401` for `/stats/reset` still uses `request.headers.get("x-cutctx-user-id", "admin")` — the same client-controllable header the fix was meant to eliminate.

**Fix:** Apply the same `sso: > key: > admin` hierarchy from `routes/admin.py:59-82` to `server.py:3401`.

### 6.7 Blocker 7 — `CutctxMode` NameError regression (uncommitted rebrand work)

**Severity: High (test fails, code is broken at runtime)**

`cutctx/__init__.py:101-102` still exports `CutctxConfig, CutctxMode` (old names). `cutctx/client.py:938` references `CutctxMode.AUDIT` which no longer exists in `cutctx/config.py:13` (renamed to `CutctxMode`). `tests/test_config.py:TestCutctxMode::test_string_conversion` fails with `NameError`.

**Fix:** Either commit the rebrand atomically (rename `CutctxMode` → `CutctxMode` in `client.py:938`, `__init__.py:101-102`, and update the 2 untracked test files) or revert the uncommitted rebrand.

---

## 7. Prioritized Roadmap

### Critical (must close before paid enterprise release)

1. **Wire ModelRouter into the request path** (Blocker 1). Add `proxy._model_router.maybe_route(model, request)` call at the earliest point in the upstream-call flow. **Estimated 1-2 weeks.**
2. **Fix Residency `verify()` method** (Blocker 2). Change `residency_proof.py:226` to pass `SHA256(payload).digest()`. **Estimated 1 hour + tests.**
3. **Implement air-gap egress enforcement** (Blocker 3a). Add a domain blocklist + firewall interceptor that respects `CUTCTX_OFFLINE_MODE=1`. **Estimated 2-3 weeks.**
4. **Implement secrets management** (Blocker 3b). Either integrate HashiCorp Vault or AWS Secrets Manager SDK. **Estimated 2-3 weeks.**
5. **Remove TODOs from `cutctx_ee/memory_service/api.py:65-75`** (Blocker 3c). Either add real auth/audit or remove the `/v1/memory/review` endpoint. **Estimated 1 day.**
6. **Make dashboard interactive** (Blocker 4). Add search/filter/sort/loading/error states. Replace hardcoded React page values with real API calls. **Estimated 2-3 weeks.**
7. **Fix audit actor in `server.py:3401`** (Blocker 6). Apply the `sso: > key: > admin` hierarchy. **Estimated 1 hour + tests.**
8. **Commit rebrand atomically** (Blocker 7). Fix `CutctxMode` → `CutctxMode` references in `__init__.py:101-102`, `client.py:938`, plus the uncommitted `test_config.py` rebrand. **Estimated 1 day.**
9. **Fix the 6 unreachable CLI commands** (Blocker 5). Add `@main.group()` to the 6 orphan files. **Estimated 1 hour.**

### High (must close before public beta)

10. Add live vLLM APC detection (Option B from Blocker 1).
11. Add SAML SSO (use `python3-saml` or `pysaml2`).
12. Add MFA on admin (TOTP via `pyotp` or WebAuthn).
13. Add persistence to RBAC (move from in-memory to SQLite).
14. Add persistence to webhook subscriptions.
15. Add persistent dead-letter queue for webhook failures.
16. Add Stripe webhook secret enforcement (refuse empty secret).
17. Fix CRL check to fail-closed (or document the security implication).
18. Fix spend ledger default query to scope to caller's tenant.
19. Fix policy audit actor to use the same hierarchy as `routes/admin.py:59-82`.
20. Add per-source savings dashboard UI (consume the data that's already in the funnel).
21. Add tests for streaming.py (verify the PII redactor wiring end-to-end).
22. Update `.env.example` to document all `CUTCTX_*` env vars.
23. Update K8s `deployment.yaml:42` to use `ghcr.io/aryansingh/cutctx:0.26.0` (or whatever the canonical image is).
24. Update K8s `backup-cronjob.yaml:22` to pin alpine version (not `latest`).
25. Update K8s `secret.yaml:11` to use `hello@cutctx.dev` (not `hello@cutctx.dev`).
26. Update `gtm/soc2-roadmap.md:87` to remove the outdated "spend ledger has no backup" claim.
27. Expose `savings_tracker.verify_integrity` via CLI.

### Medium (close within 2 quarters)

28. Decide and document Ed25519 vs ECDSA license token — pick one and remove the other.
29. Decide and document air-gap semantics — if not implemented, remove from marketing.
30. Decide and document secrets management — if not implemented, remove the routes.
31. Wire the SSR dashboard's per-source cards to actually consume the data (currently they're rendered but the React pages don't).
32. Remove duplicate `_build_savings_breakdown` in `outcome.py:36-92` (dead code, per audit).
33. Wire `RequestOutcome.from_stream` callers (`streaming.py:767, 1589, 1802`) to pass the typed per-source fields directly (currently they default to 0 in the classmethod).
34. Add SCIM HTTP-level integration tests (only 2 unit tests on the store).
35. Add failover router tests (currently 0 dedicated tests).
36. Add admin endpoints integration tests (the 50+ admin routes in `admin.py` are mostly untested; only auth-gate smoke tests exist).
37. Re-enable LLM firewall by default for at least the public cloud tier.
38. Rebrand Go + Java SDKs (still use old "cutctx" name).
39. Add onboarding "Welcome" state for zero-traffic users.
40. Update `docs/spec/013-disaster-recovery.md:42` to use `cutctx_memory.db` (or the canonical filename).
41. Make the live feed drawer closable via Esc key.

### Low (close when bandwidth allows)

42. Add CSRF protection on admin surface.
43. Reduce dashboard hardcoded strings with i18n.
44. Add a `consistency_check` field to `report buyer` and `integrations status` that asserts `sum(savings_by_source_tokens) == delta_tokens_saved` for each row.
45. Add i18n for the React dashboard.
46. Remove the 154 pre-existing test failures (mostly rebrand leftovers and env deps).

---

## 8. Production Readiness Score: **60 / 100**

| Category | Weight | Score | Notes |
|---|---|---|---|
| Core proxy functionality | 20% | 18/20 | Full provider coverage, compression, semantic cache, all 5 sources wired at data layer |
| Reliability (health, retry, circuit breaker, graceful shutdown) | 15% | 11/15 | Health endpoints, 2 circuit breakers, graceful shutdown; corruption recovery quarantine |
| Observability (metrics, logging) | 10% | 6/10 | Prometheus implemented; audit chain verification; abuse alerts not delivered |
| Dashboard UX | 5% | 1/5 | SSR dashboard has per-source cards but no search/filter/sort/loading/error; React pages are static mockups |
| **5-source savings model end-to-end** | 20% | **4/20** | **Data layer complete, dashboard/CLI/durable history complete — 2 of 5 sources (model_routing, prefix_cache_self_hosted) never fire from live traffic. Model router is dead code.** |
| Test coverage | 10% | 6/10 | 7,041 pass / 154 fail / 256 skip; 27 SSO tests pass; missing tests for streaming.py |
| Packaging + deployment | 10% | 9/10 | Python + TS + Rust + Helm + Docker all present; tag pinned; ownership consistent |
| CLI surface | 5% | 1/5 | 20 of 26 documented commands work; 6 are unreachable |
| RBAC + security | 5% | 4/5 | 38 permissions, 4 roles, factory pattern enforced; default-ADMIN fail-open; audit actor regression at `server.py:3401` |

**Deductions (40 points lost):**
- Model router dead code (-12)
- 2 of 5 savings sources never fire (-6)
- Dashboard no interactivity + React static mockups (-6)
- 6 CLI commands unreachable (-4)
- Residency verify() broken (-4)
- Air-gap + secrets + EE memory TODOs unimplemented (-3)
- 154 test failures (mostly pre-existing, but includes NameError regression) (-2)
- Audit actor regression in server.py:3401 (-1)
- Rebrand leftovers (CutctxMode, etc.) (-1)
- K8s image refs / alpine:latest (-1)

---

## 9. Enterprise Readiness Score: **45 / 100**

| Category | Weight | Score | Notes |
|---|---|---|---|
| Authentication (admin + SSO + MFA + SAML) | 15% | 8/15 | Admin auth OK, OIDC working, SAML/MFA missing |
| Authorization (RBAC + per-endpoint + per-resource) | 10% | 7/10 | RBAC 38 permissions, factory pattern enforced; in-memory only; default-ADMIN fail-open |
| Audit logging (tamper-evident, comprehensive, retention) | 10% | 6/10 | Hash chain + /audit/verify + actor hierarchy + secret key enforcement; 14 of 22 enum events never emitted |
| Compliance (GDPR/CCPA/SOC2/HIPAA) | 15% | 9/15 | DSR endpoints; SOC2 docs now match; residency verify broken; spend ledger unbacked at line 87 of roadmap |
| Multi-tenancy isolation | 10% | 7/10 | Per-project SQLite + per-org spend; cross-tenant queries need filter |
| Encryption (at rest + in transit) | 5% | 2/5 | Fernet (AES-128) not AES-256; TLS depends on deployment |
| Security hardening (firewall, PII, secret detection) | 10% | 4/10 | Regex firewall off by default; streaming redactor wired but unverified; ML classifier model missing |
| **Residency / data sovereignty** | 10% | **1/10** | **Verify() broken; signer-verifier protocol mismatch; no actual proof** |
| **Air-gap / secrets management** | 10% | **0/10** | **Not implemented** |
| Admin UI workflows | 5% | 1/5 | SSR dashboard has data, no interactivity; React pages are mockups |
| Incident response + DR + backups | 5% | 2/5 | k8s/backup-cronjob now covers spend_ledger + audit.db; spend ledger note in roadmap outdated |

**Deductions (55 points lost):**
- Residency verify() broken (-9)
- Air-gap unimplemented (-9)
- Secrets stub (-7)
- Model router dead code (-7)
- Dashboard interactivity missing (-6)
- No MFA, no SAML (-6)
- Audit events not emitted (-4)
- Default-ADMIN fail-open (-3)
- Fernet not AES-256 (-2)
- Default admin key handling (-1)
- Static React mockups (-1)

---

## 10. OSS Readiness Score: **80 / 100**

| Category | Score | Notes |
|---|---|---|
| Core proxy + compression | 9/10 | Full provider coverage, 5-source model wired at data layer (2 sources require opt-in headers + dead router) |
| Reliability | 8/10 | Health endpoints, circuit breakers, graceful shutdown, Docker healthchecks, corruption recovery |
| Dashboard | 4/10 | SSR dashboard has per-source cards but no interactivity; React pages are mockups |
| Test coverage | 7/10 | 7,041 pass / 154 fail; savings module + EE routes have tests |
| Packaging + deployment | 9/10 | Python + TS + Rust + Helm + Docker + native binary; tag pinned |
| Security (out of the box) | 7/10 | Admin auth OK, EE routes gated, DSR endpoints, audit chain; but no MFA/SAML, residency verify broken |
| Documentation | 7/10 | SOC2 docs now match; some drift; `.env.example` is incomplete |

**Deductions (20 points lost):**
- Model router dead code (-6)
- React dashboard static mockups (-4)
- No search/filter/sort/loading/error in dashboard (-3)
- 6 CLI commands unreachable (-2)
- Residency verify broken (-2)
- Rebrand leftovers (-2)
- `.env.example` incomplete (-1)

---

## 11. Final Recommendation

### **NO-GO** for paid enterprise release in current state.

### **GO** for:

- **Public OSS release** with explicit "5 sources wired, 2 require additional integration" disclosure. The proxy + compression pipeline is solid and the 3 working sources (`provider_prompt_cache`, `cutctx_compression`, `semantic_cache`) are real.
- **Internal beta** for 1-3 design partners willing to sign an NDA + accept the security disclosure (the model-router dead code, the residency verify bug, the air-gap/secrets stubs).
- **Public beta** only after Critical items 1-9 (Blockers 1-7 in §6) are closed.

### Timeline to **GO** for paid enterprise readiness:

| Phase | Duration | What closes |
|---|---|---|
| **Phase 1: Moat-b1 completion** | 2-3 weeks | Critical Blocker 1 (wire ModelRouter; add vLLM APC detection) |
| **Phase 2: Security lockdown** | 1-2 weeks | Critical Blockers 2, 6, 7 (Residency verify, audit actor, rebrand) |
| **Phase 3: Stub removal** | 4-6 weeks | Critical Blocker 3 (air-gap enforcement, secrets backend, EE memory TODOs) |
| **Phase 4: UX + admin workflows** | 3-4 weeks | Critical Blockers 4, 5 (dashboard interactivity, CLI commands); High items 11-12 (MFA, SAML) |
| **Phase 5: SOC2 + ops** | 4-6 weeks | High items 13-27 (RBAC persistence, webhook persistence, DSR robustness) |

**Total: 14-21 weeks (3.5-5 months) to paid enterprise readiness.**

### The single most important next step

Close **Critical Blocker 1 (Model router is dead code)**. This is the highest-credibility issue: the headline commercial claim of "5 savings sources" is only 3 in production, and the most differentiated source (`model_routing`) is bound but never invoked. If discovered by any technical buyer, it ends the deal in the first 15 minutes. Add `proxy._model_router.maybe_route(model, request)` to the request path at the earliest point (after cache miss, before upstream call). **Estimated 1-2 weeks.**

The second most important is **Critical Blocker 2 (Residency `verify()` broken)** — a security reviewer at any enterprise customer will catch this in the first hour. **Estimated 1 hour + tests.**

---

## Appendix A — Top 5 Things to Tell the Customer Right Now

If a customer asks "is Cutctx production-ready?" the honest answer today is:

1. **The compression pipeline is real and working.** 5 sources tracked, USD attribution is buyer-grade accurate, dashboard shows per-source cards (in the SSR dashboard), durable history survives restart, CLI reports JSON always. **Verified end-to-end for 3 of 5 sources.**

2. **2 of the 5 savings sources are bound but not firing.** Provider cache, semantic cache, and Cutctx compression fire from real traffic. Self-hosted prefix cache and model routing are bound to the proxy but not invoked by any handler — they show 0 unless a client sets the `x-cutctx-*` opt-in headers. **The model router code exists (300 lines, 16 tests) but is not called from the request path. This is the next thing we need to ship.**

3. **The enterprise security surface has known gaps.** SSO OIDC is now working (after the 06-21 class-boundary fix). All EE routes are gated. DSR endpoints exist. Audit has actor hierarchy + secret key enforcement. **However, the residency `verify()` method is broken (signer hashes, verifier doesn't), air-gap mode is a no-op, secrets management is a stub, and the SOC2 roadmap still has unimplemented items marked honestly.** A serious enterprise security review will surface these.

4. **The admin UI is mixed.** The SSR dashboard at `/dashboard` shows real per-source stats. The React dashboard at `/admin` serves static mockups with hardcoded values (4,289 req/min, 68.4% compression). 6 of 26 documented CLI commands are unreachable.

5. **Backups are complete for spend + audit.** The `k8s/backup-cronjob.yaml` now backs up `cutctx_memory.db`, `spend_ledger.db`, and `audit.db` with 30-day retention. The memory store has corruption-recovery tests; the new savings store does.

**For a private design partner with disclosure, the proxy is usable today.** **For paid enterprise, the timeline is 3.5-5 months of focused work.** **For public OSS, the product is ready with a clearly-documented "2 of 5 sources require integration" caveat.**

---

## Appendix B — Reconciliation with Prior Audits

| Claim | 2026-06-20 Audit | 2026-06-21 Reconciliation | This Audit (2026-06-21 v3) |
|---|---|---|---|
| Blocker-1 (EE routes unauth) | Critical | (not in reconciliation) | **VERIFIED FIXED** — 14 factory calls, all routes gated |
| Blocker-2 (no DSR) | Critical | (not in reconciliation) | **VERIFIED FIXED** — `/v1/me/{export,delete}` exist |
| Blocker-3 (SOC2 docs) | High | (not in reconciliation) | **VERIFIED FIXED** — paths now resolve |
| Blocker-4 (SSO broken) | Critical | "TRUE" | **VERIFIED FIXED** — class boundary restored, 27/27 tests pass |
| Blocker-5 (3 of 5 sources don't fire) | High | "Closed" | **FALSE — Model router is dead code; only 3 of 5 sources actually fire** |
| Blocker-6 (/admin 404) | High | "Closed" | **PARTIALLY FIXED — 200 OK, but serves static mockup; soft regression vs SSR dashboard** |
| Blocker-7 (admin key logged) | High | (not in reconciliation) | **VERIFIED FIXED** — admin key printed to stderr only |
| Blocker-8 (audit secret) | High | (not in reconciliation) | **VERIFIED FIXED** — refuses to start without `CUTCTX_AUDIT_SECRET_KEY` |
| Blocker-9 (audit secret default) | High | (not in reconciliation) | **VERIFIED FIXED** — same as Blocker-8 |
| Blocker-10 (PII redactor unwired) | High | "FALSIFIED — re-auditor misread" | **VERIFIED WIRED** — `streaming.py:1175-1180` calls `wrap_stream()`; `server.py:2146` sets `proxy._streaming_redactor`; **but** 3 streaming tests fail with connection errors, so end-to-end behavior is unverified |
| Medium-33 (audit actor) | High | "FALSIFIED — re-auditor searched literal string" | **PARTIALLY FIXED — `routes/admin.py:59-82` uses `sso: > key: > admin`; but `server.py:3401` still uses `X-Cutctx-User-Id` header for `/stats/reset` audit event** |
| Medium-35 (docker-compose) | Low | "TRUE" | **VERIFIED FIXED** — both `docker-compose.native.yml:9, 31` now use `aryansingh/cutctx` |
| **NEW: Residency `verify()` broken** | (not detected) | (not detected) | **CRITICAL — confirmed broken in this audit** |
| **NEW: Model router dead code** | (not detected) | (closed in 61b5196a) | **CRITICAL — confirmed dead code in this audit** |
| **NEW: Air-gap, secrets, EE memory TODOs** | (not detected) | (not detected) | **CRITICAL — confirmed stubs in this audit** |
| **NEW: 6 CLI commands unreachable** | (not detected) | (not detected) | **HIGH — confirmed in this audit** |
| **NEW: `CutctxMode` NameError regression** | (not detected) | (not detected) | **HIGH — confirmed in this audit** |
| Production readiness score | 62 | 80 | **60** (down from 80 because model router dead code is a critical moat-b1 failure) |
| Enterprise readiness score | 38 | (not stated) | **45** |

**Bottom line:** The remediation series closed 19 of 46 audit items correctly. Three of the items the 2026-06-21 reconciliation claimed "closed" are actually **partially closed** (Blocker-5 model router, Medium-33 audit actor, Blocker-6 /admin serves mockup). Three new high-severity items were found that the prior audits missed entirely (Residency verify broken, Air-gap/secrets/EE memory stubs, 6 CLI commands unreachable, `CutctxMode` regression). The 2026-06-21 reconciliation's score of 80/100 was **too optimistic** because it trusted commit messages without verifying the live code paths.
