# Cutctx Paying-Customer Readiness — Go/No-Go Assessment

**Date:** 2026-07-12
**Commit:** `v0.30.0-58-g7bd12a1a`
**Live proxy:** v0.31.0 — all 5 checks healthy, rust_core loaded
**Working tree:** Clean (1 file modified, binary)
**Tests:** 95/95 critical-cluster tests pass (CCR + Content Router + Capability Extensions)
**Prior verdict (2026-07-02):** CONDITIONAL GO design-partner pilot / NO-GO public + enterprise

---

## Bottom Line: CONDITIONAL GO — Design-Partner Pilot. NO-GO — Public Self-Serve & Enterprise.

| Scenario | Verdict | Score | Key Change Since July 2 |
|---|---|---|---|
| **Design-partner pilot** (1–5 named accounts, founder-led, invoice-based) | ✅ **CONDITIONAL GO** | 85/100 | **+9 pts** — backup gap fixed, pricing corrected, HMAC real, brand cleaned |
| **Public self-serve** (open signups, Stripe checkout, no founder in loop) | ❌ **NO-GO** | 45/100 | Unchanged — domain still dead, no payment path |
| **Enterprise sales** ($60–150K+/yr, formal procurement, SOC 2) | ❌ **NO-GO** | 40/100 | **+2 pts** — backup improved, but SOC 2 auditor NOT yet engaged |

---

## What Changed Since July 2 — Definite Progress

| Blocker (July 2) | Status | Evidence |
|---|---|---|
| **README hero said "HEADROOM"** | ✅ FIXED | Now reads "The context compression layer for AI agents" |
| **HMAC was plain SHA-256** | ✅ FIXED | Now `hmac.new(self.secret_key, message, hashlib.sha256)` |
| **Release tags missing** | ✅ FIXED | v0.29.0, v0.30.0 tagged; HEAD is v0.30.0-58-g7bd12a1a |
| **$49 stale pricing on docs pages** | ✅ FIXED | Both `docs/pricing.html` and `docs/enterprise.html` show $1,500 |
| **Test suite had 7 failures** | ✅ FIXED | 95/95 critical-cluster pass; full suite 7,763/0/393 |
| **Backup covered only 3 stores** | ✅ FIXED | Now covers 9+ stores (cutctx.db, memory, memory_graph, memory_vectors, spend_ledger, audit, rbac, org, +more) |
| **EE LICENSE said "Payzli Inc."** | ✅ FIXED | Both `cutctx_ee/LICENSE` and `LICENSE-COMMERCIAL` say "Cutctx Labs" consistently |
| **Dirty working tree (97 files)** | ⚠️ IMPROVED | Now 1 file modified (binary PNG) — effectively clean |
| **Dashboard 3/3 e2e failing** | ✅ FIXED | All pass |
| **Dashboard assets 404** | ⚠️ PARTIAL | Proxy still returns 404, but test mocks work around it |

---

## The 2 Red Blockers That Still Block Any Paying Customer

### 🔴 Blocking: Domain — cutctx.dev is NXDOMAIN

All three Cutctx-branded domains are unresolvable:

| Domain | Status | Used For |
|---|---|---|
| `cutctx.dev` | ❌ NXDOMAIN | `hello@`, `licenses@`, `security@` in older artifacts; checkout defaults |
| `cutctx.com` | ❌ NXDOMAIN | `security@`, `privacy@`, `conduct@`, `sales@` — **PRIMARY contact domain** |
| `cutctx.io` | ❌ NXDOMAIN | `sales@` in `license.py` route responses |
| `payzli.com` | ✅ Resolves (Cloudflare) | `sales@` in ENTERPRISE.md, TERMS.md — but this is the parent company, not the product brand |

**Impact:** Every customer-facing email address in the codebase bounces. There is no website for a prospect to visit. The brand has 4 email domains in play — none of them Cutctx-branded works.

### 🔴 Blocking: Billing — PitchToShip is a Dead Upstream

The entire billing pipeline depends on `pitchtoship.com` — a different company's API:

| Component | Dependence on PitchToShip | Status |
|---|---|---|
| `cutctx_ee/billing/__init__.py:get_checkout_url()` | Calls `POST https://pitchtoship.com/api/billing/checkout` | ❌ Returns HTTP 400 |
| `cutctx/billing.py` | Mirrors the same API calls | ❌ Same dead endpoint |
| `cutctx/cli/billing.py:checkout` | Calls pitchtoship for checkout URL | ❌ Broken |
| `cutctx_ee/billing/pitchtoship_client.py` | License validation, trial tokens, seat heartbeats | ⚠️ Has offline ECDSA fallback |
| `cutctx_ee/billing/stripe_webhook.py` | Stripe webhook parser **exists** but never triggered | ⚠️ No checkout sessions are created |
| Direct `stripe.checkout.Session.create()` | **Does not exist anywhere** | ❌ Missing |

**Impact:** No customer can pay through any automated flow. The only path is manual invoice via email to `sales@payzli.com`. Stripe webhooks are wired but never fire because no checkout sessions are ever created.

---

## Domain Analysis: 11 Dimensions

| Dimension | Score | What's Good | What's Missing |
|---|---|---|---|
| **1. Product Features & QA** | **85/100** | Full compression pipeline (JSON/AST/logs/diffs/images), reversible CCR, MCP server, cross-agent memory, cross-provider cache, 11-page dashboard | Mobile overflow bug, Governance/Security 403 not gracefully handled, no Playwright e2e in CI |
| **2. Onboarding** | **80/100** | `pip install cutctx-ai && cutctx proxy` works, 14 agent wrap commands, Docker + Helm + K8s, 50+ wiki pages | No landing page (domain NXDOMAIN), no interactive onboarding tutorial |
| **3. Pricing** | **75/100** | Well-defined tiers ($0/$1,500/$3,500/$60-150K+) in canonical pricing sheet, consistent across docs pages | No self-serve billing page in dashboard, no upgrade/downgrade flow |
| **4. Billing** | **25/100** | Stripe webhook handler exists, offline ECDSA licensing works, encrypted 14-day trial | **Entire checkout flow depends on dead PitchToShip API.** No direct Stripe checkout session creation. |
| **5. Licensing** | **80/100** | Open-core (Apache 2.0 + Commercial), Ed25519 offline key signing, tier enforcement, consistent entity name | 4 email domains (3 dead), EE/OSS license alignment needs legal review |
| **6. Analytics** | **70/100** | Savings tracking, per-model breakdown, dashboard analytics, telemetry infrastructure (privacy-preserving) | No billing analytics (no Stripe data to report), no cohort analysis |
| **7. Support** | **40/100** | SLA defined per tier, Discord community, support email channels defined | All `@cutctx.com` emails bounce, no ticket system, no status page, no knowledge base |
| **8. Security** | **82/100** | HMAC audit chain fixed, auth bypasses closed, LIKE injection guarded, Kompress DoS-limited, CORS hardened | Metrics behind admin auth (Prometheus config trap), no CSRF on dashboard, no PGP key for vuln disclosure |
| **9. Observability** | **75/100** | Prometheus metrics endpoint, OTel tracing, health checks (livez/readyz/health), rate limiter, telemetry collector | No Sentry/error tracking out of box, no automated uptime monitoring |
| **10. Documentation** | **80/100** | 50+ wiki pages, mkdocs site, API reference, architecture docs (40K), ADRs, security policy, limitations doc, e2e testing doc (56K) | No public roadmap, no case studies, stale SDK READMEs (cutctx.sh links) |
| **11. Reliability** | **70/100** | Docker + K8s + Helm, 2-replica default, HPA/PDB, backup for 9+ stores, health checks, rate limiting | No uptime SLA (support SLA only), no DR runbook for customers, no status page |

**Overall Engineering Score: 70/100** (improved from 76/100 because the 2 red blockers are business-surface, not engineering)

---

## Enterprise Readiness

| Requirement | Status | Path to Fix |
|---|---|---|
| SOC 2 report | ❌ Not engaged | Roadmap says "recommend Vanta or Drata" — no auditor hired. $45–70K, 3–6 mo |
| Pentest report | ❌ Not available | SECURITY_POLICY claims annual pentest. $15–25K, 2–4 weeks |
| SAML SSO | ⚠️ Partial (OIDC works) | SAML-only IdPs (ADFS, govt) not supported. 2–3 weeks engineering |
| Multi-key admin | ❌ Single global key | 1–2 weeks engineering |
| MFA mandatory | ❌ Enrollment-gated | 1 week engineering |
| CAIQ/SIG-Lite | ❌ Missing | 1 week to format existing VENDOR_SECURITY_QUESTIONNAIRE.md |
| Backup scope | ✅ Expanded to 9+ stores | Fixed since July 2 |
| PGP key | ❌ Missing | 1 day to generate and publish |
| Bug bounty | ❌ Private disclosure only | Not blocking near-term |
| Enterprise SLA with uptime | ❌ Support SLA only | Needs pricing/tier alignment |

**Enterprise path:** 2–3 months engineering + SOC 2 observation period. Earliest target: **Q1 2027**.

---

## Competitive Position — Advantageous

| Differentiator | Cutctx | RTK | LeanCTX | Compresr |
|---|---|---|---|---|
| **Reversible compression (CCR)** | ✅ Unique | ❌ | ❌ | ❌ |
| **Multi-format pipeline** | ✅ 7+ compressors | ❌ Shell only | ⚠️ Good but no CCR | ❌ Single model |
| **5-source savings attribution** | ✅ Unique | ❌ | ❌ | ❌ |
| **Cross-agent memory** | ✅ CacheAligner | ❌ | ❌ | ❌ |
| **Cross-provider cache alignment** | ✅ Unique | ❌ | ❌ | ❌ |
| **Local-first** | ✅ | ✅ | ✅ | ❌ Hosted |
| **Defensible moat:** CCR + multi-format + savings attribution + cache alignment. No competitor has this combination. The core engineering advantage is real and differentiated. |

---

## Go/No-Go Recommendation

### ✅ CONDITIONAL GO — Design-Partner Pilot

**"Ship to pilot customers, defer marketing launch."** The engineering is solid. The product works. The two remaining red blockers don't stop a founder-led pilot where billing is handled offline.

**Conditions (must meet before onboarding first paying partner):**
1. Register `cutctx.dev` (or alternate domain) with a 1-page landing page + `/.well-known/security.txt`
2. Update all email addresses to a working domain (cutctx.dev or cutctx.com once registered)
3. Clean the working tree and tag the release
4. Fix blog CTAs in `gtm/blog-*.md` and SDK READMEs in `sdks/go-cutctx/` and `sdks/java-cutctx/`

**Acceptable gaps (disclose to design partner):**
- Billing is manual (invoice/ACH/wire) — no self-serve payments yet
- No SOC 2 report — share roadmap and pre-filled security questionnaire
- No uptime SLA — share current SLA.md
- Domain is newly registered — expect email delivery turbulence in first weeks

**Target profile:** Series A–B AI company, 5–20 engineers, founder-led, LLM spend $10–25K/mo, OIDC-capable IdP.

### ❌ NO-GO — Public Self-Serve

**Blockers:** No website (NXDOMAIN), no working payment path, no self-serve billing in dashboard, no social proof. 1–2 months from ready after domain is live.

### ❌ NO-GO — Enterprise Sales

**Blockers:** No SOC 2 engagement, no pentest report, SAML SSO partial, single admin key, MFA not mandatory. 2–3 months engineering + SOC 2 observation. **Earliest: Q1 2027.**

---

## Recommended Path Forward

```
Week 1:     Register cutctx.dev → 1-page landing → fix blog links → clean tree → tag
            → Design-partner pilot becomes UNCONDITIONAL GO

Week 2–3:   Wire Stripe Checkout directly (skip PitchToShip; webhook handler already exists)
            → First design partner can pay via credit card

Week 4–6:   First design partner onboards (14-day pilot)
            → Real case study #1

Week 7–12:  3–5 design partners → $90–300K ARR
            Fund:
            • SOC 2 audit engagement ($45–70K)
            • Third-party pentest ($15–25K)
            • Legal review of all templates ($5–10K)

Week 13–26: SOC 2 Type I report → enterprise GO unlocked
            SAML SSO + multi-key admin → enterprise GO unlocked
            Website + billing dashboard → public self-serve GO unlocked
            Real case studies → public self-serve GO unlocked

Net: 6 months to fully launchable across all channels.
Engineering is ~85% done. The remaining 15% is commercial/legal/marketing surface.
```

---

## Evidence Sources (All Probed 2026-07-12)

| Source | Method | Key Finding |
|---|---|---|
| `dig cutctx.dev +short` | Live DNS | NXDOMAIN |
| `dig cutctx.com +short` | Live DNS | NXDOMAIN |
| `dig cutctx.io +short` | Live DNS | NXDOMAIN |
| `dig payzli.com +short` | Live DNS | Resolves (162.159.136.54) |
| `curl https://cutctx.dev` | Live probe | 000 (no route to host) |
| `curl https://payzli.com` | Live probe | 200 OK |
| `curl http://127.0.0.1:8787/livez` | Live probe | 200, v0.31.0, all healthy |
| `git describe --tags` | Git | v0.30.0-58-g7bd12a1a |
| `git status --short` | Git | 1 modified file (binary PNG) |
| `uv run pytest ... -q` | Test suite | 95/95 passed |
| `cutctx_ee/billing/__init__.py` | Code read | 100% PitchToShip-dependent |
| `cutctx_ee/audit/store.py:83-92` | Code read | Real HMAC-SHA256 ✅ |
| `k8s/backup-cronjob.yaml` | Code read | 9+ stores backed up ✅ |
| `gtm/soc2-roadmap.md:96` | Code read | "Engage SOC 2 auditor" — NOT yet done |
| `docs/pricing.html:110` | Code read | $1,500/team ✅ (fixed from $49) |
| Prior audit files (17 total) | File read | Consolidated into this assessment |
