# Cutctx Launch-Readiness Report — 2026-07-10

**Product:** Cutctx v0.31.0 — Context compression layer for AI agents
**Repo:** `main @ 418ae99a` (current working tree)
**Live proxy:** `GET /livez` → 200, version 0.31.0, all 6 dependency checks healthy
**Tests:** 7,763 passed / 0 failed / 393 skipped (verified 2026-07-04)
**Prior audit score:** 76/100 production readiness (2026-07-02), 83/100 verified (2026-07-04)
**Method:** Consolidated 17 prior audit files + fresh worktree inspection + live probes

---

## Executive Summary: CONDITIONAL GO — Design-Partner Pilot. NO-GO — Public Self-Serve & Enterprise.

### Scenario Verdicts

| Scenario | Verdict | Score | Rationale |
|---|---|---|---|
| **Design-partner pilot** (1–5 named accounts, founder-led, invoice-based) | ✅ **CONDITIONAL GO** | 82/100 | Engineering is solid. 4 of 8 pre-pilot blockers fixed since July 2. Domain + billing are the 2 remaining gates. |
| **Public self-serve** (open signups, Stripe checkout, no founder in loop) | ❌ **NO-GO** | 45/100 | No website (NXDOMAIN). No working payment path. No self-serve billing in dashboard. Stale blog links. No social proof. |
| **Enterprise sales** ($60–150K+/yr, formal procurement, SOC 2) | ❌ **NO-GO** | 38/100 | No SOC 2 report. No pentest report. Backup gap. Single admin key. No SAML. No MFA mandate. 2–3 months from ready. |

### What Changed Since the Last Audit (2026-07-06)

| Item | Prior Status | Current Status | Δ |
|---|---|---|---|
| README "HEADROOM" ASCII art | ❌ Wrong brand | ✅ Fixed | ✅ |
| HMAC audit chain (was plain SHA-256) | ❌ Crypto misnomer | ✅ Uses `hmac.new()` | ✅ |
| Release tags | ❌ Missing | ✅ v0.29.0, v0.30.0, v0.31.0 exist | ✅ |
| Stripe webhook handler | ❌ Stub only | ✅ Working webhook parser | ⚠️ Still needs checkout flow |
| Dashboard e2e tests | ⚠️ 3/3 failing | ✅ 3/3 passing | ✅ |
| Full test suite | ⚠️ 7 failed | ✅ 7,763 passed / 0 failed | ✅ |
| Security posture | ⚠️ 5 critical open | ✅ All verified fixed | ✅ |
| Version alignment | ⚠️ Drift | ✅ All aligned at 0.31.0 | ✅ |
| **Domain (cutctx.dev)** | ❌ NXDOMAIN | ❌ **Still NXDOMAIN** | — |
| **PitchToShip billing** | ❌ HTTP 400 | ❌ **Still dead upstream** | — |
| **Blog CTAs → cutctx.sh** | ❌ Dead links | ❌ Still dead in 5+ files | — |
| **Working tree** | ❌ Dirty | ❌ Still dirty (97 files) | — |

---

## 1. Product Features & QA — ✅ 83/100

### 1.1 Core Compression Pipeline
- **SmartCrusher** (JSON structural compression) — works, tested
- **CodeCompressor** (AST-based, 27 languages via tree-sitter) — works, tested
- **Kompress** (ML text compression via HuggingFace model) — works, DoS-guarded
- **Image compression** (auto JPEG quality routing, format conversion) — works, tested
- **Log/Diff/Search compressors** — all functional
- **CCR (reversible compression)** — originals cached for retrieval; TTL-controlled

### 1.2 Proxy & Deployment
- HTTP proxy at port 8787 — live, healthy, v0.31.0
- WebSocket relay (4 active sessions at probe time)
- Rate limiter, compression decision engine, CORS configuration
- 33+ direct API routes + ~80 enterprise routes
- MCP server (`cutctx_compress`, `cutctx_retrieve`, `cutctx_status`)

### 1.3 Dashboard (11 Pages)
| Page | Status | Notes |
|---|---|---|
| Overview | ✅ | Works |
| Savings | ✅ | Works |
| Orchestrator | ✅ | Works |
| Playground | ✅ | 3,405→2,386 tokens verified |
| Memory | ✅ | Works |
| Governance | ⚠️ | 403 on enterprise-tier features |
| Security | ⚠️ | 403 on enterprise-tier features |
| Firewall | ✅ | Works |
| Capabilities | ✅ | Works |
| Docs | ✅ | Loads but needs content |
| Replay | ✅ | Works |

### 1.4 Bug Tally (QA Audit 2026-07-08)
| Severity | Count | Issues |
|---|---|---|
| Critical | 0 | — |
| High | 0 | — |
| Medium | 2 | Mobile overflow at 390px; Governance/Security throw 403 on free tier |
| Low | 3 | /metrics requires auth (config trap, not bug); /docs title fallback; taskName leak (fixed) |
| Accessibility | 2 | No ARIA labels on nav; sidebar not keyboard-accessible |

**Finding:** No critical or high bugs. The medium-severity issues are cosmetic or expected (403 for gated features is correct behavior, just needs a friendly error page).

---

## 2. Onboarding & Installation — ⚠️ 74/100

### 2.1 What Works
- `pip install cutctx-ai && cutctx proxy` — tested, functional
- `cutctx wrap` — 14 agent wrap commands, 34/34 commands tested
- Docker two-stage distroless build with healthcheck
- Helm chart (2 replicas, image v0.30.0) + K8s manifests (16 files)
- Air-gap deployment via `CUTCTX_OFFLINE_MODE=1`
- 14-day free trial with encrypted trial enforcement

### 2.2 What's Broken or Missing

| Issue | Detail | Severity |
|---|---|---|
| ❌ **No landing page** | `cutctx.dev` NXDOMAIN — first Google click fails | **Critical** |
| ❌ **All emails bounce** | `hello@`, `security@`, `privacy@`, `conduct@`, `licenses@` all at `cutctx.dev` → NXDOMAIN | **Critical** |
| ⚠️ **SDK READMEs point to dead domain** | `sdks/go-cutctx/README.md`, `sdks/java-cutctx/README.md` → `cutctx.sh` (NXDOMAIN) | Medium |
| ⚠️ **Dashboard asset serving** | `/assets/` returns 404 from proxy (works in e2e via mocks) | Medium |
| ⚠️ **Working tree dirty** | 97 modified files — not tagged for release | Low |

---

## 3. Pricing & Billing — ❌ 38/100

### 3.1 Pricing Definition (Good)
| Tier | Monthly | Annual | Target |
|---|---|---|---|
| Builder | $0 | $0 | Individual engineers |
| Team | $1,500 | $18,000 | Single engineering team |
| Business | $3,500 | $42,000 | Platform teams |
| Enterprise | Custom | $60,000–$150,000+ | Security-sensitive orgs |

**Pricing is well-defined** in `artifacts/pricing-sheet.md`. The stale $49 Team price from `docs/pricing.html` and `docs/enterprise.html` appears to have been removed (contact-sales flow) — this blocker is **fixed**.

### 3.2 Billing Implementation (Broken)
| Component | Status | Detail |
|---|---|---|
| **Checkout URL generation** | ❌ Broken | `cutctx_ee/billing/__init__.py` calls `POST https://pitchtoship.com/api/billing/checkout` — PitchToShip is a different company, upstream returned HTTP 400 |
| **Stripe webhook handler** | ✅ Exists | `cutctx_ee/billing/stripe_webhook.py` parses `checkout.session.completed`, `.deleted`, `.updated` — but never called because no checkout sessions are created |
| **Direct Stripe Checkout** | ❌ Missing | No `stripe.checkout.Session.create()` call exists anywhere |
| **Dashboard billing page** | ❌ Missing | No Billing/Pricing/Subscription page in the dashboard |
| **Self-serve upgrade/downgrade** | ❌ Missing | Users must contact sales@payzli.com |
| **`customer.subscription.created` handler** | ❌ Missing | `stripe_webhook.py` only handles `.deleted` and `.updated`; would create orphaned subscriptions on payment-method events |
| **Trial enforcement** | ✅ Works | 14-day encrypted local trial, degrades gracefully |
| **Offline licensing (Ed25519)** | ✅ Works | Signed offline license keys for air-gap deployments |

**Bottom line on billing:** No customer can pay through any automated flow. The only path is manual invoice via email.

---

## 4. Legal & Compliance — ⚠️ 60/100

### 4.1 Legal Documents

| Document | Status | Notes |
|---|---|---|
| Terms of Service (TERMS.md) | ⚠️ Draft | **"Must be reviewed by qualified legal counsel before publication"** — explicit disclaimer |
| Privacy Policy (PRIVACY.md) | ✅ Good | Well-written, local-first narrative, specific about data handling |
| SLA (SLA.md) | ⚠️ Partial | Support response times defined, **no uptime guarantees**, no credit structure |
| DPA Template | ✅ Exists | 18.7K, appears comprehensive |
| MSA Template | ✅ Exists | 22.3K, full terms |
| DMCA Takedown Template | ✅ Exists | |
| Leak Response Runbook | ✅ Exists | |
| CODE_OF_CONDUCT.md | ✅ Exists | |

### 4.2 Brand / Entity Clarity

| Issue | Detail | Severity |
|---|---|---|
| ⚠️ **Dual entity** | `cutctx_ee/__init__.py` → "Cutctx Labs" ; `cutctx_ee/LICENSE` → "Payzli Inc." ; `ENTERPRISE.md` → "sales@payzli.com" | Medium |
| ⚠️ **EE LICENSE unaligned** | `cutctx_ee/LICENSE` and root `LICENSE-COMMERCIAL` have different contact URLs | Low |
| ⚠️ **Conduct@ in COC** | `conduct@cutctx.com` — `cutctx.com` is also NXDOMAIN | Medium |

### 4.3 SOC 2 Readiness

| Requirement | Status | Detail |
|---|---|---|
| SOC 2 report | ❌ Not started | Roadmap targets Q4 2026, no auditor engaged, $45–70K estimated cost |
| Pentest report | ❌ Not available | SECURITY_POLICY.md claims annual pentest under NDA, but no report exists |
| CAIQ / SIG-Lite | ❌ Missing | Custom VENDOR_SECURITY_QUESTIONNAIRE.md exists but not in GRC-ingestible format |
| MFA mandatory | ❌ No | MFA is enrollment-gated, not enforced |
| Backup scope | ❌ Partial | 3 of many stores backed up; RBAC, billing, webhook DLQ, team memory, knowledge graph, vector embeddings NOT backed up |
| SAML SSO | ⚠️ Partial | OIDC works for most IdPs (Okta, Azure AD, Auth0); SAML-only IdPs (legacy ADFS, govt) not supported |
| Multi-key admin API | ❌ No | Single global admin API key |
| PGP key for disclosures | ❌ No | No `/.well-known/security.txt`, no PGP key published |
| Bug bounty | ❌ No | Private responsible disclosure only |

---

## 5. Security — ✅ 82/100

### 5.1 Verified Security Fixes
| Finding | Prior Status | Current Status |
|---|---|---|
| Loopback auth bypass (/dashboard, /api/savings, /api/models) | ❌ Open | ✅ Fixed |
| LIKE wildcard injection in SQLite entity_ref queries | ❌ Open | ✅ Fixed (with `_escape_like()` + ESCAPE clause) |
| Kompress max-input DoS | ❌ Open | ✅ Fixed (CUTCTX_KOMPRESS_MAX_WORDS, default 80K) |
| CORS wildcard + credentials | ✅ Verified fixed | ✅ Still verified |
| Stats/reset audit (not swallowed) | ✅ Verified | ✅ Still verified |
| OTel metrics configured at startup | ✅ Verified | ✅ Still verified |
| HMAC audit chain (now real HMAC) | ❌ Plain SHA-256 | ✅ Uses `hmac.new()` with SHA-256 |

### 5.2 Remaining Security Gaps
| Gap | Severity | Notes |
|---|---|---|
| No rate limit on admin auth attempts | Medium | Brute-force protection for admin API key |
| No CSRF protection on dashboard | Medium | SPA with stateless auth, but no SameSite/CSRF token |
| Metrics endpoint behind admin auth | Low | Prometheus scrapers typically need unauthenticated access or separate config |
| No PGP key for vulnerability reports | Low | High-assurance orgs require PGP-encrypted disclosure |

---

## 6. Production Readiness — ⚠️ 78/100

### 6.1 Operations

| Area | Status | Notes |
|---|---|---|
| **CI/CD** | ✅ Good | 22 GitHub Actions workflows, release-please configured |
| **Docker** | ✅ Good | Two-stage distroless build, healthcheck, multi-arch |
| **Helm/K8s** | ✅ Good | 2 replicas, HPA, PDB, network policies, Prometheus rules |
| **Health checks** | ✅ Good | `/livez`, `/readyz`, `/health` all return 200 |
| **Prometheus metrics** | ✅ Good | `/metrics` endpoint with auth |
| **OTel tracing** | ✅ Configured | Tracing configured at proxy startup |
| **Rate limiting** | ✅ Implemented | Thread-safe rate limiter with configurable limits |
| **Backup** | ⚠️ Partial | Only 3 stores backed up (memory, ledger, audit) — others missing |
| **WebSocket monitoring** | ✅ Good | Active sessions tracked in `/livez` response |
| **Chaos testing** | ✅ Configured | `chaos-testing.yml` workflow exists |

### 6.2 Monitoring Gaps
- No status page for incident communication
- No automated uptime monitoring configured
- No SLA with availability targets (only support response times)

### 6.3 Observability
- Telemetry infrastructure exists (`cutctx/telemetry/` — collector, beacon, differential privacy)
- Privacy-preserving — opt-in, no content collected, aggregate metrics only
- Observability module exists (`cutctx/observability/` — metrics, tracing, memory impact)
- Sentry/error tracking not configured out of the box

---

## 7. Documentation — ⚠️ 75/100

| Area | Status | Notes |
|---|---|---|
| **Wiki** | ✅ Good | 50+ documentation pages covering all features |
| **Docs site** | ✅ Good | mkdocs-based documentation site at `docs/content/docs/` |
| **API reference** | ✅ Good | `api-reference.mdx` covers all endpoints |
| **CLI documentation** | ✅ Good | `wiki/cli.md` at 33K, comprehensive |
| **Getting started** | ✅ Good | `wiki/getting-started.md` and `wiki/quickstart.md` |
| **Architecture docs** | ✅ Good | 40K architecture doc, ADRs in `wiki/adr/` |
| **Security docs** | ✅ Good | `docs/security/SECURITY_POLICY.md` |
| **Limitations docs** | ✅ Good | `wiki/LIMITATIONS.md` — transparent about known limits |
| **Benchmark docs** | ✅ Good | `wiki/benchmarks.md`, `wiki/benchmark-cli.md` |
| **E2E testing docs** | ✅ Good | `E2E_TESTING.md` at 56K |
| **SLA/Support docs** | ⚠️ Partial | No uptime guarantees |
| **Case studies** | ❌ Missing | No real customer stories |
| **Public roadmap** | ❌ Missing | No public roadmap page |
| **Status page** | ❌ Missing | No incident communication channel |

---

## 8. Marketing — ❌ 35/100

| Item | Status | Notes |
|---|---|---|
| **Website (cutctx.dev)** | ❌ NXDOMAIN | Critical blocker — first touchpoint for any buyer |
| **Blog CTAs** | ❌ Dead | 3 blog posts reference `cutctx.sh` (NXDOMAIN) |
| **SDK READMEs** | ❌ Dead | Go and Java SDK READMEs reference `cutctx.sh` |
| **Social proof** | ❌ Missing | No case studies, no testimonials, no member counts |
| **Pitch deck** | ✅ Exists | 14-slide deck in `artifacts/pitchdeck.md` |
| **ROI calculator** | ✅ Exists | `artifacts/roi-calculator.md` |
| **Security one-pager** | ✅ Exists | For enterprise prospects |
| **Pilot success metrics** | ✅ Exists | Documented criteria |
| **GitHub presence** | ✅ Good | CI badges, trendshift badge, active dev |
| **Brand consistency** | ⚠️ 3 entities | Cutctx / Cutctx Labs / Payzli Inc. in play |

---

## 9. Support — ⚠️ 45/100

| Channel | Status | Notes |
|---|---|---|
| **Community (Discord)** | ✅ Exists | Linked in README |
| **Email support (paid tiers)** | ⚠️ Broken | All `@cutctx.dev` emails bounce (NXDOMAIN). `sales@payzli.com` works but is not aligned with product brand |
| **SLA definitions** | ✅ Covers | Response times defined per tier |
| **Knowledge base** | ✅ Exists | Wiki + docs site |
| **Ticket system** | ❌ Missing | No support portal, no ticket tracking |
| **Status page** | ❌ Missing | No incident communication |

---

## 10. Competitive Differentiation — Advantageous

| Differentiator | Cutctx | RTK | LeanCTX | Compresr |
|---|---|---|---|---|
| **Reversible compression (CCR)** | ✅ Unique | ❌ | ❌ | ❌ |
| **Multi-format compressor pipeline** | ✅ JSON+AST+logs+diffs+images+prose | ❌ Shell only | ⚠️ Good | ❌ Single model |
| **5-source savings attribution** | ✅ Unique | ❌ | ❌ | ❌ |
| **Cross-agent memory** | ✅ CacheAligner | ❌ | ❌ | ❌ |
| **Cross-provider cache** | ✅ Anthropic+OpenAI+Google+Bedrock | ❌ | ⚠️ Partial | ❌ Hosted |
| **Local-first** | ✅ Yes | ✅ Yes | ✅ Yes | ❌ Hosted |
| **MCP server** | ✅ 3 tools | ❌ Third-party | ✅ 81 tools | ❌ |
| **Enterprise governance** | ⚠️ Partial | ❌ Not yet | ⚠️ In dev | ❌ |
| **Hosted API** | ❌ No | ❌ No | ❌ No | ✅ Yes |
| **Windows support** | ✅ Yes | ⚠️ Degraded | ✅ Yes | ✅ Yes |

**Defensible moat:** CCR (reversible compression) + multi-format pipeline + savings attribution + cache alignment. No direct competitor has this combination.

---

## 11. Blockers Summary

### Red Blockers (Must Fix Before Any Paying Customer)

| # | Blocker | Why It Blocks | Effort |
|---|---|---|---|
| 1 | **`cutctx.dev` NXDOMAIN** | All email addresses bounce. No landing page. No trust signal. | 1–2 days (register domain + 1-pager) |
| 2 | **No working payment path** | PitchToShip returns HTTP 400. No direct Stripe checkout. Customer cannot pay. | 3–4 days (wire Stripe Checkout directly) |

### Yellow Blockers (Fix Before Pilot Ship)

| # | Blocker | Why It Blocks | Effort |
|---|---|---|---|
| 3 | **Blog CTAs → cutctx.sh (dead)** | 5+ marketing files point to dead domain. Embarrassing if design partner reads them. | 1 hour |
| 4 | **SDK READMEs → cutctx.sh (dead)** | Go and Java SDK READMEs reference NXDOMAIN domain | 30 min |
| 5 | **Brand entity mismatch** | "Cutctx Labs" vs "Payzli Inc." — counsel will flag | 1 hour |
| 6 | **No billing page in dashboard** | Paid users cannot self-serve | 1–2 weeks |
| 7 | **Dirty working tree** | 97 modified files — unprofessional for tag | 1 day |

### Orange Blockers (Enterprise Only)

| # | Blocker | Why It Blocks | Effort |
|---|---|---|---|
| 8 | **No SOC 2 report** | Enterprise procurement gate | 3–6 months + $45–70K |
| 9 | **No pentest report** | Enterprise procurement asks | 2–4 weeks + $15–25K |
| 10 | **Backup gap** | 3 of many stores backed up; billing/RBAC unbacked | 1 week |
| 11 | **No SAML SSO** | Blocks SAML-only IdPs (govt, ADFS) | 2–3 weeks |
| 12 | **Single admin API key** | No per-user/per-service keys | 1–2 weeks |
| 13 | **MFA not mandatory** | Compliance gap | 1 week |

---

## 12. Go / No-Go Recommendation

### ✅ CONDITIONAL GO — Design-Partner Pilot (1–5 named accounts)

**Conditions (must be met before first invoice):**
1. Register `cutctx.dev` (or alternate domain) with a 1-page landing page
2. Fix blog CTAs and SDK READMEs → remove `cutctx.sh` references
3. Clean working tree and tag v0.31.0
4. Document the PitchToShip situation honestly in the pitchdeck (billing is manual/invoice-based until Stripe is wired)

**Acceptable gaps for a design partner (disclose upfront):**
- Billing is manual (invoice/ACH) — no self-serve payments yet
- No SOC 2 report — share SOC 2 roadmap and pre-filled security questionnaire
- No uptime SLA — share current SLA.md and incident response runbook
- Domain is newly registered — expect some email delivery turbulence in first weeks

**Recommended design-partner profile:** Series A–B AI company, 5–20 engineers, founder-led, LLM spend $10–25K/mo, OIDC-capable IdP.

### ❌ NO-GO — Public Self-Serve (open signups)

**Blockers:** No website, no working payment path, no self-serve billing in dashboard, no social proof, stale marketing content, no community momentum visible.

**Estimated to ready:** 1–2 months of focused marketing-surface work after domain is live.

### ❌ NO-GO — Enterprise Sales ($60–150K+/yr)

**Blockers:** No SOC 2 (3–6 months), no pentest report, backup gap, no SAML SSO, single admin key, MFA not mandatory.

**Estimated to ready:** 2–3 months engineering + 6 months SOC 2 observation = **earliest Q1 2027**.

---

## 13. Recommended Path Forward

```
Week 1:     Register cutctx.dev → 1-page landing + fix blog links + clean tree + tag v0.31.0
            → Design-partner pilot becomes unconditional GO

Week 2–3:   Wire Stripe Checkout directly (skip PitchToShip proxy)
            → First design partner can pay via credit card

Week 4–6:   First design partner onboards (14-day pilot)
            → Real case study #1

Week 7–12:  3–5 design partners → $90–300K ARR
            Fund:
            • SOC 2 audit engagement ($45–70K)
            • Third-party pentest ($15–25K)
            • Legal review of all templates ($5–10K)

Week 13–26: SOC 2 Type I report → enterprise GO
            SAML SSO + multi-key admin → enterprise GO
            Website + billing dashboard → public self-serve GO
            Real case studies → public self-serve GO

Net: 6 months to fully launchable across all channels.
Engineering is ~85% done. The remaining 15% is commercial/legal/marketing surface.
```

---

## 14. Sources

This report synthesizes findings from:
- Live probes (July 10, 2026): `dig cutctx.dev` → NXDOMAIN, `GET /livez` → 200
- `audit/paying-customer-readiness-2026-07-06.md` — prior readiness assessment
- `audit/go-no-go-2026-07-02.md` — prior scenario analysis
- `audit/production-readiness-2026-07-02.md` — engineering readiness (76/100)
- `audit/release-audit-verify-2026-07-04.md` — 83/100, verified improvements
- `audit/qa-report.md` (2026-07-08) — 7,763 tests passed, 0 bugs critical/high
- `audit/competitor-report.md` (2026-07-04) — competitive landscape
- `artifacts/pricing-sheet.md` — canonical tier prices
- `cutctx_ee/billing/__init__.py`, `cutctx_ee/billing/stripe_webhook.py` — billing implementation
- Direct file inspection of 50+ files across the repository
- `gtm/soc2-roadmap.md` — SOC 2 compliance timeline
