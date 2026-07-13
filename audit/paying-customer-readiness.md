# Paying-Customer Readiness Assessment — 2026-07-10 (v2)

**Product:** Cutctx v0.30.0 (HEAD `418ae99a`) — Context compression layer for AI agents
**Method:** 10 parallel domain audits (architecture, frontend, backend, security, database, performance, testing, UX, accessibility, competitive) + consolidated synthesis + commercial analysis
**Predecessors:** `audit/paying-customer-readiness-2026-07-06.md` (Jul 6), `audit/paying-customer-readiness.md` (Jul 10 v1)

---

## Go / No-Go Verdict

| Channel | Verdict | Score | Change from Jul 6 | One-line reason |
|---------|---------|-------|-------------------|-----------------|
| **Design-partner pilot** (1-5 named accounts, founder-led, invoice-based) | ✅ **CONDITIONAL GO** | 82/100 | → Same | Core product outstanding; 4 conditions cover the gaps |
| **Public self-serve** (open signups, Stripe checkout) | ❌ **NO-GO** | 56/100 | → Same | No website, no billing pipeline, no working email, no CI security scanning, 3K-line CSS monolith |
| **Enterprise sales** ($60-150K+/yr, procurement, SOC 2) | ❌ **NO-GO** | 42/100 | -3 (new data) | 2-3 months eng + 6mo SOC 2 + 12-person-months of technical debt in 3 monoliths |

### Conditions for Design-Partner Pilot GO
1. **Founder-led onboarding** — no self-serve flow; founder handles install, config, and initial support
2. **Invoice-based billing** — no Stripe checkout; send invoices and collect via wire/ACH
3. **Pre-pilot security review** — share SECURITY.md + SOC2_CONTROLS.md + security-one-pager.md
4. **14-day pilot term** — bounded engagement with explicit success criteria per partner
5. **Pilot contract with correct entity** — MSA must say "Payzli Inc." not "Cutctx, Inc."
6. **Acknowledge monolith risk** — `server.py` (4.8K lines) + `admin.py` (2.6K) + `content_router.py` (3.2K) represent structural debt that will slow response to pilot feedback

---

## 1. Onboarding & Installation — 74/100 ⚠️

### What works
- `pip install cutctx-ai && cutctx proxy` — functional, tested
- 14 agent wrap commands (Claude Code, Cursor, Codex, aider, etc.)
- Docker two-stage build with distroless option + HEALTHCHECK
- docker-compose + Helm chart + full k8s manifests
- MCP server (3 tools) + memory MCP
- Python + TypeScript SDKs on PyPI and npm

### What's broken or missing (from 10-agent audit)

| Issue | Severity | Source | Detail |
|-------|----------|--------|--------|
| **No website** — `cutctx.dev` + `cutctx.com` NXDOMAIN | 🔴 BLOCKER | Commercial | First Google click fails. All docs links bounce. |
| **All emails bounce** — `hello@`, `security@`, `conduct@` all NXDOMAIN | 🔴 BLOCKER | Commercial | Security disclosures, license requests, support dead-letter. |
| **161+ cutctx.dev/com references** in source | 🟠 HIGH | Commercial | Every README link, every doc, every security notice. |
| **Dashboard assets 404 in production** | 🟠 HIGH | UX audit | `base` not set in vite.config.js. Dashboard broken in deployed proxy. |
| **No `cutctx doctor` command** | ⚠️ MEDIUM | UX audit | No built-in config validation for new users. |
| **No first-run welcome** | ⚠️ MEDIUM | UX audit | 38+ commands presented with no guidance. |
| **CLI help not grouped** | ⚠️ MEDIUM | UX audit | No "Getting Started / Daily Use / Advanced" sections. |
| **OG image says "My App"** | ⚠️ LOW | UI audit | Shows on social previews. |

### Scoring
| Sub-dimension | Score | Source |
|--------------|-------|--------|
| pip install + wrap | 90/100 | Verified working |
| Docker/k8s/Helm | 90/100 | Production-grade |
| CLI first-run | 35/100 | UX audit — 38+ command wall, no welcome |
| Dashboard production serving | 40/100 | UI audit — /assets/ 404 |
| Self-service (docs + website) | 20/100 | NXDOMAIN blocks everything |

---

## 2. Pricing — 72/100 ⚠️

### Current tiers (well-structured)
- **Builder:** Free — OSS engine, local dashboard, community support
- **Team:** $1,500/mo — team analytics, budget controls, policy presets
- **Business:** $3,500/mo — workspace model, historical/exportable reports, K8s/Helm
- **Enterprise:** Custom $60-150K/yr — SSO, RBAC, audit, fleet, SCIM, air-gap

### Pricing vs competitors (from competitive audit)
| Tier | Cutctx | RTK Cloud | Helicone | Portkey | LeanCTX |
|------|--------|-----------|----------|---------|---------|
| Free | ✅ Full engine | ✅ CLI free | Limited | Limited | Free tier |
| Team | $1,500/mo | $15/dev/mo | $120/mo | $199/mo | Not disclosed |
| Enterprise | $60-150K/yr | — | Custom | Custom | Custom |

**Competitive position:** Cutctx is premium-priced vs Helicone/Portkey. Defensible because: (a) CCR reversibility no competitor matches, (b) 5-source savings attribution, (c) multi-format pipeline, (d) cross-agent memory. **Risk:** if Helicone/Portkey add native compression, Cutctx's distribution moat erodes — what remains is compression depth + local-first.

### Issues
| Issue | Severity | Source | Detail |
|-------|----------|--------|--------|
| **No pricing on website** | 🟠 HIGH | No website exists. |
| **Pricing contradiction resolved** | ✅ FIXED | docs/pricing.html now shows $1,500/mo (was $49 in Jul 6 audit). |
| **No self-serve upgrade path** | ⚠️ MEDIUM | No Stripe Checkout → user must contact human. |

---

## 3. Billing — 30/100 ❌

### What's built
- Stripe webhook handlers exist (`stripe_webhook.py`) for `checkout.session.completed`, `.deleted`, `.updated`
- Ed25519 offline license signing + CRL revocation
- License DB with seat tracking, checkout-seat, heartbeat APIs
- PitchToShip integration for centralized license management

### What's broken (unchanged from Jul 6 — still blocking)
| Issue | Severity | Detail |
|-------|----------|--------|
| **No working checkout path** | 🔴 CRITICAL | `cli/billing.py` routes through PitchToShip which returns HTML, not API. No direct Stripe Checkout Session creation. A customer literally cannot pay. |
| **License validation is a no-op** | 🔴 CRITICAL | `watermark.py:185-204` queries DB but doesn't refuse service. Any key passes. |
| **No billing UI in dashboard** | 🟠 HIGH | No Billing.jsx, Subscription.jsx, Pricing.jsx. Customer sees nothing. |
| **Missing `subscription.created` handler** | 🟠 HIGH | Would orphan subscriptions on payment method changes. |
| **PitchToShip dependency** | 🟠 HIGH | Billing depends on a third-party service not owned by Cutctx. No fallback. |

### Scoring
| Sub-dimension | Score | Reasoning |
|--------------|-------|-----------|
| Payment collection | 0/100 | No working checkout. |
| License enforcement | 15/100 | Validates but doesn't deny. |
| Billing UI | 10/100 | Not built. |
| Webhook handlers | 60/100 | Code exists, untested end-to-end. |

---

## 4. Licensing — 62/100 ⚠️

### What's good
| Aspect | Detail |
|--------|--------|
| Open-core model | Clearly documented in LICENSING.md — Apache 2.0 boundary at `cutctx_ee/` |
| Ed25519 signing + CRL | Offline license validation with revocation |
| Tier enforcement | `entitlements.py` gates features by BUILDER < TEAM < BUSINESS < ENTERPRISE |
| Wheel separation | OSS wheel excludes `cutctx_ee/`; commercial wheel built from `packaging/cutctx-ee/` |

### Issues
| Issue | Severity | Detail |
|-------|----------|--------|
| **License enforcement no-op** | 🔴 CRITICAL | Same as billing — validates but doesn't deny. |
| **Entity mismatch** | 🟠 HIGH | `cutctx_ee/LICENSE:7` = "Payzli Inc.", `cutctx_ee/__init__.py:2` = "Cutctx Labs", root `LICENSE-COMMERCIAL` says "Payzli Inc. (operating as Cutctx Labs)". Three variations. |
| **MSA template entity wrong** | 🟠 HIGH | `docs/legal/MSA_TEMPLATE.md` = "Cutctx, Inc." Actual entity = Payzli Inc. Fails vendor vetting. |
| **License DB world-readable** | ⚠️ MEDIUM | `~/.cutctx/licenses.db` — no `chmod 600`. |
| **Rust licensing untracked** | ⚠️ MEDIUM | `crates/cutctx-core/src/licensing.rs` not in git. |

---

## 5. Support Flows — 45/100 ❌

### Status (from commercial + UX audits)
| Item | Status | Source |
|------|--------|--------|
| SLA.md | ✅ Drafted, tiered (Builder-Enterprise) | Commercial |
| Pilot success metrics | ✅ Documented | Commercial |
| SDR outreach plan | ✅ Documented | Commercial |
| **Support email** | ❌ NXDOMAIN — bounces | Commercial |
| **Ticket system** | ❌ No Zendesk/Intercom | Commercial |
| **Status page** | ❌ No uptime visibility | Commercial |
| **Paid support channel** | ❌ No Slack Connect for paid | Commercial |
| **Knowledge base / FAQ** | ❌ Docs exist but no searchable help center | UX audit |

### Pilot path
Founder handles all support via Discord DMs + shared Slack Connect + weekly sync call. Use Linear for tracking. Do not attempt self-serve support until a ticketing system is in place.

---

## 6. Security & Compliance — 72/100 ⚠️

### All 5 critical items from prior audits: VERIFIED FIXED ✅
- Loopback auth bypass closed
- LIKE wildcard injection guard
- Kompress DoS guard
- CORS wildcard resolved
- HMAC audit chain (now `hmac.new()`)

### New findings from security agent (78/100)
| Issue | Severity | Detail | Source |
|-------|----------|--------|--------|
| **Dashboard HTML served unauthenticated** | 🟠 HIGH | `/dashboard` endpoint returns HTML to any client. JS bundles enumerable. | Security audit H-1 |
| **SSO validator per-request JWKS fetch** | 🟠 HIGH | No shared JWKS cache — every request triggers IdP fetch. Performance + DoS vector. | Security audit H-2 |
| **No security headers** | ⚠️ MEDIUM | No CSP, HSTS, X-Frame-Options, X-Content-Type-Options on any response. | Security audit M-1 |
| **Rate limiting in-memory only** | ⚠️ MEDIUM | Lost on restart. No cross-replica coordination. 1000 bucket limit hardcoded. | Security audit M-3 |
| **Exception text leaked in 5+ sites** | ⚠️ MEDIUM | Raw `str(e)` in HTTP responses. | Confirmed |

### Compliance readiness
| Standard | Status | Detail |
|----------|--------|--------|
| **SOC 2 Type I** | 🚧 In preparation | Controls documented. Target Q4 2026. 6mo observation required. |
| **SOC 2 Type II** | ❌ Not started | ETA mid-2027 post-Type I. |
| **GDPR/CCPA DPA** | ⚠️ Draft | `docs/legal/DPA_TEMPLATE.md` exists. Needs legal review. |
| **MSA** | ⚠️ Draft | Entity is "Cutctx, Inc." — wrong. Needs fix + legal review. |
| **DSR endpoints** | ✅ Implemented | `/v1/me/export`, `/v1/me/delete` functional. |
| **Pentest** | ❌ Not done | Not commissioned. $15-25K est. |
| **Security questionnaire** | ✅ Ready | VENDOR_SECURITY_QUESTIONNAIRE.md (30+ items). |

### Available security materials for pilot buyers
7 documents: SECURITY.md, SECURITY_POLICY.md, SOC2_CONTROLS.md, VENDOR_SECURITY_QUESTIONNAIRE.md, security-one-pager.md, LEAK_RESPONSE_RUNBOOK.md, DMCA_TAKEDOWN_TEMPLATE.md. **All reference cutctx.dev NXDOMAIN** — fix domain to make materials usable.

---

## 7. Observability & Reliability — 65/100 ⚠️

### New findings from architecture + backend + performance audits

| Capability | Status | Source | Detail |
|------------|--------|--------|--------|
| Health endpoints | ✅ /livez, /readyz, /health | Architecture | Per-component checks |
| Prometheus metrics | ✅ /metrics (admin-gated) | Backend | Comprehensive counters |
| Structured logging | ✅ JSON option | Backend | `CUTCTX_LOG_FORMAT=json` |
| Rate limiting | ✅ Token bucket | Backend | Per-IP, configurable |
| Webhook alerting | ✅ Signed outbound with DLQ | Backend | Retry/backoff |
| OTEL metrics | ✅ Optional | Backend | Default-off |
| Langfuse tracing | ✅ Optional | Backend | Default-off |
| **No centralized error tracking** | ❌ MISSING | Backend | No Sentry/OTel exporter. Exceptions to stderr only. |
| **No DR plan** | ❌ MISSING | Architecture | No RTO/RPO, no cross-region failover. |
| **Backup gaps** | ⚠️ PARTIAL | Database audit | CronJob lists 19 stores but not all verified at runtime. Non-k8s deployments have no backup. |
| **Only 2 Prometheus alert rules** | ⚠️ WEAK | Architecture | HighErrorRate + HighLatency. No alerts for: backup failure, license expiry, high queue depth. |
| **No SLI/SLO definitions** | ⚠️ MISSING | Architecture | No measurable service level objectives. |

### Structural reliability risks (from architecture audit: 62/100)
| Risk | Detail | Impact |
|------|--------|--------|
| **Triple-stack deployment** | Rust proxy → Python proxy → Rust via PyO3 | 2 HTTP servers, 2 event loops. Double failure mode. |
| **server.py god object** | 4,819 lines in one file | Every change risks breaking the full proxy. |
| **In-memory state** | Metrics, rate limit buckets lost on restart | No horizontal scaling without Redis/external store. |
| **3 monolith hotspots** | server.py (4.8K) + admin.py (2.6K) + content_router.py (3.2K) | 10.7K lines of change-risk concentration. |

---

## 8. Documentation & Legal — 68/100 ⚠️

### New findings from UX + security + architecture audits

| Document | Status | Source | Detail |
|----------|--------|--------|--------|
| PRODUCT_GUIDE.md | ✅ 923 lines | Commercial | Comprehensive sales guide |
| README.md | ✅ 415 lines | Commercial | Thorough install + benchmarks |
| Docs (28+ MDX) | ✅ Well-structured | UX audit | Fumadocs framework |
| CHANGELOG.md | ✅ Well-maintained | Commercial | |
| SECURITY.md | ✅ Drafted but emails bounce | Security | References cutctx.dev NXDOMAIN |
| PRIVACY.md | ✅ 101 lines, clear | Commercial | Good local-first framing |
| TERMS.md | ⚠️ Draft — "must be reviewed by counsel" | Commercial | Template text still present |
| MSA_TEMPLATE.md | ⚠️ Wrong entity | Commercial | "Cutctx, Inc." → must be Payzli Inc. |
| DPA_TEMPLATE.md | ✅ 227 lines | Commercial | GDPR + CCPA compliant draft |
| LEAK_RESPONSE_RUNBOOK.md | ✅ Exists | Security | Incident response documented |
| **Docs not published** | ❌ NXDOMAIN | UX audit | All docs link to cutctx.com/docs which doesn't resolve. |
| **No landing page** | ❌ NXDOMAIN | UX audit | Just a redirect to /docs — no value prop. |

### Scoring
| Sub-dimension | Score | Reasoning |
|--------------|-------|-----------|
| Technical docs | 80/100 | Comprehensive, well-structured |
| Legal docs | 65/100 | All drafted, none reviewed by counsel |
| Publishing | 20/100 | All pages unreachable (NXDOMAIN) |
| First-run guidance | 35/100 | UX audit — no welcome, no wizard |

---

## 9. Marketing & Competitive Differentiation — 62/100 ⚠️

### Defensible Moat (from competitive audit — 7 competitors analyzed)
| Moat | Status | Competitor benchmark | Sustainability |
|------|--------|---------------------|---------------|
| **CCR reversibility** | ✅ Unique | No competitor matches | Strong — hard to replicate |
| **5-source savings attribution** | ✅ Unique | Helicone/Portkey have per-request only | Medium — could be copied |
| **Multi-format pipeline (17 strategies)** | ✅ Best-in-class | RTK = shell only. LeanCTX = 3 types. | Medium — LeanCTX closing |
| **Cross-agent memory** | ✅ Unique | No competitor has shared agent store | Medium — hard but not impossible |
| **Cross-provider cache alignment** | ✅ Unique | No competitor deduplicates across providers | Strong — novel architecture |

### Competitive Threats (new from competitive audit)
| Threat | Severity | Detail | Mitigation timeline |
|--------|----------|--------|-------------------|
| **LeanCTX** (81 MCP tools, daily shipping, knowledge graph) | 🔴 HIGH | Fastest iteration. Same local-first thesis. GitHub community growing. | Phase 2 (expand MCP to 20+, add read-side intelligence) |
| **Gateway absorption** (Helicone/Portkey adding compression) | 🟠 HIGH | If they add native compression, Cutctx loses distribution advantage. | Phase 1-2 (lean on CCR + local-first as differentiators) |
| **Morph Compact** (33K tok/s, byte-identical, SOC 2) | ⚠️ MEDIUM | Performance + compliance advantage for enterprise. | Phase 2 (add benchmark page, improve Kompress speed) |
| **RTK** (68K stars, deterministic, Homebrew) | ⚠️ LOW | Shell-only. Complementary, not competitive. | None needed. Ship RTK integration. |

### Marketing gaps (from commercial + competitive audits)
| Gap | Severity | Detail |
|-----|----------|--------|
| **No website** | 🔴 CRITICAL | First Google impression is nothing. |
| **No case studies** | 🔴 HIGH | No logos, no quotes, no real deployment numbers. |
| **No benchmark page** | 🟠 HIGH | Benchmarks exist in repo but no published comparison. |
| **No social proof** | 🟠 HIGH | No G2, no Product Hunt, no Twitter presence. |
| **Company name confusion** | ⚠️ MEDIUM | Product="Cutctx", entity="Payzli Inc.", brand="Cutctx Labs", GH="cutctx/cutctx". |
| **3 blog posts written, 0 published** | ⚠️ MEDIUM | GTM content exists in gtm/ but not deployed. |

---

## 10. Enterprise Readiness — 42/100 ❌

### New findings from architecture + security + competitive audits

| Requirement | Cutctx Status | Buyer Expectation | Remediation |
|-------------|---------------|-------------------|-------------|
| **SOC 2 Type II** | ❌ Not started (ETA mid-2027) | Required | Fund engagement in Phase 2 |
| **SAML SSO** | ❌ OIDC only (no SAML) | Table-stakes | Phase 3 |
| **Pentest report** | ❌ Not commissioned | Required for security review | Phase 2 ($15-25K) |
| **MSA correct entity** | ❌ "Cutctx, Inc." ≠ Payzli Inc. | Fails vendor onboarding | Week 1 fix |
| **Multi-key admin** | ❌ Single global admin key | Per-team, per-service keys | Phase 2-3 |
| **WebAuthn MFA** | ❌ TOTP only (not mandatory) | Many orgs require FIDO2 | Phase 3 |
| **CAIQ/SIG-Lite** | ❌ Not prepared | Often required for vetting | Phase 2 |
| **DR plan** | ❌ Not documented | Required for diligence | Phase 2 |
| **Architecture debt** | ⚠️ server.py 4.8K, triple-stack | Diligence flags complexity | Phase 1-2 |

### What enterprise buyers CAN get today
| Capability | Status | Detail |
|------------|--------|--------|
| SSO admin auth (OIDC) | ✅ Implemented | Works with Okta, Azure AD, Google |
| RBAC (15+ permissions) | ✅ Implemented | Viewer/Operator/Admin |
| HMAC audit chain | ✅ Implemented | Tamper-evident, length-prefixed |
| Retention controls | ✅ Implemented | CCR, audit, memory expiry |
| Fleet management APIs | ✅ Implemented | Multi-deployment visibility |
| SCIM provisioning | ✅ Implemented | User/group management |
| Air-gap support | ✅ Documented | HF_HUB_OFFLINE, ORT_STRATEGY |
| Security review packet | ✅ Available | 7 documents |

---

## 11. New Findings from 10-Agent Audit (Delta Analysis)

| Finding | Domain | Severity | Impact on Paying-Customer Readiness |
|---------|--------|----------|--------------------------------------|
| server.py is a 4.8K-line god object | Architecture | 🔴 HIGH | Slows response to pilot feedback. Every enterprise feature addition risks breakage. |
| 3 monoliths = 10.7K lines of change risk | Architecture | 🟠 HIGH | admin.py + content_router.py compound the problem. |
| Triple-stack deployment (Rust→Python→Rust) | Architecture | ⚠️ MEDIUM | 2 HTTP servers to monitor and troubleshoot. |
| 4 debug print() statements in streaming hot path | Backend | 🟠 HIGH | Pollutes logs. I/O overhead in latency-sensitive path. |
| Bare `except Exception` swallows errors (69-127 sites) | Backend | 🟠 HIGH | Production errors become invisible. |
| SSO validator creates per-request JWKS fetch | Security | 🟠 HIGH | Performance + DoS vector. Every request hits IdP. |
| Dashboard HTML unauthenticated | Security | 🟠 HIGH | Attack surface: JS bundles enumerable. |
| No security headers (CSP, HSTS, etc.) | Security | ⚠️ MEDIUM | Standard defense missing. |
| No migration system across 19+ SQLite DBs | Database | 🟠 HIGH | Schema changes require manual SQL. Impossible to roll back. |
| Inconsistent WAL mode across SQLite stores | Database | ⚠️ MEDIUM | Concurrency inconsistency. |
| `copy.deepcopy` on payloads = #1 latency source | Performance | 🟠 HIGH | 30-100ms P95 overhead on large payloads. |
| Compression executor saturation | Performance | ⚠️ MEDIUM | Hard ceiling on throughput. |
| 22 EE modules (3,939 LOC) untested | Testing | 🟠 HIGH | Enterprise code with zero coverage. |
| 59 time.sleep() calls in tests create flakiness | Testing | ⚠️ MEDIUM | CI false positives erode trust. |
| No skip-to-content link | UX/Accessibility | ⚠️ MEDIUM | Keyboard users tab through entire sidebar. |
| 38+ command wall with no grouping | UX | ⚠️ MEDIUM | New users overwhelmed. |
| No `cutctx doctor` | UX | ⚠️ MEDIUM | No config validation tool. |
| 62% WCAG AA compliance | Accessibility | ⚠️ MEDIUM | Legal risk for regulated buyers. |
| Dashboard /assets/ 404 in production | UI | 🟠 HIGH | Dashboard broken in deployed proxy. |

---

## Scoring Summary

| Dimension | Jul 6 Score | Jul 10 v2 | Δ | Key delta driver |
|-----------|-------------|-----------|---|-----------------|
| Onboarding & Installation | 74/100 | 74/100 | → | Same blockers (NXDOMAIN, /assets/ 404) |
| Pricing | 71/100 | 72/100 | +1 | Pricing contradiction resolved |
| Billing | 35/100 | 30/100 | -5 | Confirmed no working checkout path |
| Licensing | 65/100 | 62/100 | -3 | Entity mismatch across 3 files confirmed |
| Support Flows | 50/100 | 45/100 | -5 | No ticket system, no status page, email bounces |
| Security & Compliance | 72/100 | 72/100 | → | New findings (dashboard unauthenticated, SSO caching) balanced by prior fixes |
| Observability & Reliability | 65/100 | 65/100 | → | New findings (triple-stack risk, no DR plan) |
| Documentation & Legal | 68/100 | 68/100 | → | Same — all drafted, none published, entity wrong |
| Marketing & Differentiation | 62/100 | 62/100 | → | 7 competitors mapped, moat confirmed, LeanCTX threat quantified |
| Enterprise Readiness | 45/100 | 42/100 | -3 | Architecture debt (3 monoliths, triple-stack) quantified |
| **Overall** | **58/100** | **56/100** | **-2** | New findings add precision; core verdict unchanged |

---

## Final Recommendation

### ✅ CONDITIONAL GO — Design-Partner Pilot

**Why:** The core product is exceptional — best-in-class compression pipeline, unique reversible CCR, cross-agent memory, multi-provider support, strong security posture, production-grade deployment infra, and a defensible competitive moat. No startup at this stage should wait for perfect billing infrastructure or a fully decomposed monolith before getting first revenue.

**Conditions (must be met per partner):**
1. Founder-led everything (onboarding, support, billing via invoice)
2. 14-day bounded pilot term with explicit success criteria
3. Pre-pilot security review packet (7 documents exist — fix cutctx.dev first)
4. Pilot contract uses correct entity (Payzli Inc.)
5. Acknowledge that architecture debt (server.py monolith, triple-stack) will slow feedback response

### ❌ NO-GO — Public Self-Serve

**Blockers:** No website (NXDOMAIN), no working checkout, no error tracking, dashboard 404 in production, no CI security scanning, 22 EE modules (3,939 LOC) untested, 59 flaky time.sleep() tests. Estimate: ~6 weeks of focused work to clear.

### ❌ NO-GO — Enterprise Sales

**Blockers:** SOC 2 observation period (6mo minimum), SAML SSO missing, architecture debt (3 monoliths, triple-stack) flagged by technical diligence, wrong entity in MSA. Estimate: 2-3 months engineering + 6 months SOC 2.

---

## Action Plan for Next 90 Days

### Week 1-2: Unblock pilot (4 items, $12 + 4h)
1. Register cutctx.dev ($12/yr)
2. Set up email forwarding (30 min)
3. Fix license enforcement — deny when no key (2h)
4. Fix MSA entity to Payzli Inc. (1h)

### Week 3-4: First pilot onboarded
- Founder handles install, config, support via Discord + Slack
- Collect baseline: before/after token counts, dollar savings, user experience
- Weekly sync call per partner

### Week 5-8: Post-pilot hardening (6 items, ~2 weeks)
1. Wire Stripe Checkout (3d) — replace dead PitchToShip
2. Fix dashboard /assets/ 404 (1h) — set `base` in vite.config.js
3. Fix SSO JWKS caching (1d) — shared cache across requests
4. Add security headers — CSP, HSTS, X-Frame-Options (1d)
5. Remove 4 debug print() from streaming.py (15 min)
6. Start architecture debt: split server.py by domain (1w)

### Week 9-16: Scale to 3-5 partners ($90-300K ARR)
- Fund SOC 2 engagement ($45-70K)
- Fund pentest ($15-25K)
- Build case studies from pilot data
- Start SAML SSO + multi-key admin

### Month 6-12: Enterprise readiness
- SOC 2 Type I → enterprise GO
- SAML SSO + WebAuthn MFA → enterprise GO
- Website + billing dashboard → public self-serve GO
- Real case studies → public self-serve GO

---

## Bottom Line

**Ship the pilot today.** The engineering is exceptional. The commercial surface has 4 small blockers totaling $12 + 4 hours of work. Don't wait for Stripe, don't wait for decomposed monoliths, don't wait for case studies. Get a pilot contract signed this week.

**But be honest with yourself about what you're selling:** founder-led, invoice-based, hands-on support. You are not ready for self-serve or enterprise. Use the pilot revenue ($15-25K/mo per partner) to fund the SOC 2, pentest, and engineering time needed to close those gaps. In 6 months you can launch for real.

---

*Document classification: Paying-customer readiness assessment. Scope: full repository as of `main @ 418ae99a`. Method: 10 parallel domain agents + 3 commercial/competitive skills + live web probes. Supersedes `audit/paying-customer-readiness.md` (Jul 10 v1) and `audit/paying-customer-readiness-2026-07-06.md`.*
