# Cutctx v0.30.1 — Go/No-Go Assessment for Paying Customers

**Date:** 2026-07-05
**Data Sources:** Docs audit (6 explorers), QA playbook (177 tests), audit/fix cycle (25+ reports), permissions audit (~80 routes), product maturity audit (8 dimensions), billing/license/support audit

---

## Executive Summary

**Recommendation: NO-GO for paying customers**

Cutctx has a strong technical foundation — the compression engine works (78% at 0.999 F1), the pipeline is well-architected, the enterprise feature set is ambitious, and the entitlements/RBAC/audit infrastructure is genuinely production-grade. The codebase shows real engineering investment.

However, **3 Critical blockers and 7 High blockers** make it unsafe to accept money today. The most serious: the billing system is wired to a dead third-party domain, the product domain (`cutctx.com`) doesn't exist, and the license validation mechanism is a no-op. A paying customer would not be able to complete a purchase, activate a license, or visit the product website.

**Status:** Technically impressive, commercially incomplete.

---

## 1. Onboarding

| Criterion | Assessment | Evidence |
|-----------|-----------|----------|
| Install to first value | **7-12 minutes** (not the documented 60s) | Product audit: bare install needs `[proxy]` extra, proxy config, API key setup |
| First-run experience | No guided tour, no wizard | `cutctx setup` exists but is not in "Get started" |
| Documentation accuracy | 9 inaccuracies found, 5 fixed | SDK wrapper names, feature counts, retired features |
| Error messages during install | Clean Click validation | Tested: 5/5 error scenarios graceful |
| MCP configuration | Not installed by default | `cutctx mcp install` is a separate step |

**Grade: C — Functional but friction-filled. False time-to-value claims erode trust.**

---

## 2. Pricing

| Criterion | Assessment |
|-----------|-----------|
| Published pricing | ✅ `docs/pricing.html` exists and is polished |
| Tier structure | ✅ 4 tiers (Builder/Team/Business/Enterprise) well-defined |
| Internal pricing sheet | ✅ `artifacts/pricing-sheet.md` detailed |
| CTA destinations | ❌ **CRITICAL** — All CTAs point to: dead domain (`cutctx.com`), wrong brand (`payzli.com`), non-existent GitHub org (`github.com/cutctx`) |
| Business tier omitted | ⚠️ Public pricing page hides Business tier from card grid |
| Pricing accuracy | ⚠️ ROI case studies are templates, not real customer stories |

**Grade: D — Polished UI pointing at dead destinations.**

---

## 3. Billing

| Criterion | Assessment |
|-----------|-----------|
| Stripe webhook handler | ✅ Real, security-conscious (HMAC verification, price-ID tier resolution) |
| Stripe env vars configured | ❌ No Stripe account wired — code is dormant |
| PitchToShip integration | ❌ **CRITICAL** — `pitchtoship.com` resolves to a different company's landing page, not Cutctx's billing server |
| CLI checkout flow | ❌ Opens PitchToShip URL — customer cannot complete purchase |
| CLI portal flow | ❌ Same dead domain |
| `cutctx billing checkout --tier team` | ❌ Opens `https://pitchtoship.com/checkout?plan=starter` — owned by a different company |
| Fallback behavior | ❌ Falls back to static marketing page instead of failing loud |

**The billing code is well-written. The destination is dead. A paying customer cannot pay.**

**Grade: F — The entire revenue pipeline terminates at a domain owned by a different company.**

---

## 4. Licensing

| Criterion | Assessment |
|-----------|-----------|
| License token generation | ✅ Three formats, all signed (Ed25519, HMAC, CLI) |
| License validation | ❌ **CRITICAL** — watermark verification has a real bug: canary SHA hash is computed and discarded, so canary strings don't trace back to license IDs |
| License activation | ❌ Calls `pitchtoship.com/v1/license/validate` — dead domain |
| Offline license support | ✅ Local HMAC-protected cache with tamper detection |
| Entitlement enforcement | ✅ 66 features × 4 tiers, fail-closed defaults |
| License DB | ✅ Real SQLite store with tables for licenses, activations, revocations |
| CLI license status | ✅ Shows tier, trial remaining, available features |
| `cutctx license activate` | ❌ Cannot activate — sends request to dead domain |

**Grade: D — Local licensing infrastructure is solid. Server-side activation is broken. The canary traceability bug defeats the watermark's purpose.**

---

## 5. Analytics

| Criterion | Assessment |
|-----------|-----------|
| Telemetry | ✅ Privacy-preserving, opt-in, differential privacy implemented |
| Savings tracking | ✅ 11 savings sources tracked with attribution |
| Dashboard | ✅ 10 React pages, served at `/dashboard` |
| Dashboard accessibility | ⚠️ Admin-gated, loopback-only — cannot share/demo remotely |
| Reporting | ✅ `cutctx report buyer` with JSON/CSV/Markdown |
| No analytics data | ⚠️ `savings --stats-only` returns "No sessions recorded" |
| `cutctx perf` | ✅ 4120 requests analyzed, 23.2M tokens saved |

**Grade: B — Well-designed analytics, but dashboard access limitations hinder demos.**

---

## 6. Support Flows

| Criterion | Assessment |
|-----------|-----------|
| SLA defined | ✅ Tier-by-tier: Builder (none), Team (NBD), Business (4hr), Enterprise (1hr critical) |
| SLA credits/refunds | ❌ No section defining service credits for SLA misses |
| Support email | ❌ `hello@cutctx.dev` — NXDOMAIN, all mail bounces |
| Support channels | ❌ No support portal, ticketing system, or chat |
| Documentation | ✅ Real runbook, manual testing guide |
| Community | ✅ Discord link in README |
| Escalation procedures | ❌ Not documented |

**Grade: D — SLA exists on paper but has no delivery mechanism. No way for customers to actually reach support.**

---

## 7. Security

| Criterion | Assessment |
|-----------|-----------|
| Admin auth on API routes | ⚠️ 70/80 routes protected (3 fixed this session) |
| RBAC | ✅ 4 roles, 40+ permissions, fail-closed |
| Entitlement enforcement | ✅ 66 features, fail-closed on unknown |
| MFA/TOTP | ✅ RFC 6238 with replay protection |
| SSO/OIDC | ✅ JWT, JWKS, introspection |
| SAML SSO | ❌ **Missing** — enterprise procurement blocker |
| Exception leak in 500s | ✅ Fixed (8 sites) |
| Version header leak | ✅ Fixed (env-gated) |
| `/health` config leak | ❌ **CRITICAL** — returns full proxy config without auth |
| CCR retrieval auth | ❌ **HIGH** — `/v1/retrieve/*` missing admin auth (4 routes) |
| License validation | ❌ **CRITICAL** — no-op in watermark traceability |
| Watermark canary | ❌ **Bug** — hash computed and discarded, can't trace to license |
| CRL revocation | ❌ Fails open on network errors |
| `.env.local` secrets | ✅ Ignored by .gitignore |
| Anti-debug | ✅ macOS `PT_DENY_ATTACH`, Linux TracerPid |
| Binary integrity | ✅ HMAC-signed manifest |

**Grade: D — Auth framework is excellent, but 5+ unfixed vulnerabilities exist, including 2 CRITICAL.**

---

## 8. Observability

| Criterion | Assessment |
|-----------|-----------|
| OpenTelemetry integration | ✅ Real OTLP HTTP + console exporters |
| Langfuse tracing | ✅ `cutctx proxy --langfuse` with OTEL exporter |
| Prometheus metrics | ✅ `/metrics` endpoint with metric catalogue |
| Metric catalogue docs | ✅ `docs/observability.md` with full metric reference |
| Error tracking | ❌ No Sentry/Datadog integration |
| Health checks | ⚠️ `/health` always returns 200 even when degraded |
| Logging | ✅ Structured JSONL via `--log-file` |

**Grade: B — Observability is a strength. Missing error tracking is the only gap.**

---

## 9. Documentation

| Criterion | Assessment |
|-----------|-----------|
| README | ✅ Comprehensive, well-structured |
| PRODUCT_GUIDE | ✅ Very comprehensive (912 lines) |
| CLI `--help` | ✅ Excellent — all 30+ commands documented |
| API documentation | ❌ `/openapi.json` returns 500 — no auto-generated API docs |
| Installation guide | ✅ Real `docs/content/docs/installation.mdx` |
| Architecture docs | ✅ `docs/project-architecture.md` reference |
| Troubleshooting guide | ✅ Referenced in docs index |
| Manual testing guide | ✅ 322 lines, step-by-step |
| Operational runbook | ✅ 301 lines, deployment checklist |

**Grade: A — Documentation is a clear strength. Only `/openapi.json` is broken.**

---

## 10. Reliability

| Criterion | Assessment |
|-----------|-----------|
| Test suite | 1344 pass, 0 fail, 29 skipped |
| Circuit breaker | 3 failures → 60s bypass |
| Load testing | ❌ Never performed |
| Concurrency testing | ❌ Singleton pipeline not tested under load |
| `memory stats` crash | ✅ Fixed (datetime offset bug) |
| Pipeline error recovery | ⚠️ Circuit breaker tested? No forced failure test done |
| Streaming edge cases | ⚠️ SSE chunk boundaries, client disconnect not tested |
| Database corruption | ❌ No corruption detection in stores |

**Grade: C — Good unit test coverage but no load/concurrency/stress testing.**

---

## 11. Backup Strategy

| Criterion | Assessment |
|-----------|-----------|
| CronJob exists | ✅ Daily backup via `k8s/backup-cronjob.yaml` |
| What's backed up | Memory DB, spend ledger, audit DB (3 of 13+ stores) |
| What's NOT backed up | RBAC, billing, license, webhook DLQ, knowledge graph, fleet, org, retention, SCIM, secrets, policy stores |
| S3 destination | ✅ Hardcoded `cutctx-backups` bucket |
| Encryption | ⚠️ No application-level encryption; S3 server-side only |
| `restore` command | ❌ **CRITICAL** — no restore procedure exists anywhere |
| Monitoring/alerting | ❌ No backup failure alerts |
| Off-cluster copy | ❌ No Glacier/archive tier |

**Grade: F — Daily backup of 3/13 stores, no restore path, no monitoring. A disk failure is unrecoverable.**

---

## 12. Compliance

| Criterion | Assessment |
|-----------|-----------|
| SOC 2 | ❌ Not started — no auditor engagement, no controls evidence collection |
| GDPR | ⚠️ DSR endpoints exist, DPA template exists, but `cutctx.com/sub-processors` URL is dead |
| HIPAA | ❌ No BAA, not pursued |
| Penetration testing | ❌ Never performed |
| Data residency | ✅ Verification proof endpoints implemented |
| Privacy policy | ✅ Real, covers local-first architecture |
| Terms of service | ⚠️ Draft — marked as needing legal review |

**Grade: D — GDPR DSRs are the only compliance area that's production-ready. Everything else is absent or draft.**

---

## 13. Legal Pages

| Criterion | Assessment |
|-----------|-----------|
| TERMS.md | ⚠️ Draft — explicitly marked "must be reviewed by qualified legal counsel" |
| PRIVACY.md | ✅ Substantive, covers local-first architecture |
| LICENSING.md | ✅ Definitive open-core boundary |
| SLA.md | ✅ Real tier-by-tier, missing credits/refunds |
| DPA template | ✅ Real, references dead `cutctx.com/sub-processors` |
| MSA template | ✅ Real, `[JURISDICTION]` placeholders |
| Legal entity consistency | ❌ `DPA_TEMPLATE.md` says "Cutctx, Inc.", `LICENSING.md` says "Payzli Inc. (operating as Cutctx Labs)" |
| Security policy | ✅ Coordinated disclosure documented |
| DMCA template | ✅ Present |
| Leak response runbook | ✅ Present |

**Grade: C — Templates exist but entity name is inconsistent, TERMS.md is explicitly a draft, and DPA references a dead URL.**

---

## 14. Marketing Readiness

| Criterion | Assessment |
|-----------|-----------|
| Product domain (`cutctx.com`) | ❌ **CRITICAL** — NXDOMAIN, 30+ files reference dead URL |
| Alternate domain (`cutctx.dev`) | ❌ Also NXDOMAIN |
| Homepage | ❌ No `docs/index.html` |
| Pricing page | ✅ Polished, links to dead destinations |
| Enterprise page | ✅ Polished, links to dead destinations |
| Case studies | ❌ Template only — no real customer stories |
| ROI calculator | ✅ Real interactive calculator |
| Blog | ✅ Directory exists |
| GTM strategy | ✅ `gtm/` directory with outreach plans |
| GitHub org | ❌ `github.com/cutctx` doesn't exist |
| Discord | ✅ Link in README works |

**Grade: F — The product has no home on the internet. Every external link in the repo resolves to NXDOMAIN or a different company's website.**

---

## 15. Enterprise Readiness

| Criterion | Assessment |
|-----------|-----------|
| SSO (JWT/OIDC) | ✅ Implemented |
| SAML | ❌ Missing — procurement blocker |
| RBAC | ✅ 4 roles, 40+ permissions, fail-closed |
| MFA | ✅ TOTP RFC 6238 |
| SCIM provisioning | ✅ Users + Groups CRUD |
| Audit logging | ✅ HMAC-chained, queryable, JSONL export |
| Fleet management | ✅ Heartbeat-based |
| Multi-tenant org hierarchy | ✅ Org → Workspace → Project → Agent |
| Helm chart | ✅ `helm/cutctx/Chart.yaml` exists |
| Air-gap mode | ✅ Implemented |
| Enterprise license enforcement | ❌ **CRITICAL** — license validation is a no-op |
| Data residency | ✅ Proof endpoints exist |

**Grade: C — Most enterprise features are present. The license enforcement no-op is a dealbreaker for procurement.**

---

## 16. Competitive Differentiation

| Differentiator | Assessment |
|----------------|-----------|
| Reversible compression (CCR) | ✅ True competitive moat — no competitor has this |
| Cross-agent memory | ✅ Unique — Claude ↔ Codex memory sharing |
| Content-type routing | ✅ Auto-detects JSON, code, logs, diffs, text |
| Local-first | ✅ No cloud dependency for compression |
| Open-core | ✅ Full compression pipeline free |
| Cross-provider | ✅ Anthropic + OpenAI + Bedrock + Vertex + 100+ via LiteLLM |
| Enterprise features | ⚠️ Present but unmonetizable (license no-op) |
| Marketing credibility | ❌ Undermined by 18x overstatement of compression ratios |

**Grade: B — Technical differentiation is real. Marketing credibility is the weak point.**

---

## Go/No-Go Heatmap

| Area | Score | Go? |
|------|-------|-----|
| Onboarding | C | ⚠️ Conditional |
| Pricing | D | ❌ No |
| Billing | **F** | **❌ CRITICAL** |
| Licensing | D | ❌ No |
| Analytics | B | ✅ Yes |
| Support | D | ❌ No |
| Security | D | ❌ No |
| Observability | B | ✅ Yes |
| Documentation | A | ✅ Yes |
| Reliability | C | ⚠️ Conditional |
| Backup | **F** | **❌ CRITICAL** |
| Compliance | D | ❌ No |
| Legal | C | ⚠️ Conditional |
| Marketing | **F** | **❌ CRITICAL** |
| Enterprise | C | ⚠️ Conditional |
| Competitive Diff | B | ✅ Yes |
| **Overall** | **D+** | **❌ NO-GO** |

---

## Recommendation: NO-GO

### Critical blockers (must fix before accepting any paying customer)

| # | Blocker | Area | Fix Effort |
|---|---------|------|------------|
| 1 | **No product domain** — `cutctx.com` and `cutctx.dev` are NXDOMAIN. README, legal docs, pricing page, and 30+ source files link to a website that doesn't exist. | Marketing/Legal | **1 week** (DNS + static site) |
| 2 | **Billing is wired to a dead domain** — `pitchtoship.com` belongs to a different company. A customer cannot complete a purchase. | Billing | **2-3 weeks** (Stripe activation + CLI updates) |
| 3 | **No restore path for backups** — Daily S3 snapshots exist, but there's no way to restore them. Disk failure = data loss. | Reliability/Backup | **1 week** (restore CLI command) |

### High blockers (must fix before GA launch)

| # | Blocker | Area | Fix Effort |
|---|---------|------|------------|
| 4 | **Support email bounces** — `hello@cutctx.dev` is NXDOMAIN. No customer can reach support. | Support | **1 day** (email provider setup) |
| 5 | **License validation is a no-op** — Canary watermark doesn't trace to license IDs. Server-side activation calls dead domain. | Licensing | **1-2 weeks** |
| 6 | **Legal entity mismatch** — `Payzli Inc.` vs `Cutctx, Inc.` — which is the contracting party? | Legal | **1 day** (choice + consistency pass) |
| 7 | **`/health` leaks full config** — Returns every proxy knob without auth | Security | **1 day** (route split) |
| 8 | **CCR retrieval endpoints have no admin auth** — Any TEAM-tier user can read cached originals | Security | **1 day** (auth dependency) |
| 9 | **Marketing claims overstate performance** — "87% Avg" is 18x above production median | Marketing | **1 day** (correction) |
| 10 | **Stripe webhook is dormant** — Code exists but no Stripe account is wired | Billing | **1 week** (Stripe account + env vars) |

### What's already production-ready

- ✅ Compression engine (78% at 0.999 F1 on real data)
- ✅ CLI (34/34 commands functional)
- ✅ RBAC (40+ permissions, fail-closed)
- ✅ Entitlements (66 features × 4 tiers, fail-closed)
- ✅ MFA/TOTP (RFC 6238)
- ✅ Telemetry (privacy-preserving, differential privacy)
- ✅ OpenTelemetry observability
- ✅ Documentation (A-grade)
- ✅ Memory system (85/85 model tests)
- ✅ Audit logging (HMAC-chained)

### Phased rollout recommendation

**Phase 1 (Month 1) — Fix critical blockers**
Fix items 1-4 above. Stand up `cutctx.com`, activate Stripe, add `restore` command, configure email.

**Phase 2 (Month 2) — Fix high blockers**
Fix items 5-10. License validation, legal entity consistency, security vulnerabilities, marketing corrections.

**Phase 3 (Month 3) — Design-partner pilot**
Accept first 3-5 paying customers under concierge onboarding. Validate billing flow, support channels, backup/restore. Collect case study material.

**Phase 4 (Month 4-6) — GA readiness**
SAML SSO, load testing, penetration test, enterprise procurement packet, SLA credits section.

---

### Verdict

Cutctx has a **strong technical foundation** — the compression engine, pipeline architecture, enterprise auth infrastructure, and documentation are genuinely impressive. These are the hard parts, and they're done well.

But the **commercial layer is incomplete** — no domain, no working billing, no support email, no restore path, no SAML. Accepting money today would create liability: a customer who can't reach support, can't restore from backup, and whose license can't be validated.

**Release to open source:** ✅ Ready now (Apache-2.0 engine is complete)
**Accept paying customers:** ❌ Not before items 1-4 are resolved
**Enterprise GA:** ❌ Not before items 1-10 are resolved

**Bottom line: NO-GO for paying customers. 4-6 weeks of commercial hardening work required.**
