# Paying-Customer Readiness Assessment — 2026-07-10

**Product:** Cutctx v0.30.0 (HEAD `418ae99a`) — Context compression layer for AI agents
**Method:** On-site codebase audit across 10 commercial-readiness dimensions + live web probes + competitive landscape analysis
**Predecessor:** `audit/paying-customer-readiness-2026-07-06.md` (score: ~83/100 production, verdict: conditional go for pilot)

---

## Go / No-Go Verdict

| Channel | Verdict | Score | One-line reason |
|---------|---------|-------|-----------------|
| **Design-partner pilot** (1-5 named accounts, founder-led, invoice-based) | ✅ **GO** | 82/100 | Core product is strong; 4 clear conditions below cover the gaps |
| **Public self-serve** (open signups, Stripe checkout, no founder in loop) | ❌ **NO-GO** | 58/100 | No website (NXDOMAIN), no billing pipeline, no working email |
| **Enterprise sales** ($60-150K+/yr, formal procurement, SOC 2) | ❌ **NO-GO** | 45/100 | 2-3 months of engineering + 6 months SOC 2 observation period |

### Conditions for Design-Partner Pilot GO (must be met per partner)
1. **Founder-led onboarding** — no self-serve flow; founder handles install, config, and initial support
2. **Invoice-based billing** — no Stripe checkout; send invoices and collect via wire/ACH
3. **Pre-pilot security review** — share SECURITY.md + SOC2_CONTROLS.md + security-one-pager.md
4. **14-day pilot term** — bounded engagement with explicit success criteria per partner

---

## 1. Onboarding & Installation — 74/100 ⚠️

### What works
- `pip install cutctx-ai && cutctx proxy` — functional, tested
- 14 agent wrap commands (Claude Code, Cursor, Codex, aider, etc.)
- `cutctx wrap` tested across 34/34 CLI commands
- Docker two-stage build with distroless option + HEALTHCHECK
- docker-compose (proxy + qdrant + neo4j) with healthcheck
- Helm chart + full k8s manifests
- MCP server (3 tools: compress, retrieve, stats) + memory MCP
- SDKs in Python and TypeScript on PyPI and npm

### What's broken or missing
| Issue | Severity | Detail |
|-------|----------|--------|
| **No website** — `cutctx.dev` + `cutctx.com` both NXDOMAIN | 🔴 BLOCKER | First Google click fails. All docs links, security contacts, and copyright notices dead. |
| **All emails bounce** — `hello@cutctx.dev`, `security@cutctx.com`, `conduct@cutctx.com` all NXDOMAIN | 🔴 BLOCKER | Security disclosures, license requests, support tickets, code of conduct reports all dead-letter. |
| **161+ references to cutctx.dev/com in docs** | 🟠 HIGH | Every doc, every README link, every security notice points at NXDOMAIN. Fixing the domain fixes all of them. |
| **Dashboard assets 404** — `/assets/` from proxy returns 404 | ⚠️ MEDIUM | Dashboard serves from Vite dev only. Production deployment needs fix. |
| **OG image hardcoded** — `docs/app/og/[...slug]/route.tsx:14` says "My App" | ⚠️ LOW | Only visible on social previews. |

### Scoring detail
| Sub-dimension | Score | Reasoning |
|--------------|-------|-----------|
| pip install experience | 90/100 | Works. Clean outputs. |
| Agent wrap commands | 85/100 | 14 agents, well documented. |
| Docker/k8s/Helm | 90/100 | Production-grade. |
| Self-service onboarding | 20/100 | No website, no docs site, no signup flow. |
| First-run experience | 65/100 | Works but no guided setup, no welcome dashboard. |

---

## 2. Pricing — 72/100 ⚠️

### What's good
- Canonical prices are well-structured and aligned with buyer expectations
- **Builder:** Free (OSS engine + local dashboard)
- **Team:** $1,500/mo ($18K/yr) — single team
- **Business:** $3,500/mo ($42K/yr) — platform teams
- **Enterprise:** Custom $60-150K/yr
- Pricing sheet (`artifacts/pricing-sheet.md`) is comprehensive with ROI framing, discount rules, quote skeleton
- Sales artifacts exist: pitchdeck, ROI one-pager, security one-pager, pilot success metrics
- Pricing contradiction (Team = $49 vs $1,500) **resolved** — docs/pricing.html now shows $1,500

### What's still wrong
| Issue | Severity | Detail |
|-------|----------|--------|
| **No pricing on website** | 🔴 HIGH | There is no website. Pricing.html is a local static file not published anywhere reachable. |
| **ROI calculator is a static HTML page** | ⚠️ MEDIUM | Not interactive. No "try pricing" flow. |
| **No self-serve upgrade path** | ⚠️ MEDIUM | No way for a user to upgrade from Builder to Team without contacting a human. |
| **Annual vs monthly billing** | INFO | $1,500/mo Team, $18K/yr = 0% discount on annual (pricing sheet says 20% premium on monthly). |
| **Sales@payzli.com** | INFO | Uses Payzli email (operating entity). Acceptable for pilot, confusing for brand. |

### Pricing vs competitors
| Tier | Cutctx | RTK Cloud | Helicone | Portkey | LeanCTX |
|------|--------|-----------|----------|---------|---------|
| Free | ✅ Full OSS engine | ✅ CLI free | Limited | Limited | Free tier |
| Team | $1,500/mo | $15/dev/mo (waitlist) | $120/mo | $199/mo | Not disclosed |
| Business | $3,500/mo | — | Custom | Custom | — |
| Enterprise | $60-150K/yr | — | Custom | Custom | Custom |

**Note:** RTK is CLI-only with narrower scope. Helicone/Portkey are API gateways with compression as a feature, not the product. LeanCTX is the closest direct competitor with a similar local-first thesis. Cutctx's pricing is at a premium to LeanCTX — defensible if CCR, multi-format, and cross-agent memory are the differentiators.

---

## 3. Billing — 30/100 ❌

### What's built
- Stripe webhook handlers exist (`stripe_webhook.py`) for `checkout.session.completed`, `customer.subscription.deleted`, `.updated`
- Ed25519 offline license signing and CRL revocation
- License DB with seat tracking
- PitchToShip client for centralized license management

### What's broken
| Issue | Severity | Detail |
|-------|----------|--------|
| **No working checkout path** | 🔴 CRITICAL | `cutctx/cli/billing.py` routes through PitchToShip. PitchToShip returns HTTP 200 (HTML landing page, not API response). No direct Stripe Checkout Session creation. A customer literally cannot pay. |
| **License validation is a no-op** | 🔴 CRITICAL | `cutctx_ee/watermark.py:185-204` queries the license DB but doesn't refuse service if no valid license is found. Any key passes. |
| **No billing UI in dashboard** | 🟠 HIGH | No Billing.jsx, no Subscription.jsx, no Pricing.jsx. Customer cannot see tier, invoices, or manage payment. |
| **Missing `customer.subscription.created` webhook handler** | 🟠 HIGH | Would orphan subscriptions on payment method changes. |
| **PitchToShip dependency** | 🟠 HIGH | Billing pipeline depends on a third-party service (PitchToShip) that is not owned or operated by Cutctx. No fallback. |
| **No usage-based billing** | ⚠️ MEDIUM | All tiers are flat-rate. Per-seat or per-token metering would unlock enterprise adoption. |
| **No invoicing system** | ⚠️ MEDIUM | No automated invoice generation, no dunning, no overdue collection. |

### Scoring
| Sub-dimension | Score | Reasoning |
|--------------|-------|-----------|
| Payment collection | 0/100 | No working checkout. |
| License enforcement | 15/100 | Code validates but doesn't deny. |
| Billing UI | 10/100 | Not built. |
| Webhook handlers | 60/100 | Code exists but untested end-to-end. |
| Invoice/collection | 20/100 | No automated system. |

---

## 4. Licensing — 62/100 ⚠️

### What's good
| Aspect | Detail |
|--------|--------|
| Open-core model | Clearly documented in LICENSING.md — Apache 2.0 for OSS engine, proprietary for commercial modules |
| License boundary | Well-defined file system boundary: `cutctx_ee/` is commercial; everything else is Apache 2.0 |
| Ed25519 signing | Offline license signing with CRL revocation |
| Tier-gated enforcement | `cutctx_ee/billing/entitlements.py` gates features by BUILDER < TEAM < BUSINESS < ENTERPRISE |
| SPDX headers | All commercial files carry `LicenseRef-Cutctx-Commercial` header |
| Wheel separation | OSS wheel excludes `cutctx_ee/` per `pyproject.toml`; commercial wheel built from `packaging/cutctx-ee/` |

### Issues
| Issue | Severity | Detail |
|-------|----------|--------|
| **License enforcement is a no-op** | 🔴 CRITICAL | Watermark checker queries DB but doesn't refuse service. OSS users can use EE features by installing the EE wheel without a license. |
| **Entity mismatch** | ⚠️ HIGH | `cutctx_ee/LICENSE:7` = "Payzli Inc."; `cutctx_ee/__init__.py:2` = "Cutctx Labs"; root `LICENSE-COMMERCIAL` says "Payzli Inc. (operating as Cutctx Labs)". Three variations. |
| **`cutctx_ee/LICENSE` vs root `LICENSE-COMMERCIAL` diverge** | ⚠️ MEDIUM | Different contact URLs (PitchToShip vs hello@). Different copyright lines. |
| **License DB world-readable** | ⚠️ MEDIUM | `~/.cutctx/licenses.db` — no `chmod 600` |
| **Rust-side licensing untracked** | ⚠️ MEDIUM | `crates/cutctx-core/src/licensing.rs` is not tracked in git |
| **2 license formats coexist** | ⚠️ LOW | Ed25519 + ECDSA P-256 both supported. No consolidation plan visible. |

---

## 5. Support Flows — 45/100 ❌

### What's documented
- `SLA.md` defines tiered support: Builder (community/best-effort), Team (email/business hours/next business day), Business (4hr), Enterprise (1hr/24/7)
- `artifacts/pilot-success-metrics.md` — pilot acceptance criteria
- `artifacts/50-client-outreach-plan.md` — SDR outreach plan
- `CHANGELOG.md` — well-maintained

### What's missing
| Issue | Severity | Detail |
|-------|----------|--------|
| **No support email** | 🔴 CRITICAL | `hello@cutctx.dev` bounces. All pilot inquiries, support tickets, security reports dead-letter. |
| **No support ticket system** | 🟠 HIGH | SLA references "email" support. No Zendesk, Intercom, Freshdesk, or Linear. |
| **No status page** | 🟠 HIGH | Customers cannot check uptime. No incident communication channel. |
| **No dedicated support channel for paid customers** | 🟠 HIGH | Community = OSS Discord only. No Slack Connect, no private support channel. |
| **No bug bounty program** | ⚠️ MEDIUM | SECURITY.md describes responsible disclosure process but email bounces. |
| **No knowledge base / FAQ** | ⚠️ MEDIUM | Docs are good (28+ MDX files) but no searchable help center. |

### Pilot support path
For the design-partner pilot, support can be: **founder handles all support via Discord DMs + shared Slack Connect channel + weekly sync call.** Automatable with a Linear board for tracking. Do not attempt self-serve support until a ticketing system is in place.

---

## 6. Security & Compliance — 72/100 ⚠️

### What's verified fixed from prior audits
- ✅ Loopback auth bypass closed (dashboard, savings, model endpoints)
- ✅ LIKE wildcard injection guard (`_escape_like()` + `ESCAPE "\"`)
- ✅ Kompress max-input DoS guard (`CUTCTX_KOMPRESS_MAX_WORDS`)
- ✅ CORS wildcard + credentials conflict resolved
- ✅ Health endpoint split: public vs admin-gated
- ✅ HMAC audit chain: `hmac.new(secret, msg, hashlib.sha256)` (was plain SHA-256)
- ✅ All 5 critical security items from prior audits resolved
- ✅ EgressEnforcer wired at 15+ call sites
- ✅ Residency verification via `hashlib.sha256().digest()`

### Still open — HIGH security
| Issue | Severity | Detail |
|-------|----------|--------|
| **License validation no-op** | 🔴 CRITICAL | Paying customer bypasses license check trivially. |
| **Cross-project memory leak** | 🔴 CRITICAL | Tenant isolation not enforced in memory backends. Multi-tenant pilot leaks memory between orgs. |
| **CCR retrieval + feedback endpoints no admin auth** | 🟠 HIGH | `/v1/retrieve/*`, `/v1/feedback` — entitlement-gated only, no auth check. |
| **Spend ledger tenant isolation** | 🟠 HIGH | Ledger not org-scoped. |

### Compliance readiness
| Standard | Status | Detail |
|----------|--------|--------|
| **SOC 2 Type I** | 🚧 In preparation | SOC2_CONTROLS.md maps controls. Target: Q4 2026. 6-month observation period required. |
| **SOC 2 Type II** | ❌ Not started | Requires 6-month observation after Type I. ETA mid-2027. |
| **GDPR** | ⚠️ Draft DPA | `docs/legal/DPA_TEMPLATE.md` exists. Needs legal review and execution. |
| **CCPA** | ⚠️ Draft DPA | Covered in DPA template. |
| **MSA** | ⚠️ Draft | `docs/legal/MSA_TEMPLATE.md` exists. "Cutctx, Inc." — entity doesn't match Payzli Inc. Needs legal review. |
| **DSR endpoints** | ✅ Implemented | `/v1/me/export`, `/v1/me/delete` — functional. |
| **Pentest** | ❌ Not done | Not commissioned. $15-25K estimated cost. |
| **HIPAA** | ❌ Not scoped | No BAA. Not a target for this phase. |
| **Vendor security questionnaire** | ✅ Ready | `docs/security/VENDOR_SECURITY_QUESTIONNAIRE.md` exists, 30+ questions with Cutctx-specific answers. |

### Security materials available for pilot buyers
- `SECURITY.md` — vulnerability reporting policy
- `docs/security/SECURITY_POLICY.md` — internal security policies
- `docs/security/SOC2_CONTROLS.md` — SOC 2 control mapping (64 lines, thorough)
- `docs/security/VENDOR_SECURITY_QUESTIONNAIRE.md` — 30+ item Q&A
- `artifacts/security-one-pager.md` — buyer-facing summary
- `docs/legal/LEAK_RESPONSE_RUNBOOK.md` — incident response procedure

---

## 7. Observability & Reliability — 65/100 ⚠️

### What's implemented
| Capability | Status | Detail |
|------------|--------|--------|
| Health endpoints | ✅ `/livez`, `/readyz`, `/health` | Per-component health checks, runtime metadata |
| Prometheus metrics | ✅ `/metrics` | Admin-gated. Request counts, latency, token usage, per-transform timing. |
| Structured logging | ✅ JSON format option | `CUTCTX_LOG_FORMAT=json` |
| Rate limiting | ✅ Token bucket | Per-IP, configurable requests/min + tokens/min |
| Webhook alerting | ✅ Signed outbound webhooks | With retry/backoff and dead-letter queue |
| OTEL metrics | ✅ `CutctxOtelMetrics` | Optional (default-off via CUTCTX_OTEL_ENABLED) |
| Langfuse tracing | ✅ `CutctxTracer` | Optional (default-off via CUTCTX_LANGFUSE_ENABLED) |
| Backup | ✅ CronJob in k8s | Daily backup to S3, 19+ SQLite stores, 30-day retention |
| HPA | ✅ Autoscaling | CPU 70% / memory 80% target, 2-10 replicas |
| PDB | ✅ PodDisruptionBudget | minAvailable: 1 |
| Docker healthcheck | ✅ Interval 30s, retries 3 | Calls /readyz |

### Critical gaps
| Gap | Severity | Detail |
|-----|----------|--------|
| **No centralized error tracking** | 🔴 HIGH | No Sentry, no OTel error exporter. Exceptions written to stderr only — invisible unless someone reads logs. |
| **No DR plan** | 🟠 HIGH | No documented disaster recovery procedure, no RTO/RPO targets, no cross-region failover. |
| **Backup gaps** | 🟠 HIGH | Backup CronJob lists 19 stores but prior audits noted not all paths were verified to exist at runtime. Non-k8s deployments have no backup. |
| **Only 2 Prometheus alert rules** | ⚠️ MEDIUM | HighErrorRate (5% 5xx) and HighLatency (p99 >2s). No alerts for: backup failure, license expiry, high queue depth, disk usage, memory pressure. |
| **No SLI/SLO definitions** | ⚠️ MEDIUM | SLA defines support response times but no measurable service level objectives. |
| **No capacity planning** | ⚠️ MEDIUM | HPA exists but no documented load testing or capacity model. |

---

## 8. Documentation & Legal Pages — 68/100

### What's excellent
- `PRODUCT_GUIDE.md` (923 lines) — comprehensive sales/technical guide with objection handling
- `README.md` (415 lines) — thorough install guide, benchmarks, agent compatibility matrix
- 28+ MDX docs files — covering architecture, compression, CCR, memory, configuration, benchmarks
- `CHANGELOG.md` — well-structured
- `CONTRIBUTING.md` — contributor guide
- `SECURITY.md` — vulnerability reporting policy
- `PRIVACY.md` (101 lines) — clear local-first data handling description
- `TERMS.md` (76 lines) — draft ToS with proper structure
- `docs/legal/MSA_TEMPLATE.md` (215 lines) — comprehensive MSA draft
- `docs/legal/DPA_TEMPLATE.md` (227 lines) — GDPR + CCPA compliant DPA draft
- `docs/legal/LEAK_RESPONSE_RUNBOOK.md` — incident response
- `docs/legal/DMCA_TAKEDOWN_TEMPLATE.md` — DMCA process

### What's missing or broken
| Issue | Severity | Detail |
|-------|----------|--------|
| **Docs not published** | 🔴 HIGH | All docs link to `https://cutctx.com/docs` which is NXDOMAIN. Docs site not deployed. |
| **TERMS.md header**: "must be reviewed by qualified legal counsel" | ⚠️ HIGH | Template text clearly states it's a draft. Cannot be used in commercial transactions without legal review. |
| **Legal entity in MSA ≠ actual entity** | ⚠️ HIGH | MSA template says "Cutctx, Inc." — actual entity operating as Cutctx is "Payzli Inc." This will fail procurement vendor vetting. |
| **No wizard/guided setup docs** | ⚠️ MEDIUM | First-run experience is `cutctx proxy --help`. No interactive walkthrough. |
| **No troubleshooting docs for common problems** | ⚠️ MEDIUM | `docs/content/docs/troubleshooting.mdx` exists but doesn't cover common customer issues. |

---

## 9. Marketing & Competitive Differentiation — 62/100

### What's strong
| Strength | Detail |
|----------|--------|
| **CCR (reversible compression)** | No competitor has this. Unique moat. |
| **5-source savings attribution** | Per-source breakdown (JSON, AST, code, logs, diffs, images) + USD attribution. CFO-grade. |
| **Multi-format compressor pipeline** | 17 strategies across JSON, code, text, logs, diffs, images, audio. |
| **Cross-agent memory** | Shared store across Claude, Codex, Gemini. Unique. |
| **Cross-provider cache alignment** | Deduplication across Anthropic + OpenAI + Gemini. Unique. |
| **Local-first architecture** | All processing on-premise. No data leaves customer infra. |
| **Agent compatibility** | 14 agents supported. Only tool with this breadth. |

### What's weak
| Weakness | Severity | Detail |
|----------|----------|--------|
| **No website** | 🔴 CRITICAL | First impression is a GitHub README. Enterprise buyers Google "cutctx" → nothing. |
| **No case studies** | 🔴 HIGH | Nothing to send a skeptical buyer. No logos, no quotes, no numbers from real deployments. |
| **No benchmark page** | 🟠 HIGH | Benchmarks exist in repo (`benchmarks/`, `benchmark_results.md`) but no published comparison page. |
| **No social proof** | 🟠 HIGH | No G2, no Capterra, no Product Hunt launch. No Twitter presence. |
| **Company name confusion** | ⚠️ MEDIUM | Product = "Cutctx", entity = "Payzli Inc.", brand = "Cutctx Labs", GitHub = "cutctx/cutctx". Inconsistent. |
| **GTM materials exist but no distribution** | ⚠️ MEDIUM | 3 blog posts written but not published. Outreach plan exists but no outbound campaigns running. |

### Competitive positioning
**Cutctx's defensible moat** = (CCR reversible compression) × (multi-format pipeline) × (cross-agent memory) × (cross-provider cache alignment) × (local-first data handling)

**Largest competitive gaps vs threats:**
| Gap | Threat | Impact |
|-----|--------|--------|
| No verification/hallucination guard | Entroly, LeanCTX ctx_verify | Enterprise buyers ask "how do I know compression didn't break my agent?" |
| Only 3 MCP tools vs 81 (LeanCTX) | LeanCTX | MCP is becoming table stakes; LeanCTX sets the bar |
| No read-side intelligence | LeanCTX (10 read modes) | User perceives less value — LeanCTX gets 60-90% savings on every file read |
| Compression speed (5-10K tok/s) | Morph Compact (33K tok/s) | Performance benchmark comparison |
| No deterministic-only mode | RTK (always deterministic) | Predictability-sensitive buyers prefer deterministic |

---

## 10. Enterprise Readiness — 45/100 ❌

### Enterprise requirements (standard for $60-150K/yr deals)
| Requirement | Cutctx Status | Buyer Expectation |
|-------------|---------------|-------------------|
| **SOC 2 Type II** | ❌ Not started (ETA mid-2027) | Required for procurement |
| **SAML SSO** | ❌ OIDC only | SAML is table-stakes for most enterprises |
| **Pentest report** | ❌ Not commissioned | Required for security review |
| **MSA with correct entity** | ❌ Template only; entity mismatch | "Cutctx, Inc." ≠ Payzli Inc. — fails vendor onboarding |
| **Multi-key admin API** | ❌ Single global admin key | Per-team, per-service keys with rotation |
| **WebAuthn MFA** | ❌ TOTP only (not mandatory) | Many orgs require FIDO2/WebAuthn |
| **CAIQ/SIG-Lite** | ❌ Not prepared | Often required for initial vendor vetting |
| **Enterprise support SLA** | ⚠️ Draft exists | SLA.md defines tiers but no tooling behind it |

### What enterprise buyers CAN get today
| Capability | Status |
|------------|--------|
| SSO admin authentication (OIDC) | ✅ Implemented |
| RBAC (Viewer/Operator/Admin, 15+ permissions) | ✅ Implemented |
| Audit log with HMAC tamper-evident chain | ✅ Implemented |
| Retention controls (CCR, audit, memory expiry) | ✅ Implemented |
| Fleet management APIs | ✅ Implemented |
| SCIM provisioning APIs | ✅ Implemented |
| Air-gap deployment support | ✅ Documented |
| Security review packet | ✅ Available (7 documents) |
| Local-first deployment (no data leaves infra) | ✅ Core architecture |

---

## Scoring Summary

| Dimension | Score | Status |
|-----------|-------|--------|
| Onboarding & Installation | 74/100 | ⚠️ 2 blockers (NXDOMAIN, dashboard assets) |
| Pricing | 72/100 | ⚠️ Contradictions resolved; no published pricing page |
| Billing | 30/100 | ❌ No working checkout, license enforcement no-op |
| Licensing | 62/100 | ⚠️ Clear model, no enforcement, entity mismatch |
| Support Flows | 45/100 | ❌ No email, no ticket system, no status page |
| Security & Compliance | 72/100 | ⚠️ Well-defended, missing tenant isolation + enterprise auth items |
| Observability & Reliability | 65/100 | ⚠️ No error tracking, partial backup, thin alerting |
| Documentation & Legal | 68/100 | ⚠️ Comprehensive drafts, not published, entity mismatch |
| Marketing & Differentiation | 62/100 | ⚠️ Strong moat, no website, no case studies, no social proof |
| Enterprise Readiness | 45/100 | ❌ 2-3 months of work + SOC 2 timeline |
| **Overall** | **58/100** | **CONDITIONAL GO for pilot; NO-GO for self-serve/enterprise** |

---

## Recommended Path Forward

### Week 1-2: Ship design-partner pilot (4 P0 items)
1. **Register cutctx.dev** — $12/year, redirect to GitHub README as landing page. Unblocks all 161 doc links, security contact, and email. **1 hour.**
2. **Set up email forwarding** — `hello@`, `security@`, `conduct@` to founder's email. **30 minutes.**
3. **Fix license enforcement** — `watermark.py:185-204` needs a `raise LicenseViolation` when DB returns no matching key. **2 hours.**
4. **Prepare pilot contract** — Fill MSA template with correct entity (Payzli Inc.), get counsel review. **1 week (legal).**

### Week 3-4: First design partner onboarded
- Founder handles install, config, and support via Discord/Slack
- Collect case study data: before/after token counts, dollar savings, user experience
- Run weekly sync call per partner
- Surface benchmark numbers from real deployment → material for website

### Week 5-8: Post-pilot hardening
| Item | Effort | Why |
|------|--------|-----|
| Wire direct Stripe Checkout | 2-3d | Replace dead PitchToShip path |
| Fix tenant isolation in memory backends | 3-5d | Required for multi-tenant pilots |
| Add admin auth to CCR retrieval + feedback | 1d | HIGH security gap |
| Wire error tracking (Sentry) | 1d | Operational visibility |
| Build billing UI in dashboard | 1w | Customer self-service |
| Publish website with docs + pricing | 1w | Fix the NXDOMAIN gap |

### Week 9-16: Scale to 3-5 design partners ($90-300K ARR)
- Fund SOC 2 engagement ($45-70K)
- Fund pentest ($15-25K)
- Build case studies from pilot data
- Start SAML SSO + multi-key admin implementation

### Month 6-12: Enterprise readiness
- SOC 2 Type I report → enterprise GO
- SAML SSO + WebAuthn MFA → enterprise GO
- Website + billing dashboard → public self-serve GO
- Real case studies from design partners → public self-serve GO

---

## Final Recommendation

**CONDITIONAL GO for design-partner pilot.** The core product is exceptional — best-in-class compression pipeline, reversible CCR, cross-agent memory, multi-provider support, strong security posture, production-grade infra (k8s, Helm, CI/CD, monitoring). The engineering team has done outstanding work.

**But the commercial surface is not ready for self-serve or enterprise.** Two fundamental facts remain blocked from the Jul 6 audit: (a) cutctx.dev is NXDOMAIN — no website, no docs site, all emails bounce; (b) there is no working payment path. These are not hard to fix (domain registration = $12, Stripe Checkout = 2 days), but they must be fixed before any dollar changes hands.

**Do not sell to self-serve or enterprise buyers today.** Sell 1-5 named design partners. Founder does all onboarding. Billing is invoice-based. Each partner gets 14 days and a weekly sync. In 90 days you'll have case studies, revenue, and a clear path to self-serve.

---

*Document classification: Paying-customer readiness assessment. Scope: full repository as of `main @ 418ae99a`. Independent analysis — all findings from read-only codebase recon + live web probes. Supersedes `audit/paying-customer-readiness-2026-07-06.md`.*
