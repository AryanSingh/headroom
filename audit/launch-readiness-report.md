# Cutctx Launch-Readiness Report — 2026-07-18

**Product:** Cutctx v0.31.0 — Context compression layer for AI agents  
**Repo:** `main @ 7b726934` (2026-07-18 hardening, attribution, entitlement enforcement)  
**Live proxy:** `GET /livez` → 200, v0.31.0 (verified)  
**Test suite:** 9,176 collected (2026-07-17), full Rust + Python + dashboard gates pass  
**Prior verdict (2026-07-12):** CONDITIONAL GO design-partner pilot / NO-GO public + enterprise  
**Method:** Fresh multi-source analysis: 17 prior audit reports reconciled, live DNS probes, git log inspection, source grep on key modules, latest 2026-07-17/18 release-hardening commits verified.

---

## Executive Summary

| Channel | Verdict | Score | Δ since 2026-07-12 |
|---------|---------|-------|---------------------|
| **Design-partner pilot** (1–5 named accounts, founder-led, invoice-based) | ✅ **CONDITIONAL GO** | **85/100** | — (hold) |
| **Public self-serve** (open signups, Stripe checkout, no founder in loop) | ❌ **NO-GO** | **48/100** | +3 (entitlements fixed, plans page published) |
| **Enterprise sales** ($60–150K+/yr, SOC 2, procurement) | ❌ **NO-GO** | **42/100** | +2 (entitlement enforcement, release gates stronger) |

**One-line:** Engineering is ~88% complete and the technical moat is real. The two red blockers — dead domain and dead billing pipeline — prevent any automated customer acquisition. Design-partner pilot is viable today with founder-led offline billing.

---

## 15-Dimension Assessment

### 1. Product Features & QA — 86/100 ✅

**What works:**
- Full compression pipeline: SmartCrusher (JSON), CodeCompressor (AST, 27 languages), Kompress (ML text), Log/Diff/Search compressors, Image compression, Audio compression
- CCR reversible compression with TTL control and stateless mode
- Cross-provider: Anthropic, OpenAI, Google, Bedrock, Vertex via LiteLLM
- 11-page React dashboard (Overview, Savings, Orchestrator, Playground, Memory, Governance, Security, Firewall, Capabilities, Docs, Replay)
- MCP server (compress, retrieve, status)
- Cross-agent memory with vector (USearch/SQLite-vec) and graph backends
- Orchestration: deterministic routing, budget controls, policy bundles, fallback chains
- LLM Firewall (24 regex patterns), structured output validation
- 4 agent plugins (Claude Code, Codex, Claude.ai, Hermes, OpenClaw)
- SDKs: TypeScript (306 tests), Go, Python
- Multi-modal compression: images + audio inline

**Recent hardening (2026-07-18):**
- Safe Savings Mode (feature-flagged, read-only orchestration status model)
- Savings attribution integrity (schema v7, reconciled ledgers)
- Entitlement enforcement on request path (episodic/cross-agent memory fail-closed for free tier)
- Compression quality guarantees (expansion guard, Python code elision preserves `from __future__` imports)
- Per-request overhead: p50 2.5ms / p95 3.1ms (~443 req/s single-worker)
- Routing quality: 75/75 with zero unsafe downgrades

**Remaining product gaps:**
- **[Low]** Mobile overflow at 390px
- **[Low]** Governance/Security pages throw 403 on free tier (expected but ungraceful)
- **[Low]** Dashboard JS bundle 255 kB minified (within threshold after July 17 fix)

---

### 2. Pricing — 78/100 ⚠️

| Tier | Monthly | Annual | Target |
|------|---------|--------|--------|
| Builder | $0 | $0 | Individual engineers |
| Team | $1,500 | $18,000 | Single engineering team |
| Business | $3,500 | $42,000 | Platform teams |
| Enterprise | Custom | $60K–$150K+ | Security-sensitive orgs |

**What's good:**
- Four well-defined tiers with clear feature differentiation
- Feature matrix published in `docs/content/docs/plans.mdx`
- Pricing sheet in `artifacts/pricing-sheet.md` consistent across docs
- Add-ons defined (Onboarding $5K, Deployment Hardening $3K, Premium SLA $10K/yr, Security Review $7.5K)
- Deal rules documented (discount frameworks, guardrails, pilot terms)
- ROI framing ready (4 value buckets, 10-20% of measurable annual value)

**What's missing:**
- No pricing page on website (no website exists)
- No self-serve upgrade/checkout path
- No billing UI in dashboard

**Competitive pricing position:** Premium vs Helicone ($120/mo team) and Portkey ($199/mo team). Defensible due to CCR reversibility (unmatched), savings attribution, multi-format pipeline, and cross-agent memory.

---

### 3. Billing — 32/100 ❌

**🔴 Critical blocker — unchanged since July 2.**

| Component | Status | Detail |
|-----------|--------|--------|
| Stripe webhook handler | ✅ Exists | `cutctx_ee/billing/stripe_webhook.py` parses checkout events |
| Offline ECDSA licensing | ✅ Works | Ed25519 signed licenses with CRL revocation |
| License DB + seat tracking | ✅ Works | SQLite-backed, heartbeat APIs |
| **Direct Stripe Checkout Session.create()** | ❌ **Missing** | Does not exist anywhere in codebase |
| **PitchToShip upstream** | ❌ **Dead** | Returns HTTP 400; entire billing pipeline depends on it |
| **Self-serve checkout** | ❌ **Missing** | No customer can pay through an automated flow |
| **Dashboard billing UI** | ❌ **Missing** | No Billing.jsx, Subscription.jsx, Pricing.jsx |
| **Invoicing** | ⚠️ Manual only | Email sales@payzli.com, invoice/wire/ACH |

**Impact:** A customer literally cannot purchase Cutctx through any automated path. The only path is manual invoice via email to the parent company (Payzli Inc., not Cutctx).

---

### 4. Licensing — 82/100 ✅

- Open-core model: Apache 2.0 (engine, proxy, SDKs, CLI, MCP) + Commercial (control plane, enterprise modules)
- Authoritative boundary doc (`LICENSING.md`) maps every directory
- SPDX headers on all files: `Apache-2.0` or `LicenseRef-Cutctx-Commercial`
- Split-distribution model: OSS wheel excludes `cutctx_ee/` via `[tool.maturin] exclude`
- Entity name aligned: "Payzli Inc. (operating as Cutctx Labs)" throughout
- Ed25519 offline key signing for license validation
- Entitlement enforcement now wired for episodic/cross-agent memory on request path (2026-07-18 fix)
- CCR correctly labeled as Builder-tier (2026-07-17 fix)

**Gaps:**
- 4 email domains in play (cutctx.dev, cutctx.com, cutctx.io — all NXDOMAIN; payzli.com — resolves)
- Legal review of templates still needed per LICENSING.md

---

### 5. Analytics — 72/100 ⚠️

**What's built:**
- Per-model token/cost savings tracking
- Savings attribution with reconciled ledger (schema v7, 2026-07-18)
- Dashboard analytics (Overview, Savings by Model, Usage Reports)
- Privacy-preserving telemetry (opt-in, aggregate only, no content)
- Community savings snapshot page
- Prometheus metrics endpoint

**What's missing:**
- No billing analytics (no Stripe data to report)
- No cohort/retention analysis
- No cost allocation or showback reporting
- No measured vs estimated savings validation in production (shadow mode planned in remediation runbook)

---

### 6. Support — 40/100 ❌

| Tier | Channel | Coverage | Response |
|------|---------|----------|----------|
| Builder | Discord/Community | Best effort | No SLA |
| Team | Email | Business hours | Next business day |
| Business | Email + scheduled calls | Business hours | 4 hours |
| Enterprise | Priority channel + escalation | 24/7 critical | 1 hour critical |

**What exists:**
- SLA document published (`SLA.md` and `docs/content/docs/sla.mdx`)
- Severity levels defined (Critical/High/Medium/Low)
- Discord community channel active
- Documentation, issue templates, and contributing guide

**What's missing:**
- **🔴 All @cutctx.com emails bounce** — security@, privacy@, hello@, conduct@, sales@ all NXDOMAIN
- No ticket/helpdesk system (Zendesk, Intercom, etc.)
- No status page
- No knowledge base beyond docs site
- No SLAs for uptime/availability (support SLA only, not service SLA)
- No phone/Slack priority channel for paid tiers

---

### 7. Security — 83/100 ✅

**Fixed since July 2:**
- Auth bypass closure: `/dashboard`, `/api/savings`, `/api/models` stripped from loopback bypass
- LIKE injection guard: `_escape_like()` helper with `ESCAPE "\\"` clause
- Kompress DoS limit: `CUTCTX_KOMPRESS_MAX_WORDS` default 80K
- HMAC audit chain: now uses `hmac.new()` (was plain SHA-256 prefix)
- Audit CLI filters: safe `params=` dicts (was URL interpolation)
- CORS hardened
- Metrics behind admin auth (Prometheus config trap documented)
- Ruff lint cleanup: 56 auto-fixable errors resolved

**Current posture:**
- No credential storage
- Local-first architecture (compression runs in-process, no phone-home)
- HMAC-SHA256 audit hash chain with canonical framing
- Passthrough mode for sensitive content
- Admin API key auto-generation (no plaintext log)
- EE routes behind admin auth + RBAC
- MFA enforced on SSO routes (RFC 6238 TOTP)

**Gaps:**
- No pentest report (est. $15–25K, 2–4 weeks)
- No PGP key for vulnerability disclosure
- No bug bounty program (private disclosure only)
- No CSRF protection on dashboard
- Dependency scanning frequency unclear

---

### 8. Observability — 76/100 ⚠️

**What's built:**
- Prometheus metrics endpoint with admin auth
- OpenTelemetry tracing available
- Health endpoints: `/livez`, `/readyz`, `/health`
- Rate limiter (configurable)
- Request-level trace inspector in dashboard (`/transformations/traces/{request_id}`)
- Compression statistics exposed via `/stats`
- Circuit breaker (per-provider and pipeline-level)

**Gaps:**
- No Sentry/error tracking out of the box
- No automated uptime monitoring
- No centralized log aggregation
- No SIEM integration
- No alerting (abuse.py generates alerts but doesn't deliver them)

---

### 9. Documentation — 82/100 ✅

| Area | Status |
|------|--------|
| Quickstart | ✅ Multilingual (Python + TypeScript tabs), 5-minute claim |
| Full docs site | ✅ 44 pages via mkdocs/Next.js, architecture, API reference |
| Plans & Pricing | ✅ `plans.mdx` with feature matrix, consistent with pricing sheet |
| SLA | ✅ Published in `sla.mdx` |
| Security policy | ✅ SECURITY.md, VENDOR_SECURITY_QUESTIONNAIRE.md |
| Limitations | ✅ Documented |
| Architecture | ✅ Architecture, deployment, compression pipeline docs |
| Agent guides | ✅ Per-agent install docs (Claude Code, Codex, Cursor, etc.) |
| Enterprise docs | ✅ ENTERPRISE.md, air-gap deployment, enterprise install |
| OTel/Savings telemetry | ✅ Documented |

**Gaps:**
- No public roadmap
- No case studies
- No changelog accessible from docs site (exists in CHANGELOG.md only)
- Docs site not publicly accessible (no website)
- Some SDK READMEs reference stale `cutctx.sh` links

---

### 10. Reliability & Backup — 74/100 ⚠️

**What's built:**
- Docker multi-stage build with distroless option + HEALTHCHECK
- Docker Compose for local orchestration (Qdrant, Neo4j, etc.)
- Kubernetes manifests + Helm chart (2-replica default, HPA, PDB)
- Health probes (liveness, readiness, startup)
- Rate limiting on proxy
- Circuit breakers (per-provider + pipeline)
- Backup cronjob: covers 9+ stores (cutctx.db, memory, memory_graph, memory_vectors, spend_ledger, audit, rbac, org)
- 30-day S3 backup retention

**Gaps:**
- No disaster recovery runbook for customers
- No uptime SLA (support SLA only)
- No automated DR testing
- No status page
- No multi-region deployment guide

---

### 11. Onboarding — 76/100 ⚠️

**What's good:**
- `pip install cutctx-ai && cutctx proxy` — functional, tested
- 14 agent wrap commands documented
- Docker + Helm + K8s deployment paths
- MCP server auto-install (`cutctx mcp install`)
- Python + TypeScript SDKs published on PyPI and npm
- `cutctx init` creates config file

**What's broken or missing:**
- **🔴 No website** — `cutctx.dev`, `cutctx.com`, `cutctx.io` all NXDOMAIN
- **🔴 All @cutctx.com emails bounce**
- No `cutctx doctor` config validation command
- No first-run welcome/tutorial (38 CLI commands shown with no guidance)
- CLI help not grouped (no "Getting Started / Daily Use / Advanced" sections)
- No interactive onboarding tutorial

---

### 12. Compliance — 45/100 ❌

| Requirement | Status | Path |
|-------------|--------|------|
| SOC 2 Type II | ❌ Not engaged | SOC 2 roadmap exists ($45–70K, ~7.5 months including 6-month observation) |
| Penetration test | ❌ Not available | $15–25K, 2–4 weeks |
| CAIQ/SIG-Lite | ❌ Missing | 1 week to format existing security questionnaire |
| GDPR/CCPA DSR | ⚠️ Partial | DSR endpoints exist (Blocker-2 fix) |
| Data retention policies | ⚠️ Partial | RetentionManager exists but not default-enabled |
| SAML SSO | ⚠️ Partial (OIDC works) | SAML-only IdPs not supported (2-3 weeks eng) |
| Multi-key admin | ❌ Single global key | 1-2 weeks engineering |
| MFA mandatory | ⚠️ Enrollment-gated | MFA exists but not mandatory |

**Enterprise path:** 2–3 months engineering + SOC 2 observation → earliest Q1 2027.

---

### 13. Marketing & GTM — 48/100 ❌

**What exists:**
- Comprehensive GTM plan (`gtm/cutctx-comprehensive-acquisition-plan.md`)
- 3 blog posts (token costs, reversible compression, cross-agent memory)
- Case study template
- ROI calculator
- Outreach plan for SMBs
- Lead generation script
- Competitive analysis (Portkey, Helicone, LiteLLM, RTK, LeanCTX)
- Discord community

**What's missing:**
- **🔴 No website** — cannot be found via search, no social proof, no pricing page
- **🔴 No case studies** — no existing customers to reference
- Stale blog CTAs pointing to `cutctx.sh` (dead)
- No product hunt / launch plan
- No landing page for any tier
- No comparison page vs competitors
- No self-serve demo/sandbox
- No PLG motion

---

### 14. Enterprise Readiness — 44/100 ❌

| Capability | Status | Notes |
|------------|--------|-------|
| SSO (OIDC) | ✅ Works | Implemented, tested |
| SSO (SAML) | ⚠️ Partial | OIDC works; SAML-only IdPs not supported |
| RBAC | ✅ Works | 4 roles, 25+ permissions, 40+ admin routes |
| Audit logging | ✅ Works | HMAC hash chain, 8+ event types |
| Retention controls | ✅ Implemented | RetentionManager with configurable TTL |
| SCIM provisioning | ⚠️ Partial | APIs exist but not fully tested |
| Air-gap deployment | ✅ Supported | Offline licensing, pre-staged models |
| Fleet management | ⚠️ Partial | APIs exist; multi-instance not validated |
| SOC 2 | ❌ Not engaged | Roadmap only |
| Pentest report | ❌ Not available | — |
| Multi-key admin | ❌ Single global key | — |
| MFA mandate | ⚠️ Enrollment-gated | — |
| DR plan | ❌ Missing | — |
| VPC/private link | ✅ Supported | Local-first architecture |

---

### 15. Competitive Differentiation — Strong Moat

| Differentiator | Cutctx | RTK | LeanCTX | Helicone | Portkey | Compresr |
|---|---|---|---|---|---|---|
| Reversible compression (CCR) | ✅ **Unique** | ❌ | ❌ | ❌ | ❌ | ❌ |
| Multi-format pipeline (7+ compressors) | ✅ **Unique** | ❌ Shell only | ⚠️ Good | ❌ | ❌ | ❌ Single model |
| Savings attribution (5 sources) | ✅ **Unique** | ❌ | ❌ | ❌ | ❌ | ❌ |
| Cross-agent memory | ✅ **Unique** | ❌ | ❌ | ❌ | ❌ | ❌ |
| Cross-provider cache alignment | ✅ **Unique** | ❌ | ❌ | ❌ | ❌ | ❌ |
| Local-first deployment | ✅ | ✅ | ✅ | ❌ Hosted | ❌ Hosted | ❌ Hosted |
| Open-core | ✅ Apache 2.0 | ✅ | ✅ | ⚠️ Limited OSS | ⚠️ Limited OSS | ❌ |

**Risk:** If Helicone or Portkey add native compression, Cutctx's distribution moat narrows. What remains is compression depth (CCR + multi-format) + local-first governance. The core engineering advantage is real and defensible for 12–24 months.

---

## Red Blockers (Must Fix Before Any Customer Acquisition)

### 🔴 Blocker 1: Domain — cutctx.dev / cutctx.com are NXDOMAIN

| Domain | Status | Used For |
|--------|--------|----------|
| `cutctx.dev` | ❌ NXDOMAIN | hello@, licenses@, checkout defaults |
| `cutctx.com` | ❌ NXDOMAIN | **Primary brand domain** — security@, privacy@, conduct@, sales@ |
| `cutctx.io` | ❌ NXDOMAIN | sales@ in license.py routes |
| `payzli.com` | ✅ Resolves | Parent company — not product brand |

**Impact:** No website for prospects. All customer-facing email bounces. The brand has 4 email domains — none of the Cutctx-branded ones work. This is a zero-trust signal to any potential buyer.

### 🔴 Blocker 2: Billing Pipeline — PitchToShip Dead Upstream

| Component | Dependence | Status |
|-----------|-----------|--------|
| `get_checkout_url()` | Calls pitchtoship.com API | ❌ HTTP 400 |
| License validation (PitchToShip path) | Calls pitchtoship.com | ❌ Broken |
| Stripe webhook handler | Exists but never triggered | ⚠️ Needs checkout sessions |
| Direct Stripe Checkout.Session.create() | **Does not exist anywhere** | ❌ Missing |
| Self-serve payment path | None | ❌ Missing |

**Impact:** No customer can pay through any automated flow. The only path is manual invoice via email to a non-product-branded parent company.

---

## Go/No-Go Recommendation

### ✅ CONDITIONAL GO — Design-Partner Pilot (85/100)

**"Ship to 1–5 named pilot accounts, defer marketing launch."**

The engineering is strong, the product works, and the technical moat is real. The two red blockers don't stop a founder-led pilot where billing is handled offline.

**Conditions (must meet before first paying partner onboarding):**
1. Register `cutctx.dev` (or alternate) with a 1-page landing page + `/.well-known/security.txt`
2. Update all email addresses to a working domain
3. Tag the release (working tree is clean per latest audit)
4. Fix blog CTAs and stale SDK README links

**Acceptable gaps (disclose to pilot partner):**
- Billing is manual (invoice/ACH/wire) — no self-serve
- No SOC 2 — share roadmap + pre-filled security questionnaire
- No uptime SLA — share current support SLA
- Domain is new — expect email delivery turbulence in first weeks

**Target profile:** Series A–B AI company, 5–20 engineers, LLM spend $10–25K/mo, OIDC-capable IdP.

### ❌ NO-GO — Public Self-Serve (48/100)

**Blockers:** No website, no payment path, no self-serve billing, no social proof. 4–6 weeks from ready after domain registration + Stripe checkout wiring.

### ❌ NO-GO — Enterprise Sales (42/100)

**Blockers:** No SOC 2 engagement, no pentest, SAML partial, single admin key, MFA not mandatory. 2–3 months engineering + 6-month SOC 2 observation. Earliest: **Q2 2027**.

---

## Recommended Path Forward

```
Week 1:     Register cutctx.dev → 1-page landing → fix email/blog links → tag release
            → Design-partner pilot becomes UNCONDITIONAL GO

Week 2–3:   Wire Stripe Checkout directly (skip PitchToShip; webhook handler exists)
            → First design partner can pay via credit card

Week 4–8:   Onboard 3–5 design partners (14-day pilots)
            → Real case studies, real social proof

Week 9–16:  $90–300K ARR from pilot partners
            Fund:
            • SOC 2 audit engagement ($45–70K)
            • Third-party pentest ($15–25K)
            • Legal review of templates ($5–10K)

Week 17–30: SOC 2 Type II report (6-month observation inherent)
            SAML SSO + multi-key admin → enterprise GO unlocked
            Website + billing dashboard → public self-serve GO unlocked

Net: 6–9 months to fully launchable across all channels.
Engineering is ~88% complete. The remaining 12% is commercial/legal/marketing surface.
```

---

## Verification Sources

| Source | Method | Key Finding |
|--------|--------|-------------|
| `dig cutctx.dev +short` | Live DNS | NXDOMAIN |
| `dig cutctx.com +short` | Live DNS | NXDOMAIN |
| `curl http://127.0.0.1:8787/livez` | Live probe | 200, v0.31.0, all healthy |
| `git log --oneline -20` | Git | Last commit 7b726934 (2026-07-18 hardening) |
| `pytest ... -q` | Test suite | 9,176 collected (July 17), full gates pass |
| `cutctx_ee/billing/pitchtoship_client.py` | Code read | Dead upstream dependency |
| `cutctx/proxy/server.py` | Code read | Entitlement enforcement wired (July 18 fix) |
| `cutctx_ee/entitlements.py` | Code read | CCR labeled Builder (July 17 fix) |
| `docs/content/docs/plans.mdx` | Code read | Published feature matrix |
| `audit/verified-remediation-2026-07-17.md` | Audit read | 6 claims refuted, 5 confirmed, all remediated |
| `audit/release-readiness-audit-2026-07-17.md` | Audit read | Local gates pass; staging evidence required |
| `audit/go-no-go-final.md` | Audit read | Prior verdicts consistent with current analysis |
| `gtm/soc2-roadmap.md` | Code read | SOC 2 not yet engaged |
| `k8s/backup-cronjob.yaml` | Code read | 9+ stores backed up |
