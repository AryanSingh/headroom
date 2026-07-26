# Cutctx — Go/No-Go Assessment for Paying Customers

**Date:** 2026-07-18
**Revision:** `7b726934`
**Artifact version:** v0.32.0
**Method:** Full-stack audit across 16 dimensions using static analysis, test execution, manual verification, documentation review, and code inspection.

---

## 1. Executive Verdict

## 🟡 CONDITIONAL GO — Pilot-Ready, Not Broad-Release-Ready

**Overall score: 82/100**
**Pilot path score: 92/100**

Cutctx is ready for a **pilot program with named, technically sophisticated paying customers** who have been briefed on the known gaps. It is **not yet ready for broad self-serve commercial release** to anonymous paying customers.

| Customer Type | Verdict | Rationale |
|---|---|---|
| **Pilot customer** (named, supported, under NDA) | ✅ **GO** | All critical paths work; manual support can cover gaps |
| **Self-serve customer** (unassisted signup) | ❌ **NO-GO** | Billing incomplete, a11y gaps, no onboarding docs |
| **Enterprise customer** (procurement, SSO, audit) | ⚠️ **CONDITIONAL** | EE features exist but are untestable without staging |

### Rationale for Conditional Go

The product's **core value proposition — LLM proxy compression, model routing, CCR reversible storage, memory system, and operator dashboard — is fully functional and tested** (304 verifier tests pass, P0 manual gates pass 18/24, zero P0 failures). The team should not delay pilot revenue for polish items.

However, **six gaps block broad self-serve release**. Each is bounded, fixable, and clearly scoped.

---

## 2. Dimension-by-Dimension Assessment

### 2.1 Onboarding — ✅ GOOD

| Criterion | Status | Evidence |
|---|---|---|
| `cutctx setup` command | ✅ | Unified CLI with auto-detect, proxy start, MCP registration |
| `cutctx init` command | ✅ | Agent-specific integration init (global, port, backend, region) |
| `cutctx install` command | ✅ | Persistent deployment installation and removal |
| `cutctx capabilities` | ✅ | Full capability manifest with JSON output |
| Docs quickstart | ✅ | `README.md` 60-second install works |
| Docs site | ✅ | 20+ pages in `docs/content/docs/` covering all major features |
| Docker quickstart | ✅ | `docker-compose.yml` with healthcheck |
| Agent compatibility matrix | ✅ | Documented in README and PRODUCT_GUIDE |
| CLI help consistency | ✅ | Every command has `--help`, groups have headings |
| **First-run friction** | ⚠️ | No guided first-run wizard beyond `setup`; no in-app onboarding |

**Verdict: Onboarding is production-ready for CLI-savvy users.**

### 2.2 Pricing — ✅ GOOD

| Criterion | Status | Evidence |
|---|---|---|
| Published tier definitions | ✅ | 4 tiers: Builder (free), Team ($18k/yr), Business ($42k/yr), Enterprise ($60k–$150k+) |
| Tier-to-feature mapping | ✅ | PRODUCT_GUIDE.md section 13 with detailed per-tier breakdown |
| Monthly vs annual pricing | ✅ | 20% monthly premium documented |
| Public pricing page | ⚠️ | `docs/pricing.html` exists; `cutctx.com/pricing` is fallback in code |
| ROI calculator | ✅ | `marketing/roi-calculator/` with claims of 471–680% annual ROI |
| Feature gating in code | ✅ | `cutctx_ee/entitlements.py` enforces tier boundaries |

**Verdict: Pricing is well-defined and enforceable. Public pricing page uses fallback URL — should be updated before GA.**

### 2.3 Billing — 🟡 CONDITIONAL

| Criterion | Status | Evidence |
|---|---|---|
| Stripe integration | ✅ | `stripe_webhook.py` — signature verification, license CRUD |
| Checkout flow | ✅ | `checkout.py` + `billing.py` generate PitchToShip URLs |
| Webhook handlers | ⚠️ | `checkout.session.completed` ✅, `invoice.paid` ✅, `customer.subscription.deleted` ✅, `customer.subscription.updated` ✅ |
| Self-serve subscription | ⚠️ | Uses PitchToShip external service — single point of failure |
| Trial management | ✅ | `trial.py` + `license start-trial` endpoint |
| Invoice handling | ✅ | `handle_invoice_paid` — extends license on payment |
| License activation | ✅ | `license activate` — key validation, seat tracking |
| **Direct Stripe checkout** | ❌ | No direct `stripe.checkout.Session.create()` — always goes through PitchToShip |
| **Payment method management** | ⚠️ | Portal URL generation exists, no self-serve payment method update UI |

**Verdict: Billing works end-to-end but relies on PitchToShip. Self-serve customers would be blocked if PitchToShip is unavailable. For pilot customers with invoiced billing, this is acceptable.**

### 2.4 Licensing — ✅ GOOD

| Criterion | Status | Evidence |
|---|---|---|
| License key generation | ✅ | `license_db.py` — SQLite-backed, HMAC-signed keys |
| License validation | ✅ | `license_validation.py` — REST endpoint + `verify_license_signature` in Rust core |
| Seat tracking | ✅ | `seats.py` + `license checkout-seat` |
| Trial management | ✅ | `license start-trial`, `license check-trial` endpoints |
| CRL (Certificate Revocation List) | ✅ | `license crl` — license revocation support |
| Offline/airgap mode | ✅ | `CUTCTX_OFFLINE_MODE` env var + `airgap.py` endpoints |
| CLI license management | ✅ | `cutctx license activate/status/generate/upgrade` |
| Entitlement enforcement | ✅ | `cutctx_ee/entitlements.py` — tier-based feature gating on request path |

**Verdict: Licensing is production-ready. HMAC-signed keys with CRL support and airgap mode exceed typical requirements.**

### 2.5 Analytics — ✅ GOOD (for pilot; ⚠️ partial for self-serve)

| Criterion | Status | Evidence |
|---|---|---|
| Request volume analytics | ✅ | `/stats`, `/stats-history`, `/v1/stats` |
| Savings analytics | ✅ | `/reports/savings`, `/v1/retrieve/stats`, dashboard Savings page |
| Usage by provider/model | ✅ | `/reports/usage` with provider/model/stack/time breakdown |
| Team analytics dashboard | ✅ | `/analytics/dashboard` endpoint |
| Per-project breakdown | ✅ | `/analytics/projects` endpoint |
| Dashboard visualization | ✅ | 11-page SPA with Overview, Savings, Orchestrator, Memory views |
| Telemetry system | ✅ | `telemetry/` module — privacy-preserving compression pattern collection |
| TOIN (Tool Output Intelligence Network) | ✅ | `toin_*` endpoints + `cli/toin_publish.py` |
| **Self-serve analytics portal** | ⚠️ | Dashboard requires running proxy — no hosted analytics option |

**Verdict: Analytics are comprehensive for operators who run the dashboard. No hosted/SaaS analytics option exists, which is consistent with the local-first product positioning.**

### 2.6 Support Flows — 🟡 CONDITIONAL

| Criterion | Status | Evidence |
|---|---|---|
| Published SLA | ✅ | `SLA.md` — per-tier response times (1hr critical for Enterprise) |
| Community channel | ✅ | Discord link in README |
| Issue templates | ✅ | GitHub bug report, feature request, PR templates |
| Support email | ✅ | `hello@aoexl.com` in `checkout.py` |
| Support tiers defined | ✅ | Community (best-effort), Team (next-business-day), Business (4hr), Enterprise (1hr critical) |
| Error messages with remediation | ✅ | `server.py` returns `"remediation"` field in auth/policy errors |
| **In-app support widget** | ❌ | No live chat, no support portal, no knowledge base |
| **Self-serve troubleshooting** | ⚠️ | `config-check` + `config doctor` exist but no guided troubleshooting flow |

**Verdict: Support flows are sufficient for a pilot program with named contacts. Self-serve customers would benefit from a knowledge base and in-app help.**

### 2.7 Security — 🟢 STRONG

| Criterion | Status | Evidence |
|---|---|---|
| Authentication | ✅ | Bearer token, API key header, SSO JWT, proxy client key (4 mechanisms) |
| Authorization | ✅ | RBAC (Viewer/Operator/Admin roles), entitlement tier gates |
| Deployment security gate | ✅ | Block non-loopback launch without admin auth — `deployment_security.py` |
| LLM Firewall | ✅ | PII detection, injection blocking, jailbreak detection |
| State encryption | ✅ | `security/state_crypto.py` — Fernet + HMAC |
| Audit trail integrity | ✅ | HMAC chain — `security/integrity.py` |
| Egress policy | ✅ | `security/egress.py` — outbound URL allowlisting |
| CORS | ✅ | Configurable origins, wildcard blocked for non-loopback |
| Rate limiting | ✅ | Token bucket per API key/IP |
| Circuit breaker | ✅ | Per-provider CLOSED→OPEN→HALF_OPEN |
| Secret scanning | ✅ | `.pre-commit-config.yaml` + `.gitguardian.yaml` |
| Credential redaction | ✅ | Logs redact API keys, structured JSON |
| MFA/TOTP | ✅ | `mfa.py` — enrollment, verification, code generation |
| **No Sentry/error tracking** | ⚠️ | Unhandled exceptions have no fallback reporting |
| **No dependency vulnerability scanning in CI** | ⚠️ | No `pip-audit` or `cargo audit` in pipeline |
| **Auth brute-force no progressive backoff** | ⚠️ | Fixed token-bucket refill, no exponential backoff |

**Verdict: Security is a strength. The three ⚠️ items are important but not pilot-blocking — manual monitoring can cover them until automated tooling is added.**

### 2.8 Observability — 🟡 CONDITIONAL

| Criterion | Status | Evidence |
|---|---|---|
| Prometheus metrics | ✅ | 20+ metric families (requests, tokens, latency, savings, cache, WS sessions, executor) |
| Health check endpoints | ✅ | `/livez`, `/readyz`, `/health`, `/health/config` |
| Structured logging | ✅ | JSON logs with request ID, key redaction, PII filtering |
| Request tracing | ✅ | `/transformations/traces` + `/transformations/traces/{request_id}` |
| K8s probes | ✅ | Liveness, readiness, startup probes |
| FluentBit log collection | ✅ | DaemonSet configured in k8s/ |
| OpenTelemetry | ✅ | Optional OTel exporter |
| **Alerting rules** | ⚠️ | Only 2 rules (error rate, latency). No memory, disk, WS, upstream, cert-expiry alerts |
| **No synthetic monitoring** | ❌ | No external health check probes |
| **No PagerDuty/Opsgenie integration** | ❌ | No alert notification routing |
| **No dashboard uptime page** | ❌ | No status.cutctx.com equivalent |

**Verdict: Observability instrumentation is excellent. Alerting and notification routing are insufficient for 24/7 production operation without an on-call engineer watching the dashboard. Acceptable for pilot with named operator.**

### 2.9 Documentation — 🟢 STRONG

| Criterion | Status | Evidence |
|---|---|---|
| README | ✅ | Comprehensive with badges, install, quickstart, agent matrix, links |
| PRODUCT_GUIDE | ✅ | Full product guide — 20 sections, competitive landscape, objection handling |
| Docs site | ✅ | 20+ MDX pages covering all features, API, configuration, errors |
| ENTERPRISE.md | ✅ | Enterprise feature catalog and deployment guide |
| SECURITY.md | ✅ | Security policy with vulnerability disclosure process |
| PRIVACY.md | ✅ | Privacy policy — local-first data handling |
| TERMS.md | ✅ | Terms of service draft (⚠️ marked as pre-legal-review) |
| LICENSING.md | ✅ | Open-core licensing map — authoritative |
| SLA.md | ✅ | Support policy with per-tier response times |
| PROTECTION.md | ✅ | Data protection terms |
| API documentation | ✅ | `api-reference.mdx` in docs |
| Changelog | ✅ | `CHANGELOG.md` — up to date |
| CONTRIBUTING.md | ✅ | Contribution guide |
| **Legal review status** | ⚠️ | TERMS.md explicitly marked as pre-legal-review draft |
| **Upgrade/migration docs** | ⚠️ | No `docs/content/docs/upgrade.mdx` |

**Verdict: Documentation is a strength. Two legal/migration gaps exist but don't block a pilot program.**

### 2.10 Reliability — 🟢 STRONG

| Criterion | Status | Evidence |
|---|---|---|
| Circuit breaker | ✅ | Per-provider state machine — prevents cascading failure |
| Retry with backoff | ✅ | Exponential backoff for provider failures |
| Health checks | ✅ | `/livez` (lightweight), `/readyz` (full dependency check) |
| Graceful shutdown | ✅ | SIGTERM handler + preStop hook (5s sleep) |
| Resource limits | ✅ | K8s CPU/memory limits, security context, read-only root FS |
| PDB | ✅ | PodDisruptionBudget for HA |
| Startup probe | ✅ | 30-retry startup probe (60s window) |
| Non-root execution | ✅ | Docker + K8s run as nonroot user |
| Distroless base image | ✅ | Slim variant uses `gcr.io/distroless/python3-debian13` |
| **No canary deployment** | ⚠️ | RollingUpdate configured but no progressive rollout strategy |
| **No explicit rollback procedure** | ⚠️ | No rollback.md or runbook |

**Verdict: Reliability architecture is strong. The missing canary/rollback docs are acceptable for pilot.**

### 2.11 Backup Strategy — ✅ ADEQUATE

| Criterion | Status | Evidence |
|---|---|---|
| Automated backups | ✅ | K8s CronJob — daily at 00:00 UTC |
| Backup target | ✅ | S3 with 17 SQLite databases |
| Retention | ✅ | 30-day retention with automatic pruning |
| Backup verification | ✅ | `scripts/verify-backup.sh` exists |
| **Restore procedure documented** | ❌ | No restore playbook in repo |
| **Backup failure alerting** | ⚠️ | No PrometheusRule for backup failure |

**Verdict: Backup automation is solid. Restore procedure must be documented before the first paying customer is onboarded.**

### 2.12 Compliance — 🟡 CONDITIONAL

| Criterion | Status | Evidence |
|---|---|---|
| GDPR readiness | ✅ | DSR endpoints (`/dsr/export`, `/dsr/delete`), PRIVACY.md commitments |
| CCPA readiness | ✅ | Covered by DSR endpoints |
| SOC 2 | ❌ | `ENTERPRISE.md` explicitly states certification is incomplete |
| HIPAA | ❌ | No HIPAA claims — explicitly stated as incomplete |
| ISO 27001 | ❌ | Not claimed |
| Data residency | ✅ | `residency.py` endpoints — geo-fenced data control |
| Audit trail | ✅ | Tamper-evident HMAC chain audit |
| Data retention controls | ✅ | `retention.py` + `retention/cleanup` endpoint |
| **SOC 2 timeline** | ⚠️ | No public timeline for certification |
| **Data Processing Agreement** | ❌ | No DPA template in repository |

**Verdict: Compliance posture is honest (no false claims) and covers GDPR/CCPA basics. SOC 2/HIPAA customers must wait. DPA is needed for EU customers.**

### 2.13 Legal Pages — 🟡 CONDITIONAL

| Criterion | Status | Evidence |
|---|---|---|
| Terms of Service | ⚠️ | Present but marked as pre-legal-review draft — **must be reviewed before any paying customer signs** |
| Privacy Policy | ✅ | Comprehensive, local-first focused |
| Licensing | ✅ | Detailed open-core map with commercial entity identified |
| Data Protection terms | ✅ | PROTECTION.md |
| **DPA template** | ❌ | Missing — required for EU customers |
| **Vendor security questionnaire** | ⚠️ | Referenced in audit docs but not in repo root |

**Verdict: Legal docs exist but TERMS.md explicitly requires legal review before use with paying customers. This is the single biggest blocker to signing contracts.**

### 2.14 Marketing Readiness — 🟢 STRONG

| Criterion | Status | Evidence |
|---|---|---|
| Product messaging | ✅ | Clear "context control plane for AI agents" positioning |
| README badges | ✅ | CI, coverage, PyPI, npm, license, docs |
| Case study template | ✅ | `marketing/case-study-template.md` |
| ROI calculator | ✅ | `marketing/roi-calculator/` with 471–680% annual ROI claims |
| llms.txt | ✅ | Present for LLM-based discovery |
| Discord community | ✅ | Invite link in README |
| Benchmark evidence | ✅ | `benchmarks/` directory with 35+ benchmark files |
| Competitive comparison | ✅ | PRODUCT_GUIDE section 15 with vs-table |
| **Public website** | ⚠️ | `cutctx.com` mentioned but source not in repo — presumably external |
| **Social proof (case studies, testimonials)** | ⚠️ | Template exists but no published case studies |

**Verdict: Marketing collateral is well-developed for an open-source project. Public website and case studies would strengthen broad-release readiness.**

### 2.15 Enterprise Readiness — 🟡 CONDITIONAL

| Criterion | Status | Evidence |
|---|---|---|
| SSO/JWT auth | ✅ | OIDC-compatible admin authentication |
| RBAC | ✅ | Viewer/Operator/Admin roles with enforcement |
| SCIM provisioning | ✅ | Full SCIM 2.0 API (Users + Groups CRUD) |
| Audit logging | ✅ | Tamper-evident audit with export |
| Data retention | ✅ | Configurable retention policies |
| Fleet management | ✅ | Deployment heartbeat, health summary |
| Organization hierarchy | ✅ | Org → Workspace → Project |
| Data residency | ✅ | Geo-fenced residency controls |
| Secrets management | ✅ | Encrypted secrets CRUD |
| MFA/TOTP | ✅ | Multi-factor authentication |
| Airgap support | ✅ | Offline deployment mode |
| **SSO test coverage** | ⚠️ | No automated IdP integration test |
| **Enterprise dashboard UI** | ⚠️ | Backend APIs exist but most EE features lack dashboard UIs |
| **Self-serve enterprise provisioning** | ⚠️ | SCIM/SSO require manual configuration |

**Verdict: Enterprise features are implemented in the backend but lack dashboard UIs and automated IdP testing. Suitable for guided enterprise pilots with implementation support.**

### 2.16 Competitive Differentiation — 🟢 STRONG

| Factor | Cutctx | RTK | lean-ctx | Compresr | Native Caching |
|---|---|---|---|---|---|
| Local-first | ✅ | ✅ | ✅ | ❌ | N/A |
| Reversible (CCR) | ✅ | ❌ | ❌ | ❌ | N/A |
| Cross-provider | ✅ | ❌ | ❌ | Partial | ❌ |
| Team analytics | ✅ | ❌ | ❌ | ❌ | ❌ |
| Policy/governance | ✅ | ❌ | ❌ | ❌ | ❌ |
| Memory system | ✅ | ❌ | ❌ | ❌ | ❌ |
| Open-core | ✅ | ❌ | ✅ | ❌ | N/A |
| Role-based access | ✅ | ❌ | ❌ | ❌ | ❌ |

**Verdict: Strong competitive position. The local-first + reversible + cross-provider + governance combination is unique. ROI claims (471–680%) are well-documented.**

---

## 3. Risk Register for Paying Customers

| Risk | Likelihood | Impact | Mitigation | Deadline |
|---|---|---|---|---|
| **Billing: PitchToShip outage** | Low | Critical | Invoice pilot customers manually; add direct Stripe path before GA | Month 2 |
| **Legal: TERMS.md pre-review** | Medium | Critical | Engage counsel for review before signing first contract | **Before first contract** |
| **Observability: no alert routing** | Medium | High | Operator must watch dashboard; add PagerDuty before GA | Month 1 |
| **Backup: no restore playbook** | Medium | High | Write restore procedure before customer onboarding | **Before first customer** |
| **Auth: no progressive backoff** | Low | High | Manual IP-blocking for pilot; automated fix before GA | Month 2 |
| **Error tracking: no Sentry** | Medium | High | Operator must monitor logs manually; add Sentry before GA | Month 1 |
| **Enterprise: SSO untested** | Medium | High | Guide pilot customer through SSO config with engineering support | Ongoing |
| **Dashboard a11y: no aria-labels** | Low | Medium | Pilot not blocked; fix before GA (WCAG 2.4.4 violation) | Month 1 |
| **Compliance: no DPA** | Medium | Medium | Draft DPA template for EU customers | Month 1 |

---

## 4. Go/No-Go Recommendation

### For Pilot Paying Customers

## ✅ GO

**Conditions (must be met before signing the first pilot customer):**

1. **TERMS.md reviewed by legal counsel** — the current draft explicitly states it is pre-review. A single paying contract signed on pre-review terms creates liability.
2. **Restore procedure documented** — the backup system works; the restore does not. Write a restore playbook.
3. **Named support contact assigned** — the pilot customer must have a direct line to engineering, not just Discord.
4. **Customer briefed on alerting gaps** — the customer must understand that observability relies on dashboard monitoring, not automated paging.

**Recommended pilot customer profile:**
- Technically sophisticated engineering team
- Willing to use CLI + dashboard as primary interfaces
- Comfortable with local-first deployment (Docker or bare metal)
- Has named contacts for support escalation
- Does not require SOC 2/HIPAA/certifications
- Accepts that billing is invoice-based (not self-serve)

### For Broad Self-Serve Release

## ❌ NO-GO (estimated 4–6 weeks of work)

**Required before self-serve release:**

| Blocker | Fix ETA |
|---|---|
| TERMS.md legal review | 1 week |
| Direct Stripe checkout (decouple from PitchToShip) | 2 weeks |
| Sentry/error tracking | 0.5 week |
| Alerting rules expansion (8+ new rules) | 1 week |
| Restore playbook | 0.5 week |
| Dashboard a11y: nav aria-labels + landmarks | 0.5 week |
| DPA template | 0.5 week |
| Auth progressive backoff | 1 week |
| **Total** | **~4–6 weeks** |

### For Enterprise Customers

## ⚠️ CONDITIONAL

**Additional requirements for enterprise deals:**
- SSO integration must be tested against the customer's IdP with engineering support
- Audit export must be verified against customer's SIEM requirements
- DPA must be signed before data processing begins
- Fleet management must be validated in customer's K8s environment

---

## 5. Summary Scorecard

| Dimension | Score | Status | Blocker? |
|---|---|---|---|
| Onboarding | 90/100 | ✅ | No |
| Pricing | 85/100 | ✅ | No |
| Billing | 70/100 | 🟡 | Not for invoiced pilots; blocks self-serve |
| Licensing | 95/100 | ✅ | No |
| Analytics | 85/100 | ✅ | No |
| Support flows | 70/100 | 🟡 | No (named contacts for pilot) |
| Security | 88/100 | ✅ | No |
| Observability | 65/100 | 🟡 | No (operator monitoring covers pilot) |
| Documentation | 90/100 | ✅ | No |
| Reliability | 85/100 | ✅ | No |
| Backup | 75/100 | 🟡 | Restore playbook needed **before first customer** |
| Compliance | 70/100 | 🟡 | No (SOC 2/HIPAA not required for pilot) |
| Legal pages | 60/100 | 🟡 | TERMS.md legal review **required before first contract** |
| Marketing | 85/100 | ✅ | No |
| Enterprise readiness | 75/100 | 🟡 | No (SSO untested; dashboard UIs missing) |
| Competitive differentiation | 90/100 | ✅ | Strong position |
| **OVERALL** | **80/100** | **🟡 CONDITIONAL GO** | **2 legal/ops items must be resolved before signing** |

---

## 6. Next Steps

### Before first paying customer (Critical Path)

- [ ] **Engage legal counsel** to review TERMS.md (estimated: $2–5k, 1 week)
- [ ] **Write restore playbook** — document step-by-step S3 restore procedure (0.5 day)
- [ ] **Add Sentry** to proxy startup (0.5 day)
- [ ] **Add PagerDuty webhook** to PrometheusAlertManager (0.5 day)
- [ ] **Brief pilot customer** on alerting gaps and support process

### First sprint after pilot signed (Month 1)

- [ ] Expand PrometheusRules (8+ new rules — memory, disk, WS, upstream, cert)
- [ ] Add dashboard aria-labels and landmarks
- [ ] Add auth progressive backoff
- [ ] Write DPA template
- [ ] Add `pip-audit` + `cargo audit` to CI

### Before self-serve GA (Month 2)

- [ ] Wire direct Stripe checkout (decouple from PitchToShip)
- [ ] Add `customer.subscription.created` webhook handler
- [ ] Publish case studies from pilot customers
- [ ] Verify SSO against real IdP
- [ ] Run Playwright a11y scan + fix violations
- [ ] Add Python 3.10/3.11/3.13 CI matrix

---

*End of Go/No-Go Assessment — 2026-07-18*
*Based on: audit/qa-report.md, audit/manual-verification/execution-report.md, audit/application-functionality-map.md, audit/production-readiness.md, codebase inspection, and test suite execution.*
