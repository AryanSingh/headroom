# Paying-Customer Readiness Assessment

**Date:** 2026-07-19  
**Version:** 0.31.0  
**Classification:** Internal — Go/No-Go Recommendation  

---

## Executive Summary

**Verdict: CONDITIONAL GO** — Ready for early paid customers under strict conditions. Not ready for mass-market self-serve or procurement-driven enterprise sales.

Cutctx demonstrates surprising maturity for a project classified "Development Status :: 4 — Beta." It has a published pricing page, legal terms (draft), SLA definitions, SOC 2 control mapping, vendor security questionnaire, backup automation, Helm deployment, artifact signing, and a structured lead generation playbook. The open-core licensing boundary is clearly documented. The local-first architecture inherently satisfies many enterprise security requirements.

However, critical gaps remain: the Terms of Service are explicitly marked as "draft — must be reviewed by legal counsel," SOC 2 is "in preparation" with Q4 2026 target, there is no self-serve payment flow (all paid tiers require emailing sales), and the enterprise sales motion consists of a single `sales@payzli.com` contact. These are not code gaps — they are business and operational gaps that will block procurement-driven deals.

### Readiness Score: 67/100

| Dimension | Score | Assessment |
|-----------|:-----:|------------|
| Onboarding | 7/10 | Quick to install, moderate learning curve |
| Pricing | 7/10 | Visible, clear tiers, but no self-serve |
| Billing | 3/10 | Stripe integration exists, no self-serve payment |
| Licensing | 8/10 | Open-core boundary well-documented |
| Analytics | 7/10 | Dashboard + telemetry + savings reporting |
| Support | 5/10 | Community + email; no in-app support, no chat |
| Security | 8/10 | Local-first architecture + enterprise controls |
| Observability | 7/10 | Prometheus + audit logs + health checks |
| Documentation | 8/10 | Comprehensive docs site + product guide |
| Reliability | 6/10 | Good infra; no DR plan, no capacity planning |
| Backup | 7/10 | Automated + verified; 17 databases covered |
| Compliance | 5/10 | SOC 2 in preparation; terms are draft |
| Legal | 5/10 | Terms / Privacy exist but need counsel review |
| Marketing | 6/10 | Structured materials with gaps |
| Enterprise | 5/10 | Features ready, sales motion not |
| Competitive | 8/10 | Strong positioning, verifiable savings needed |

---

## 1. Onboarding Readiness — 7/10

### Strengths
- **30-second install:** `pip install cutctx-ai` then `cutctx proxy`
- **Zero-code-change proxy mode:** Just change `ANTHROPIC_BASE_URL`
- **CLI quickstart** works without reading docs
- **MCP server** works with Claude/Cursor out of the box
- **Product guide** (PRODUCT_GUIDE.md, 929 lines) is a comprehensive sales/training resource
- **Deployment docs:** Docker, Docker Compose, Kubernetes, air-gap all covered

### Gaps
| Gap | Impact | Fix Priority |
|-----|--------|:------------:|
| No interactive onboarding wizard | Users don't see value immediately | Medium |
| No "before vs after" compression preview | Can't verify savings before committing | High |
| No cloud-hosted trial option | Enterprise buyers can't "try before buy" without infra | High |
| Documentation scattered across 3 surfaces (README, docs.cutctx.com, GitHub) | Users must navigate multiple sources | Medium |
| No sample apps or starter templates | No quick way to see integration patterns | Low |
| No guided migration from OSS to paid | Friction at upgrade point | Medium |

---

## 2. Pricing Readiness — 7/10

### What Exists
- **Published pricing page** (docs/pricing.html): Builder (Free), Team ($1,500/mo), Enterprise (Custom)
- **Detailed pricing sheet** (artifacts/pricing-sheet.md): Annual pricing breakdown
- **Feature comparison table**: Clear what each tier includes
- **Enterprise pricing tiers**: Team ($18K/yr), Business ($42K/yr), Enterprise ($60K-$150K+/yr)
- **ROI calculator** (marketing/roi-calculator/): Interactive HTML tool for prospects
- **Pricing pitch** in PRODUCT_GUIDE.md section 13

### Gaps
| Gap | Impact | Fix Priority |
|-----|--------|:------------:|
| No self-serve upgrade from Free → Team | Every paid conversion requires a sales call | **Critical** |
| No monthly pricing for Team tier | Listed at "$1,500/mo" but no payment mechanism | High |
| Team tier at $1,500/mo for "beta" software | Value perception risk | Medium |
| No usage-based or per-seat pricing listed | Only flat monthly tiers | Medium |
| No free trial of Team features | Users can't evaluate EE features without commit | High |
| Enterprise pricing has massive range ($60K-$150K+) | Unclear what determines the price | Medium |

---

## 3. Billing Readiness — 3/10

### What Exists
- `cutctx_ee/billing/` package with license issuance and Stripe webhook integration
- Subscription window tracking (`cutctx/subscription/`)
- Spend ledger (`cutctx_ee/ledger/`)
- License key validation with HMAC-SHA256 signing
- Entitlement enforcement on request path

### Gaps
| Gap | Impact | Fix Priority |
|-----|--------|:------------:|
| **No self-serve payment flow** | Cannot accept credit cards without sales contact | **CRITICAL** |
| No automated invoicing | Manual billing operations only | **High** |
| No proration logic | Upgrading mid-cycle is manual | Medium |
| No metered billing infrastructure | Per-usage pricing not supported | Medium |
| No billing portal for customers | Customers can't see invoices/payment history | Medium |
| No dunning system | Failed payments handled manually | Medium |
| No automated seat counting | Seat enforcement but no auto-billing | Medium |

**Billing is the single weakest dimension.** The product has license enforcement but no way for a customer to actually pay for it without emailing a human. This blocks the entire Team tier ($1,500/mo) funnel.

---

## 4. Licensing Readiness — 8/10

### What Exists
- **LICENSING.md** (97 lines) — authoritative open-core boundary document
- **Apache 2.0** for OSS components (clearly listed by path)
- **Cutctx Commercial License** (proprietary) for EE components (also listed by path)
- **Package separation**: `cutctx_ee/` excluded from OSS wheel via `[tool.maturin] exclude`
- **SPDX headers**: `Apache-2.0` and `LicenseRef-Cutctx-Commercial`
- **Release-marker boundary** in `cutctx_ee/watermark.py`
- **Contributor guidance**: Inbound=outbound for OSS; CLA required for commercial
- **License enforcement**: HMAC-signed license keys validated on every request
- **Entitlement tiers**: BUILDER < TEAM < BUSINESS < ENTERPRISE

### Gaps
| Gap | Impact | Fix Priority |
|-----|--------|:------------:|
| Terms of Service says "draft — must be reviewed by counsel" | Legal risk for paid customers | **Critical** |
| No CLA in place for external contributors | Relicensing risk for commercial components | High |
| No contributor audit performed | Unknown if commercial components have clean chain | High |
| License-COMMERCIAL file not reviewed | Legal wording unvalidated | Medium |
| LICENSING.md says "not legal advice" | Well-hedged but needs formal review | Medium |

---

## 5. Analytics & Reporting Readiness — 7/10

### What Exists
- **Savings dashboard**: Live SPA (React/Vite) with per-period, per-model breakdowns
- **Savings data exports**: JSON/CSV
- **Cost tracking**: Per-request cost tracking with savings attribution (v7 schema)
- **Savings sources**: Compression, normalization, memoization, batch routing, output optimization
- **Cost forecasting**: `cutctx/cost_forecast.py`
- **Spend ledger**: `cutctx_ee/ledger/`
- **Agent savings reports**: `cutctx/agent_savings.py` and `cutctx/cli/agent_savings.py`
- **Buyer report**: `cutctx/cli/report.py` generates buyer-facing reports
- **Prometheus metrics**: `/metrics` endpoint with operational counters
- **Structured audit logging**: JSON audit events with HMAC hash chain

### Gaps
| Gap | Impact | Fix Priority |
|-----|--------|:------------:|
| No usage alerts (e.g., "you've used 80% of budget") | Surprise bills | High |
| No scheduled report delivery | Manual report generation only | Medium |
| No per-user usage breakdown | Cannot attribute costs to individuals | Medium |
| No spend anomaly detection | Unexpected spikes invisible | Medium |
| Dashboard requires proxy connection | Cannot view history without running proxy | Low |

---

## 6. Support Readiness — 5/10

### What Exists
- **Discord community** (discord.gg/yRmaUNpsPJ) for questions and feedback
- **SLA.md** with tiered response targets:
  - Builder: Best effort (no SLA)
  - Team: Next business day (email, business hours)
  - Business: 4 business hours (email + scheduled calls)
  - Enterprise: 1 hour for critical (priority channel + escalation)
- **Severity levels defined**: Critical, High, Medium, Low
- **Security vulnerability reporting**: GitHub Security Advisories (48h acknowledgment)
- **SLA note**: "may be superseded by executed order form or MSA"

### Gaps
| Gap | Impact | Fix Priority |
|-----|--------|:------------:|
| No in-app support widget | Users must leave product to get help | Medium |
| No knowledge base / self-help portal | Support scales with team size | High |
| No phone or chat support (any tier) | Only email for paid tiers | High |
| No onboarding call included | New Team customers set up themselves | Medium |
| No customer success manager (any tier) | No proactive health monitoring | Medium |
| No support ticket tracking visible | Users can't check status of their issues | Medium |
| `sales@payzli.com` is the only contact | Single point of failure, doesn't match product brand | Medium |

---

## 7. Security Readiness — 8/10

### What Exists
- **Local-first architecture** — data stays in customer infrastructure
- **Enterprise auth**: SSO (OIDC/JWT), SCIM provisioning, RBAC (Viewer/Operator/Admin)
- **MFA**: TOTP (RFC 6238) for admin accounts
- **LLM Firewall**: PII, injection, and jailbreak pattern detection
- **Egress enforcement**: Domain allowlisting for air-gap deployments
- **Secrets store**: Encrypted credential management
- **State crypto**: Fernet (AES-128-CBC + HMAC-SHA256) for data at rest
- **Audit logging**: HMAC-SHA256 hash chain for tamper evidence
- **Health endpoints**: `/livez`, `/readyz`, `/health`, `/health/config`
- **Security.md**: Vulnerability disclosure policy via GitHub Advisories
- **SLA note**: "proxies should run behind private network boundary"

### Gaps
| Gap | Impact | Fix Priority |
|-----|--------|:------------:|
| No SOC 2 attestation | Blocking for regulated enterprise procurement | **Critical** |
| No penetration test results | No evidence of security posture | High |
| No bug bounty program | No external security researchers testing | Medium |
| Provider passthrough routes unauthenticated | Anyone with network access can make LLM calls | High |
| No rate limiting per API key / tier | Single global rate limiter | Medium |
| No session timeout enforcement | Long-lived admin sessions | Medium |
| `CUTCTX_AUDIT_SECRET_KEY` requirement | Good for audit, but `CUTCTX_ALLOW_DEV_AUDIT_KEY=1` is a bypass | Low |

---

## 8. Observability Readiness — 7/10

### What Exists
- **Prometheus metrics** (`/metrics`): Operational counters, stage timings, rate limit stats
- **Health endpoints**: `/livez` (liveness), `/readyz` (readiness), `/health` (full), `/health/config` (config)
- **Structured logging**: JSON audit events with timestamp, event type, tier, result
- **Telemetry beacon**: Anonymous aggregate stats to Supabase (opt-in)
- **Stage timers**: Per-request timing across compression pipeline stages
- **Prometheus ServiceMonitor**: Helm chart includes ServiceMonitor for operator-based scraping
- **Prometheus rules**: `k8s/prometheus-rules.yaml` for alerting rules
- **OpenTelemetry tracing**: `cutctx/observability/tracing.py`

### Gaps
| Gap | Impact | Fix Priority |
|-----|--------|:------------:|
| No pre-built Grafana dashboard | Must build from scratch | Medium |
| No alert delivery integration | Webhooks exist, no Slack/PagerDuty connectors | Medium |
| No log aggregation integration | No Fluentd/Logstash/Loki output | Medium |
| No SLO/SLI definitions | No service level targets published | Medium |
| `--no-telemetry` is default | Fleet-level visibility for Cutctx operators is limited | Low |

---

## 9. Documentation Readiness — 8/10

### What Exists
- **44 documentation pages** on docs site (Next.js/Fumadocs)
- **Comprehensive Product Guide** (PRODUCT_GUIDE.md, 929 lines)
- **Sales playbook** (LEAD_GEN_PLAYBOOK.md) 
- **Pricing sheet** (artifacts/pricing-sheet.md)
- **Enterprise procurement packet** (artifacts/enterprise-procurement-packet.md)
- **Security one-pager** (artifacts/security-one-pager.md)
- **Deployment guides**: Docker, K8s, air-gap, docker-compose, devcontainers
- **Quickstart**, tutorials, API reference, troubleshooting
- **llms.txt** for AI-agent consumption

### Gaps
| Gap | Impact | Fix Priority |
|-----|--------|:------------:|
| No "getting started with Team tier" guide | Paid users have no specialized onboarding | Medium |
| No video tutorials or screencasts | Visual learners underserved | Low |
| No API reference for the full proxy API | Only orchestration API documented | Medium |
| No migration guide from OSS → EE | Friction at upgrade point | Medium |
| Docs duplicated between README and docs site | Version drift risk | Low |

---

## 10. Reliability Readiness — 6/10

### What Exists
- **Kubernetes HPA**: Horizontal Pod Autoscaler (CPU/memory based)
- **PodDisruptionBudget**: `k8s/pdb.yaml`
- **Health probes**: Liveness + readiness in deployment manifest
- **Docker healthcheck**: Calls `/readyz`
- **Graceful shutdown**: Proxy handles SIGTERM/SIGINT
- **Rate limiting**: Token bucket for request throttling
- **Circuit breaker**: `cutctx/proxy/circuit_breaker.py`
- **Retry logic**: Provider call retries with exponential backoff
- **Chaos testing**: `chaos-testing.yml` workflow (manual)
- **Release evidence**: `product-release-evidence.yml` with verification steps

### Gaps
| Gap | Impact | Fix Priority |
|-----|--------|:------------:|
| **No disaster recovery plan** documented | Data loss scenario has no recovery procedure | **Critical** |
| **No capacity planning documentation** | Unknown how many requests/sec the proxy handles | **High** |
| **No published SLO/SLI** | Customers don't know what reliability to expect | High |
| **No multi-region deployment guide** | No HA across regions | Medium |
| **Chaos testing is manual** | Not part of CI or release pipeline | Medium |
| **No load testing in CI** | Performance regression not caught automatically | Medium |
| **SQLITE_BUSY under concurrent load** | No retry logic in storage backends | High |

---

## 11. Backup Readiness — 7/10

### What Exists
- **Automated daily backup CronJob**: `k8s/backup-cronjob.yaml` — covers all 17 SQLite databases
- **S3 backup destination**: AWS S3 with 30-day retention
- **Backup script**: `scripts/verify-backup.sh` — verifies SQLite integrity
- **Backup test**: `tests/test_verify_backup_script.py` — automated test of the verification script
- **Point-in-time recovery**: SQLite `.backup` command for consistent snapshots
- **Docker Healthcheck**: Container health monitoring
- **PodDisruptionBudget**: K8s PDB for deployment stability
- **Retention policy**: 30-day S3 lifecycle + 7 successful/3 failed job history

### Gaps
| Gap | Impact | Fix Priority |
|-----|--------|:------------:|
| No restore procedure documentation | Backup exists but recovery is tribal knowledge | **High** |
| No backup encryption | S3 bucket encryption not configured in manifest | Medium |
| No cross-region backup | Single-region failure loses all backups | Medium |
| No backup monitoring alert | Silent backup failures invisible | Medium |
| No RTO/RPO validation | Targets declared but not tested | Medium |

---

## 12. Compliance Readiness — 5/10

### What Exists
- **SOC 2 Controls Mapping** (SOC2_CONTROLS.md): 64-line document mapping TSC criteria to implementations
- **SOC 2 Type I audit**: "In preparation; target completion Q4 2026"
- **Vendor Security Questionnaire**: Pre-filled 200-line document for procurement
- **Data Residency**: `docs/data-residency.md` with proof endpoints
- **Data Subject Rights**: `/v1/me/export` and `/v1/me/delete` DSR endpoints
- **Privacy**: PRIVACY.md with local-first architecture and data flow diagram
- **Terms of Service**: TERMS.md (draft, needs legal review)
- **GDPR readiness**: DSR endpoints + data residency controls
- **Retention policies**: Configurable via `cutctx_ee/retention.py`

### Gaps
| Gap | Impact | Fix Priority |
|-----|--------|:------------:|
| **SOC 2 not attested** | Blocking for regulated enterprise procurement | **CRITICAL** |
| **No ISO 27001 certification** | EU/govt procurement blocker | High |
| **No HIPAA BA agreement available** | Healthcare sector blocked | High |
| **DPA not published** | GDPR processing agreement must be signed | High |
| **No penetration test available** | No third-party security validation | High |
| **Terms of Service are draft** | Legal risk if used in commercial transaction | **CRITICAL** |
| DSR delete paths are incomplete | Spend ledger and audit log delete "documented but not shipped" | High |

---

## 13. Legal Readiness — 5/10

### What Exists
- **TERMS.md**: 76 lines, covers all standard sections (license, subscription, acceptable use, IP, data handling, warranty, liability, termination, governing law)
- **PRIVACY.md**: 101 lines, comprehensive data flow documentation
- **LICENSING.md**: 97 lines, authoritative open-core boundary
- **SLA.md**: 46 lines, tiered support policy
- **SECURITY.md**: 66 lines, vulnerability disclosure policy
- **CODE_OF_CONDUCT.md**: Standard contributor covenant
- **CONTRIBUTING.md**: PR guidelines and policies

### Gaps
| Gap | Impact | Fix Priority |
|-----|--------|:------------:|
| **TERMS.md explicitly says "draft — must be reviewed by qualified legal counsel"** | Cannot use in commercial transactions | **CRITICAL** |
| No entity named in terms | "Cutctx Labs" used but legal entity unclear | High |
| No DPA published | Required for EU customers | High |
| No data processing location specified | GDPR compliance gap | Medium |
| Delaware law + Wilmington courts | May not suit all customers | Low |
| `sales@payzli.com` contact | Doesn't match product or domain brand | Medium |

---

## 14. Marketing Readiness — 6/10

### What Exists
| Asset | Status | Quality |
|-------|--------|---------|
| README | ✅ Complete | Excellent — badges, comparison table, quickstart |
| Product Guide | ✅ Complete | 929 lines — comprehensive sales enablement |
| Lead Gen Playbook | ✅ Complete | ICP tiers, pain points, key signals |
| Case Study Template | ✅ Complete | Fill-in-the-blank format |
| ROI Calculator | ✅ Interactive | HTML-based, in marketing/roi-calculator/ |
| Pricing Page | ✅ Complete | HTML with tiers, comparison table |
| Enterprise Page | ✅ Complete | HTML with features, use cases |
| Pitch Deck | ✅ Exists | `artifacts/pitchdeck.md` |
| Outreach Playbook | ✅ Exists | `artifacts/outreach-current-positioning.md` |
| Value Proposition | ✅ Exists | `artifacts/value-proposition.md` |
| Security One-Pager | ✅ Exists | For procurement |
| Demo Script | ✅ Exists | `artifacts/design-partner-demo-script.md` |
| Pilot Success Metrics | ✅ Exists | `artifacts/pilot-success-metrics.md` |
| Enterprise Procurement Packet | ✅ Exists | For procurement reviews |
| Social Proof | ❌ Missing | No case studies, no testimonials, no logos |
| Website | ⚠️ Static | HTML pages, not a real CMS/marketing site |
| Blog | ❌ Missing | No thought leadership content |
| Comparison Page | ❌ Missing | No competitive comparison on website |
| Video/Demo | ❌ Missing | No screencasts or walkthroughs |

### Gaps
| Gap | Impact | Fix Priority |
|-----|--------|:------------:|
| No published case studies | Prospects can't see real customer results | **Critical** |
| No customer logo wall | No social proof | High |
| No G2/Capterra/PeerSpot presence | Evaluation platforms uncovered | Medium |
| No product launch strategy | No coordinated go-to-market | Medium |
| No analyst relations | No Gartner/Forrester coverage | Low |
| No press kit / media assets | Journalists can't easily cover product | Low |

---

## 15. Enterprise Readiness — 5/10

### What Exists (Feature)
- ✅ SSO (OIDC/JWT) with role mapping
- ✅ SCIM user/group provisioning
- ✅ RBAC (Viewer/Operator/Admin) with permission model
- ✅ Audit logging with HMAC hash chain
- ✅ Retention policy controls
- ✅ Fleet management
- ✅ Air-gap deployment
- ✅ Kubernetes + Helm deployment
- ✅ Multi-tenant org/workspace/project model
- ✅ License key enforcement
- ✅ Entitlement-based feature gating

### What Exists (Process)
- Enterprise pricing tiers defined ($60K-$150K+/yr)
- Enterprise procurement packet assembled
- Vendor security questionnaire pre-filled
- SOC 2 controls mapped (audit in progress)
- Data residency proofs available
- Published SLA with enterprise escalation path
- DSR endpoints for GDPR compliance
- Artifact signing for supply chain security

### Gaps (Feature)
- No SAML support (OIDC/JWT only)
- No dedicated enterprise admin panel
- No read-only replica support
- No audit log forwarding to SIEM
- No custom retention policy per data type
- No organizational chart/org tree

### Gaps (Sales Motion)
| Gap | Impact | Fix Priority |
|-----|--------|:------------:|
| **No sales team** | Single email contact | **CRITICAL** |
| **No sales engineering** | No technical pre-sales support | **Critical** |
| **No onboarding/customer success** | Enterprise customers set up themselves | High |
| **No proof of concept framework** | Every evaluation is ad-hoc | High |
| **No reference architecture calls** | No guided architectural decisions | Medium |
| No partner/reseller channel | Only direct sales | Medium |
| No professional services org | No custom implementation support | Medium |

---

## 16. Competitive Differentiation Readiness — 8/10

### Strengths
- **Broadest feature set** in the context optimization space
- **Local-first architecture** — unique privacy positioning
- **Open-core licensing** — avoids vendor lock-in concern
- **Reversible compression (CCR)** — no competitor has this at this level
- **Multi-provider support** — 10+ LLM providers
- **Enterprise governance** — only player with RBAC/SSO/audit/fleet
- **Multi-modal** — images, audio, text, code, JSON

### Weaknesses
| Weakness | Impact | Fix Priority |
|----------|--------|:------------:|
| **Fleet-level savings contested** by independent benchmark | Undermines core value proposition | **Critical** |
| Complexity is highest in the market | Barrier to adoption | High |
| No SaaS offering (self-hosted only) | Excludes non-ops buyers | Medium |
| Python-centric perception | Limits market to Python shops | Low |

---

## 17. Dimension Score Summary

| Dimension | Score | Status |
|-----------|:-----:|--------|
| Onboarding | 7/10 | 🟢 Good |
| Pricing | 7/10 | 🟢 Good |
| Billing | 3/10 | 🔴 Critical gap |
| Licensing | 8/10 | 🟢 Excellent |
| Analytics | 7/10 | 🟢 Good |
| Support | 5/10 | 🟡 Needs work |
| Security | 8/10 | 🟢 Excellent |
| Observability | 7/10 | 🟢 Good |
| Documentation | 8/10 | 🟢 Excellent |
| Reliability | 6/10 | 🟡 Needs work |
| Backup | 7/10 | 🟢 Good |
| Compliance | 5/10 | 🟡 Needs work |
| Legal | 5/10 | 🟡 Needs work |
| Marketing | 6/10 | 🟡 Needs work |
| Enterprise | 5/10 | 🟡 Needs work |
| Competitive | 8/10 | 🟢 Excellent |
| **Average** | **67/100** | **CONDITIONAL GO** |

---

## 18. Go/No-Go Recommendation

### VERDICT: CONDITIONAL GO

The product is ready to take **early adopter paying customers** but is **not ready** for mass-market self-serve or procurement-driven enterprise sales.

### Conditions for Go

**Phase 1 — Immediate (can start selling today to early adopters):**

1. **Legal counsel reviews and signs off on TERMS.md** — remove the "draft" warning before any transaction
2. **Establish a self-serve payment capability** — even if it's just a Stripe checkout link for Team tier
3. **Publish named entity and DPA** — customers need to know who they're contracting with
4. **At least 1 published customer case study** — even if anonymized
5. **Document the initial DR/restore procedure** — backup exists but recovery is tribal knowledge

**Phase 2 — Near-term (next 30-60 days for broader sales):**

1. **Enable self-serve Team tier upgrade** — automated billing from Free → $1,500/mo
2. **Commission and publish third-party benchmarks** — address the tokbench contested savings finding
3. **Build a customer success onboarding flow** — even a 30-min call template
4. **Add alert delivery (Slack/PagerDuty webhook docs)** — production operators need this
5. **Fix SQLITE_BUSY retry** — reliability gap for concurrent deployments

**Phase 3 — Pre-Enterprise (before pursuing procurement-driven deals):**

1. **SOC 2 Type I attestation** (target Q4 2026 — must hit this)
2. **Penetration test by third party** — publish executive summary
3. **Complete DSR delete paths** — spend ledger and audit log delete are not shipped
4. **Publish SLO/SLI targets** — customers need to know what reliability to expect
5. **Establish basic sales engineering capacity** — at least one technical pre-sales person

### What Can Be Sold Today

| Segment | Recommendation | Max Price |
|---------|---------------|:---------:|
| **Individual developers** | ✅ Free tier — no changes needed | $0 |
| **Small teams (2-10)** | ⚠️ Team tier — but only via email + manual billing | $1,500/mo |
| **Mid-market (10-100)** | ⚠️ Business tier — needs SOC 2 for procurement | $42K/yr |
| **Enterprise (100+)** | ❌ Hold — SOC 2, legal, and sales motion gaps | — |
| **Design partners** | ✅ Full EE access — in exchange for case study + feedback | Negotiated |

### No-Go Triggers (Things That Would Change This to NO-GO)

Any ONE of these would block paying customers:
1. **TERMS.md draft warning used in a real transaction** — legal liability
2. **SOC 2 audit fails or is abandoned past Q4 2026** — enterprise channel dead
3. **An independent multi-replication benchmark confirms tokbench finding** → fleet-level savings are negative → product value proposition is not real
4. **Data loss incident due to missing SQLITE_BUSY handling** — trust destroyed
5. **License boundary leak** — proprietary code accidentally shipped in OSS wheel

---

## Appendix A: Readiness Checklist — Sign-Off Status

| Item | Status | Owner | Deadline |
|------|--------|-------|----------|
| Terms reviewed by legal counsel | ❌ | Legal | Before first paid sale |
| DPA published | ❌ | Legal | Before first EU customer |
| Self-serve payment enabled | ❌ | Engineering | Q3 2026 |
| Automated invoicing | ❌ | Operations | Q3 2026 |
| Customer case study published | ❌ | Marketing | Q3 2026 |
| SOC 2 Type I attested | ❌ | Security | Q4 2026 |
| Third-party penetration test | ❌ | Security | Q4 2026 |
| DR plan documented | ❌ | Engineering | Q3 2026 |
| SLO/SLI published | ❌ | Engineering | Q3 2026 |
| alert delivery (Slack/PagerDuty) | ❌ | Engineering | Q3 2026 |
| SQLITE_BUSY retry implemented | ❌ | Engineering | Q3 2026 |
| DSR delete paths completed | ❌ | Engineering | Q4 2026 |
| Independent benchmark published | ❌ | Product | Q3 2026 |
| Sales engineering capacity | ❌ | GTM | Q4 2026 |

## Appendix B: Top 10 Actions Before First Paid Customer

1. **🔴 Legal review TERMS.md** — strip the draft warning
2. **🔴 Establish entity for contracting** — update TERMS with named legal entity
3. **🔴 Create Stripe checkout for Team tier** — no-code self-serve payment
4. **🔴 Publish DPA** — GDPR compliance prerequisite
5. **🟡 Commission third-party benchmark** — validate savings claims independently
6. **🟡 Document DR/restore procedure** — turn backup CronJob into runbook
7. **🟡 Add SQLITE_BUSY retry** — concurrency reliability
8. **🟡 Set up Slack alert webhook** — operations monitoring
9. **🟡 Build onboarding checklist for paid customers** — 30-min setup call template
10. **🟡 Get one customer case study signed** — social proof exists
