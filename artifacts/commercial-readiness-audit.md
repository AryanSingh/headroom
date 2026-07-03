# Commercial Readiness Assessment — Cutctx

**Date:** 2026-07-03  
**Commit:** `70758acc` (main)  
**Recommendation:** **Conditional Go**

---

## Executive Summary

Cutctx is **ready for design-partner and early adopter commercial engagements** with explicit conditions. The product has strong fundamentals: comprehensive pricing, clear open-core licensing, 7900+ tests, SSO/RBAC/audit in EE, and detailed go-to-market materials including outreach email templates, a demo script, and a 913-page product guide.

**Score: 6.3/10** — Functionally capable but operationally immature for enterprise procurement.

**Can sell today:** Builder (free), Team-tier design partners, enterprise POCs with engineering-led onboarding.

**Needs before full launch:** Backup automation, structured logging, SOC 2 evidence collection, payment collection flow, error tracking.

---

## 1. Pricing — Score: **8/10**

| Tier | Price | Target | Key Features |
|------|-------|--------|-------------|
| **Builder** | $0 | Individual engineers | Core compression, proxy, CLI, local dashboard |
| **Team** | $1,500/mo ($18K/yr) | Single team | Team analytics, usage reports, policy presets |
| **Business** | $3,500/mo ($42K/yr) | Platform teams | Workspace model, historical reports, K8s/Helm |
| **Enterprise** | Custom ($60K-$150K+/yr) | Regulated orgs | SSO, RBAC, audit, SCIM, air-gap |

**What exists:**
- ✅ Detailed pricing sheet (`artifacts/pricing-sheet.md`, 212 lines) with all four tiers
- ✅ Add-on pricing: onboarding ($5K), hardening ($3K), premium SLA ($10K/yr)
- ✅ Deal rules: design partner 30-40%, multi-year 10-15%, floor at 60% of list
- ✅ Quote skeleton template with commercial terms (Net 30, annual prepay)
- ✅ ROI framing with 4 value buckets (token savings, context utility, fewer retries, governance)

**Gaps:**
- ⚠️ No public pricing page on website — internal artifact only
- ⚠️ No self-serve checkout flow
- ⚠️ No usage-based pricing option

---

## 2. Billing — Score: **4/10**

**What exists:**
- ✅ EE billing module (`cutctx_ee/billing/`) with Stripe webhook handler
- ✅ License issuance and verification infrastructure
- ✅ `.env.example` documents billing env vars

**Gaps:**
- 🔴 **No automated payment collection** — pricing sheet states this as external work
- 🔴 **No self-serve portal** — all paid tiers require manual quoting
- 🟡 No invoicing automation (Net 30, tax handling stated as external)
- 🟡 No usage metering or overage tracking

**Verdict:** Suitable for manual enterprise deals; blocks self-serve growth.

---

## 3. Licensing — Score: **9/10**

**What exists:**
- ✅ Clear open-core model (`LICENSING.md`, 97 lines): Apache 2.0 OSS + Commercial License
- ✅ SPDX headers on every file (`Apache-2.0` or `LicenseRef-Cutctx-Commercial`)
- ✅ EE import shims transparently re-export commercial implementations
- ✅ OSS wheel excludes `cutctx_ee/` via `[tool.maturin] exclude`
- ✅ Anti-debug + binary integrity verification on EE
- ✅ Rust-side license verification with Ed25519 signatures

**Gap:**
- ⚠️ EE `.so` files need rebuild + sign before commercial distribution

**Verdict:** Industry best-practice open-core licensing.

---

## 4. Onboarding — Score: **7/10**

**What exists:**
- ✅ README "Get started (60 seconds)" with 4-step install
- ✅ Supports Claude Code, Codex, Cursor, Aider, Copilot, Windsurf, Zed, OpenCode
- ✅ `cutctx capabilities` command lists all algorithms and formats
- ✅ Quickstart for multiple agent types

**Gaps:**
- ⚠️ No interactive tutorial or guided demo
- ⚠️ No sandbox/demo environment for evaluation without installing
- ⚠️ First-time setup requires API keys — no try-without-keys path
- ⚠️ Rust toolchain needed for full source installation

---

## 5. Analytics — Score: **6/10**

**What exists:**
- ✅ Dashboard with 11-source savings attribution and history charts
- ✅ Agent Context Report (`cutctx report agent-context`)
- ✅ `/stats` endpoint with comprehensive telemetry
- ✅ Opt-in telemetry egress (`CUTCTX_TELEMETRY_EGRESS=1`)
- ✅ `cutctx learn --aggregate` for local anonymized summaries

**Gaps:**
- ⚠️ No product usage analytics (feature adoption, retention)
- ⚠️ No funnel analysis (install → configure → active use)
- ⚠️ No customer health scoring
- ⚠️ No BI integration (Snowflake/Tableau export)

---

## 6. Support — Score: **6/10**

**What exists:**
- ✅ Community Discord link in README
- ✅ Business-hours support for Team tier
- ✅ Premium SLA add-on ($10K/yr, 24/7, 1-hr critical response)
- ✅ Vulnerability reporting: `security@cutctx.dev`, 48hr acknowledgment
- ✅ Sales objection handling in `PRODUCT_GUIDE.md`

**Gaps:**
- ⚠️ No support portal or ticketing system
- ⚠️ No knowledge base / self-service help center
- ⚠️ No documented response times for non-premium tiers
- ⚠️ No status page for incident communication

---

## 7. Security — Score: **7/10**

**What exists:**
- ✅ SECURITY.md with supported versions and vulnerability reporting
- ✅ Admin auth + RBAC on all sensitive endpoints
- ✅ EE binary integrity verification (SHA-256 manifest)
- ✅ Anti-debug guard
- ✅ Rate limiting per identity
- ✅ Firewall module (PII/injection/jailbreak scanning)
- ✅ SSO with OIDC JWT verification
- ✅ Local-first architecture — data stays on-premises

**Gaps:**
- 🔴 No SOC 2 certification (controls documented, not audited)
- 🔴 No penetration testing evidence
- 🟡 No secrets manager for API keys
- 🟡 No audit logging of admin actions
- 🟡 No TLS enforcement in proxy

**Verdict:** Strong for OSS. SOC 2 is the enterprise procurement blocker.

---

## 8. Observability — Score: **5/10**

**What exists:**
- ✅ `/livez`, `/readyz`, `/health` endpoints
- ✅ `/metrics` endpoint
- ✅ Per-request latency/overhead/TTFB tracking
- ✅ `/stats` and `/stats-history` endpoints

**Gaps:**
- 🔴 No structured logging (all string-format)
- 🔴 No error tracking (Sentry/DataDog — zero references)
- 🟡 No request tracing
- 🟡 Health check lacks dependency probing
- 🟡 No alerting or notifications

**Verdict:** Weakest operations dimension. Enterprise customers will require structured logging and error tracking.

---

## 9. Documentation — Score: **8/10**

**What exists:**
- ✅ README.md (406 lines) with architecture diagram and install guide
- ✅ PRODUCT_GUIDE.md (913 lines) — sales guide with objection handling
- ✅ docs/ directory with architecture, benchmarks, security, compliance
- ✅ wiki/ with getting-started, quickstart, troubleshooting
- ✅ llms.txt for AI agents
- ✅ Legal: TERMS.md, PRIVACY.md, SECURITY.md, CODE_OF_CONDUCT.md
- ✅ Public docs site at cutctx.dev/docs

**Gaps:**
- ⚠️ No published API reference (OpenAPI/Swagger)
- ⚠️ No video tutorials or screencasts
- ⚠️ No unified documentation navigation

---

## 10. Reliability — Score: **6/10**

**What exists:**
- ✅ 7900+ tests, 19 dashboard E2E tests
- ✅ Stats caching with async lock
- ✅ Bounded replay queues
- ✅ AsyncIO throughout
- ✅ Graceful degradation for upstream API failures

**Gaps:**
- 🟡 64+ broad `except Exception` handlers
- 🟡 No load testing or throughput benchmarks
- 🟡 No circuit breakers for upstream APIs
- 🟡 No documented uptime history

---

## 11. Backup Strategy — Score: **3/10**

**What exists:**
- ✅ Local SQLite databases — filesystem-level backup possible
- ✅ `--stateless` mode for ephemeral deployments
- ✅ `cutctx memory export` for data portability

**Gaps:**
- 🔴 No documented backup/restore procedures
- 🔴 No automated backup scripts
- 🟡 No backup validation or recovery testing
- 🟡 No disaster recovery plan
- 🟡 No cross-region or off-site backup guidance

**Verdict:** Weakest dimension. Enterprise customers will demand backup automation.

---

## 12. Compliance — Score: **5/10**

**What exists:**
- ✅ SOC 2 controls documented (`docs/security/SOC2_CONTROLS.md`)
- ✅ Data residency docs (`docs/data-residency.md`)
- ✅ Audit compliance docs (`docs/audit-compliance.md`)
- ✅ HMAC-SHA256 evidence ledger with tamper detection
- ✅ Local-first architecture — data stays on-premises
- ✅ Privacy policy clearly describes data handling

**Gaps:**
- 🔴 SOC 2 not certified — controls not audited
- 🔴 No HIPAA, GDPR, or FedRAMP assessments
- 🟡 No DPA template
- 🟡 No subprocessor list
- 🟡 No compliance automation

---

## 13. Legal Pages — Score: **8/10**

**What exists:**
- ✅ TERMS.md, PRIVACY.md (101 lines), SECURITY.md (65 lines)
- ✅ CODE_OF_CONDUCT.md, LICENSING.md (97 lines)
- ✅ LICENSE (Apache 2.0), LICENSE-COMMERCIAL
- ✅ NOTICE (third-party notices)
- ✅ Commercial entity identified (Payzli Inc. / Cutctx Labs)

**Gaps:**
- ⚠️ No DPA template
- ⚠️ No standalone SLA.md
- ⚠️ No cookie policy (not applicable)

---

## 14. Marketing Readiness — Score: **7/10**

**What exists:**
- ✅ Outreach positioning (`artifacts/outreach-current-positioning.md`, 97 lines)
- ✅ P0/P1/P2 email templates for different buyer personas
- ✅ 913-page PRODUCT_GUIDE.md with sales objection handling
- ✅ Demo script (`artifacts/design-partner-demo-script.md`)
- ✅ Benchmarks with honest methodology
- ✅ Trendshift badge on GitHub
- ✅ Clear "Safe Claims" and "Claims That Need Care" boundaries

**Gaps:**
- ⚠️ No case studies or customer testimonials
- ⚠️ No public pricing page
- ⚠️ No published product roadmap
- ⚠️ No comparison page vs competitors

---

## 15. Enterprise Readiness — Score: **6/10**

**What exists (all EE):**
- ✅ SSO/OIDC admin authentication
- ✅ RBAC with permission model
- ✅ Audit log query and export
- ✅ Retention controls
- ✅ Fleet management APIs
- ✅ SCIM provisioning
- ✅ Air-gap deployment
- ✅ Multi-tenant org/workspace/project hierarchy
- ✅ Kubernetes and Helm deployment

**Gaps:**
- 🔴 SOC 2 not certified — enterprise procurement blocker
- 🔴 No penetration testing evidence
- 🟡 No documented HA/failover
- 🟡 No backup automation
- 🟡 No formal support SLA with response times

---

## 16. Competitive Differentiation — Score: **7/10**

**Strengths:**
- Provider-agnostic (Anthropic, OpenAI, Google, Bedrock)
- Reversible compression (CCR retrieves originals)
- Open-core license (Apache 2.0)
- Local-first (no data exfiltration)
- Full control plane (compression + policy + memory + attribution + replay + assurance)
- 280MB model vs LLMLingua2's 4200MB (15x smaller)
- Cross-agent (Claude Code, Codex, Cursor, Aider, Copilot)

**Vulnerabilities:**
- Only benchmarked against LLMLingua2
- EE required for enterprise features
- No published case studies
- README messaging split ("compression layer" vs "context control plane")

---

## Readiness Heatmap

```
Dimension                        Score     Bar
────────────────────────────────────────────────────
1.  Pricing                       8/10     ████████░░
2.  Billing                       4/10     ████░░░░░░  🔴
3.  Licensing                     9/10     █████████░
4.  Onboarding                    7/10     ███████░░░
5.  Analytics                     6/10     ██████░░░░
6.  Support                       6/10     ██████░░░░
7.  Security                      7/10     ███████░░░
8.  Observability                 5/10     █████░░░░░  🔴
9.  Documentation                 8/10     ████████░░
10. Reliability                   6/10     ██████░░░░
11. Backup Strategy               3/10     ███░░░░░░░  🔴
12. Compliance                    5/10     █████░░░░░  🔴
13. Legal Pages                   8/10     ████████░░
14. Marketing Readiness           7/10     ███████░░░
15. Enterprise Readiness          6/10     ██████░░░░
16. Competitive Differentiation   7/10     ███████░░░
────────────────────────────────────────────────────
OVERALL                        6.3/10     ██████░░░░
```

---

## Buyer Decision Matrix

| Buyer Type | Ready? | Action Required |
|------------|--------|-----------------|
| **Individual developer** (Builder) | ✅ **Go** | Install works, docs exist, free tier. No blockers. |
| **Small team** (Team, $1.5K/mo) | ⚠️ **Conditional** | Manual billing only. Needs discount approval. |
| **Platform team** (Business, $3.5K/mo) | ⚠️ **Conditional** | Needs K8s/Helm walkthrough. SOC 2 gap may arise. |
| **Regulated enterprise** (Enterprise, custom) | ❌ **No-Go** | Needs SOC 2, pen test, backup/DR, structured logging. |
| **VC/PE evaluation** | ✅ **Go** | Open-core story is strong. Competitive differentiation is clear. |

---

## Conditions for Full Launch

### 🔴 Must Fix Before Public Launch (P0)

| # | Condition | Dimension | Effort |
|---|-----------|-----------|--------|
| 1 | Backup automation — script to backup/restore all SQLite databases | Backup | 2 days |
| 2 | Structured JSON logging | Observability | 4 days |
| 3 | SOC 2 evidence automation from assurance ledger | Compliance | 5 days |
| 4 | Payment collection flow (Stripe checkout or manual invoicing) | Billing | 5 days |
| 5 | Error tracking integration (Sentry) | Observability | 2 days |

### 🟡 Recommended Before Q4 2026

| # | Priority | Dimension | Effort |
|---|----------|-----------|--------|
| 6 | Publish public pricing page | Marketing | 2 days |
| 7 | Document backup/restore procedures | Backup | 1 day |
| 8 | Penetration testing evidence | Security | Weeks (external) |
| 9 | Customer case study from design partner | Marketing | 3 days |
| 10 | Uptime/SLA documentation | Support | 1 day |

---

## Go/No-Go Recommendation

**⚠️ CONDITIONAL GO**

**Go for:** design-partner pilots, Team-tier commercial conversations, enterprise POCs with engineering-led onboarding.

**No-Go for:** broad enterprise go-to-market, self-serve paid tiers, regulated industry procurement.

The product is functionally ready. The gaps are operational: observability, backup, compliance certification, and payment automation. These are addressable in 2-4 weeks of focused work.

---

*Generated by commercial readiness assessment on 2026-07-03.*
