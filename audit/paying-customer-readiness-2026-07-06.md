# Paying-Customer Readiness Assessment — 2026-07-06

**Product:** Cutctx v0.30.0-12-g2c787ca5 — Context compression layer for AI agents  
**Method:** Consolidated 17 prior audit files + live probes + current worktree inspection  
**Prior verdict (2026-07-02):** CONDITIONAL GO for design-partner pilot; NO-GO for public/enterprise

---

## Bottom Line: CONDITIONAL GO — Design-Partner Pilot. NO-GO — Public Self-Serve & Enterprise.

The product has improved significantly since 2022-07-02. Engineering and QA converged to **~83/100** production readiness. The 30-file sprint from the prior go/no-go is partially complete: HMAC audit chain fixed, version tags published, brand-name typos cleaned, health endpoint split, admin auth hardened, pricing/savings pipeline built.

**But the two blocking facts remain unchanged:** (a) `cutctx.dev` and `cutctx.com` are both NXDOMAIN, so every email address in the codebase bounces, and (b) there is no working payment path.

| Scenario | 2026-07-02 | 2026-07-06 | Change |
|---|---|---|---|
| **Design-partner pilot** (1-5 named accounts, founder-led, invoice-based) | ✅ CONDITIONAL GO | ✅ CONDITIONAL GO | Improved; ~6 of 8 pre-pilot items done or in flight |
| **Public self-serve** (open signups, Stripe checkout, no founder in loop) | ❌ NO-GO | ❌ NO-GO | Still blocked by domain/billing |
| **Enterprise sales** ($60-150K+/yr, formal procurement, SOC 2) | ❌ NO-GO | ❌ NO-GO | Still 2-3 months from ready |

---

## 1. Onboarding & Installation — ⚠️ 74/100

### What works
- `pip install cutctx-ai && cutctx proxy` — tested and functional
- 14 agent wrap commands (`claude`, `codex`, `cursor`, etc.) all documented
- `cutctx wrap` tested across 34/34 CLI commands in QA pass
- Docker two-stage distroless build with healthcheck
- Helm chart and K8s manifests exist
- MCP server (`cutctx_compress`, `cutctx_retrieve`, `cutctx_status`) functional

### What's broken or missing
| Issue | Detail | File |
|---|---|---|
| ❌ **No landing page** | `cutctx.dev` NXDOMAIN — first Google click fails | `ENTERPRISE.md:162`, `SECURITY.md:18` |
| ❌ **All emails bounce** | `hello@cutctx.dev` → NXDOMAIN. Security disclosures, license requests, support tickets all dead-letter | 28+ files |
| ⚠️ **Install one-liner was stale** | `chopratejas/cutctx` → now fixed to `cutctx/cutctx` per verification on 7/4 | `wiki/getting-started.md` |
| ⚠️ **Dashboard asset serving** | `/assets/` returns 404 from proxy; works in dev via mocks | `proxy/server.py` |
| ⚠️ **OG image hardcoded** | Docs social card says "My App" | `docs/app/og/[...slug]/route.tsx:14` |

---

## 2. Pricing — ⚠️ 71/100

### Current state
- **Canonical prices exist** and are well-structured: Builder ($0), Team ($1,500/mo), Business ($3,500/mo), Enterprise (Custom $60-150K/yr)
- **Pricing sheet** (`artifacts/pricing-sheet.md`) is comprehensive with ROI framing, discount rules, quote skeleton
- **Sales artifacts** calibrated: pitchdeck, ROI calculator, security one-pager, pilot success metrics

### Open issues
| Issue | Detail |
|---|---|
| ❌ **30x pricing contradiction** | `docs/pricing.html:110` says Team = $49/mo. Canonical is $1,500/mo. Buyer Googling finds $49. |
| ❌ **No pricing on website** | There is no website |
| ⚠️ **ROI calculator is a static HTML page** | Not interactive, no "try pricing" on docs |
| ⚠️ **4.8% median compression** | Disclosed in pitchdeck small-font caveat but not on any public surface |

---

## 3. Billing — ❌ 35/100

### What's built
- Stripe webhook handlers exist (`cutctx_ee/billing/stripe_webhook.py`: `customer.subscription.deleted`, `.updated`)
- Ed25519 offline license key validation works (`cutctx_ee/billing/pitchtoship_client.py:198-350`)
- License validation routes exist (`cutctx/proxy/routes/license.py`)

### What's broken
| Issue | Severity | Detail |
|---|---|---|
| **PitchToShip billing API is dead** | CRITICAL | `curl https://pitchtoship.com/api/billing/checkout` → HTTP 400 "Missing plan configuration" |
| **No direct Stripe checkout path** | CRITICAL | `cutctx/cli/billing.py:65-89` still routes through dead PitchToShip |
| **License validation no-op** | CRITICAL | `cutctx_ee/watermark.py:195` validates but doesn't enforce |
| **Missing `customer.subscription.created`** | HIGH | `stripe_webhook.py:149-201` — would orphan subscriptions on payment-method changes |
| **No billing/subscription page in dashboard** | HIGH | No `Billing.jsx`, `Pricing.jsx`, `Subscription.jsx` in dashboard |
| **No subscription management UI** | HIGH | Customer can't see/change tier, cancel, see invoices |

**Verdict:** No customer can pay through the documented flow. This is the single biggest blocker.

---

## 4. Licensing — ⚠️ 65/100

### What's good
- Apache 2.0 for OSS engine, `LICENSE-COMMERCIAL` for EE modules
- Ed25519 offline license signing and CRL revocation
- Tier-gated feature enforcement via `cutctx_ee/billing/entitlements.py`

### Issues
| Issue | Detail |
|---|---|
| ❌ **Entity mismatch** | `cutctx_ee/LICENSE:7` says "Payzli Inc."; `cutctx_ee/__init__.py:2` says "Cutctx Labs" |
| ❌ **`cutctx_ee/LICENSE` vs root `LICENSE-COMMERCIAL` divergent** | Different contact URLs at end (PitchToShip vs hello@) |
| ⚠️ **License DB world-readable** | `~/.cutctx/licenses.db` — no `chmod 600` |
| ⚠️ **Rust-side licensing untracked** | `crates/cutctx-core/src/licensing.rs` is untracked |

---

## 5. Analytics & Savings Attribution — ✅ 78/100

### Recently fixed
- Savings tracking pipeline overhauled in latest commit: `cutctx/proxy/savings_tracker.py` with USD attribution, schema version, Prometheus metrics
- `savings_pricing.py` thin wrapper around LiteLLM pricing
- Dashboard savings breakdown now shows by-source USD attribution
- CLI `savings` command prefers live proxy store over stale SQLite

### Open gaps
| Issue | Severity |
|---|---|
| Memoization/output-optimization/batch-routing savings unwired | MEDIUM |
| No shadow-mode validation (estimated vs measured savings) | MEDIUM |
| Cross-process savings tracker tests just added | Verifying |

---

## 6. Support Flows — ⚠️ 50/100

### What's documented
- SLA.md defines tiered support: Builder (community/best-effort), Team (email/business hours/next business day), Business (4hr), Enterprise (1hr/24/7)
- `artifacts/pilot-success-metrics.md` — pilot acceptance criteria
- `artifacts/50-client-outreach-plan.md` — SDR outreach plan

### What's missing
| Issue | Severity |
|---|---|
| ❌ **No support email** | `hello@cutctx.dev` bounces (NXDOMAIN). Pilot inquiries dead-letter. |
| ❌ **No support ticket system** | SLA references email-only; no Zendesk/Intercom/etc. |
| ❌ **No status page** | Downtime invisible to customers |
| ❌ **No dedicated Discord/slack for paid customers** | Community = OSS Discord only |
| ❌ **No "contact sales" on website** | No website |

---

## 7. Security — ⚠️ 72/100

### What's been fixed
- ✅ Loopback auth bypass closed for `/dashboard`, `/api/savings`, `/api/models`
- ✅ LIKE wildcard injection fixed (`_escape_like()` helper)
- ✅ Kompress max-input DoS guard (`CUTCTX_KOMPRESS_MAX_WORDS`)
- ✅ CORS wildcard + credentials conflict resolved
- ✅ Stats/reset logged as warning
- ✅ Health endpoint split into public (`/health`, no config) and admin-gated (`/health/config`)
- ✅ HMAC audit chain fixed (was plain SHA-256, now `hmac.new()`)
- ✅ 5/5 CRITICAL security items from prior audits resolved
- ✅ EgressEnforcer, residency verification, DSR endpoints all functional

### Still open (CRITICAL/HIGH)
| Issue | Severity | Detail |
|---|---|---|
| **License validation no-op** | 🔴 CRITICAL | `cutctx_ee/watermark.py:195` validates but doesn't enforce. Paying customer bypasses license check trivially. |
| **Cross-project memory leak** | 🔴 CRITICAL | Tenant isolation not enforced. Multi-tenant pilot leaks memory between orgs. |
| **`/v1/retrieve/{hash_key}` no admin auth** | 🟠 HIGH | CCR retrieval endpoints protected by entitlement only, not admin auth |
| **`/v1/retrieve/tool_call` no admin auth** | 🟠 HIGH | Same as above |
| **`/v1/retrieve/stats` no admin auth** | 🟠 HIGH | Same as above |
| **`/v1/feedback` no admin auth** | 🟠 HIGH | Same as above |
| **Spend ledger tenant isolation** | 🟠 HIGH | `cutctx_ee/ledger/` not org-scoped |

---

## 8. Observability — ⚠️ 65/100

### What's built
- `/livez`, `/readyz`, `/health` endpoints
- OTel metrics configured at startup
- Prometheus `/metrics` endpoint exists and exposes core metrics
- Prometheus metrics for new features (pricing/savings/telemetry) added in latest commit
- Langfuse tracing integration

### Open issues
| Issue | Severity |
|---|---|
| No Sentry error tracking configured | MEDIUM |
| No Grafana dashboard or OTel dashboard | MEDIUM |
| Native Rust-core metrics not in Prometheus (Python-only) | LOW |
| Dashboard polling can miss events (5s/60s intervals) | LOW |

---

## 9. Documentation — ⚠️ 70/100

### What's good
- `PRODUCT_GUIDE.md` — 912-line comprehensive product guide
- `README.md` — clear, with badges, architecture diagram, install instructions
- `docs/` directory with ~20 sub-sections, full mkdocs config
- `wiki/` getting-started and quickstart
- `llms.txt` for AI agents
- API reference docs in `docs/app/`

### Gaps
| Issue | Detail |
|---|---|
| ⚠️ **docs/ and wiki/ overlap** | Getting-started, proxy setup, MCP config, config reference all duplicated |
| ⚠️ **`docs/policies.md` and `docs/audit-compliance.md` are ~1KB stubs** | Skeleton pages, near-empty |
| ⚠️ **No "pricing" page on docs site** | `docs/pricing.html` exists but has wrong $49/mo price |
| ⚠️ **No FAQ for paying customers** | No billing FAQ, no tier comparison page |
| ⚠️ **No troubleshooting guide for paid tiers** | Enterprise deploy issues undocumented |

---

## 10. Reliability — ⚠️ 68/100

### Evidence
- 8,247 tests collected; critical path tests (CCR, content router, admin auth, healthchecks, DSR, entitlements) all pass
- 1 flaky test across full suite (network-import check — passes on re-run)
- Live proxy health: v0.30.0, `rust_core loaded`, all checks green
- CI/CD with GitHub Actions (22 workflows, release-please configured)

### Risks
| Issue | Severity |
|---|---|
| ❌ **Single-replica only** | Multi-replica HA coordination not built (13+ SQLite stores) |
| ❌ **Backup covers 3 of 13+ stores** | Only `cutctx_memory.db`, `spend_ledger.db`, `audit.db` backed up |
| ⚠️ **Working tree dirty** | 6 modified + 3 untracked files |
| ⚠️ **SLA covers support response only** | No uptime target, no credit structure |

---

## 11. Backup Strategy — ❌ 40/100

### Current coverage
| Store | Backed Up? |
|---|---|
| `cutctx_memory.db` | ✅ `k8s/backup-cronjob.yaml:14` |
| `spend_ledger.db` | ✅ `k8s/backup-cronjob.yaml:15` |
| `audit.db` | ✅ `k8s/backup-cronjob.yaml:16` |
| RBAC store | ❌ Not backed up |
| Billing store | ❌ Not backed up |
| Webhook DLQ | ❌ Not backed up |
| Team memory | ❌ Not backed up |
| Knowledge graph | ❌ Not backed up |
| Vector embeddings | ❌ Not backed up |
| Secrets store | ❌ Not backed up |
| License DB | ❌ Not backed up |
| OTel telemetry data | ❌ Not backed up |
| Dashboard config | ❌ Not backed up |

**No backup verification step exists.** A silent backup failure is invisible until restore time.

---

## 12. Compliance — ❌ 35/100

| Item | Status | Detail |
|---|---|---|
| SOC 2 Type II | ❌ **In preparation, target Q4 2026** | No auditor engaged; 7.5 months minimum |
| Penetration test | ❌ **None published** | `SECURITY_POLICY.md` claims annual pentest under NDA but no report exists |
| CAIQ-v4 / SIG-Lite | ❌ **Not pre-filled** | Custom questionnaire exists but not in GRC-ingestible format |
| MFA mandatory | ❌ **Enrollment-gated, not mandatory** | Enterprise buyer can't enforce |
| SAML SSO | ❌ **OIDC only** | Blocks legacy ADFS/gov buyers |
| Vulnerability management | ❌ **No formal program** | Private disclosure only |
| Bug bounty | ❌ **No program** | `VENDOR_SECURITY_QUESTIONNAIRE.md:145` confirms |
| Security.txt | ❌ **No `/.well-known/security.txt`** | No PGP key published |
| DSR endpoints | ✅ **Exist, honest about narrow scope** | Spend-ledger-only, but documented |
| Data residency controls | ✅ **Residency verification and routing** | Fixed in prior sprint |

---

## 13. Legal Pages — ⚠️ 65/100

### What's present
- `TERMS.md` — 76-line draft template, clearly marked "must be reviewed by qualified legal counsel"
- `PRIVACY.md` — 101-line document, comprehensive on data handling
- `SECURITY.md` — 65 lines, disclosure policy and supported versions
- `LICENSE` — Apache 2.0
- `LICENSE-COMMERCIAL` — Commercial license
- `LICENSING.md` — Open-core licensing explanation
- `DPA_TEMPLATE.md` — Exists but references dead domain

### Issues
| Issue | Detail |
|---|---|
| ❌ **TERMS.md is a template, not reviewed by counsel** | "Must be reviewed by qualified legal counsel" — not ready for customer signature |
| ❌ **Domain references all dead** | Terms/Privacy both reference `cutctx.dev` |
| ❌ **Entity name mismatch** | Payzli Inc. vs Cutctx Labs in legal documents |
| ❌ **No HIPAA BAA** | Even mentioned as "future work" |
| ❌ **No GDPR DPA signed by counsel** | DPA_TEMPLATE exists but is unexecuted |

---

## 14. Marketing Readiness — ❌ 30/100

### What's built
- `artifacts/pitchdeck.md` — 14-slide sales deck
- `artifacts/roi-calculator.md` — 3 hypothetical case studies
- `artifacts/security-one-pager.md` — Security overview for prospects
- `marketing/case-study-template.md` — Template (no real case studies)
- `marketing/roi-calculator/index.html` — Interactive ROI calculator
- `gtm/` — Comprehensive acquisition plan, 3 blog drafts, soc2 roadmap, SDR outreach plan
- `gtm/lead_gen.py` — Lead generation scripts

### What's missing
| Issue | Detail |
|---|---|
| ❌ **No website** | `cutctx.dev` NXDOMAIN. Zero web presence. |
| ❌ **No real case studies** | Template exists, zero filled-in examples |
| ❌ **No community size to show** | No GitHub stars, Discord member count, testimonials on any public surface |
| ❌ **Blog links to wrong domain** | 5 blog files reference `cutctx.sh` — all stale CTAs |
| ❌ **No social proof of any kind** | No "Used by X companies," no logos, no testimonial quotes |
| ❌ **No public changelog for customers** | `CHANGELOG.md` exists but no "what's coming" roadmap |
| ❌ **No "we're in pilot" framing** | README reads as if launched — misleading for self-serve visitors |
| ⚠️ **Pricing contradiction published** | $49/mo Team on `docs/pricing.html` vs $1,500/mo canonical |

---

## 15. Enterprise Readiness — ❌ 40/100

### What's present
- RBAC: implemented in EE with tier-gated feature matrix
- OIDC SSO: works for most IdPs
- Audit logging: HMAC-SHA256 hash chain with canonical framing
- Fleet management APIs: partial
- Air-gap deployment: offline licensing with Ed25519
- Workspace/project model: implemented
- SCIM provisioning APIs: partially implemented
- K8s manifests + Helm chart: exist

### Critical gaps for enterprise
| Issue | Severity | Detail |
|---|---|---|
| ❌ **No SAML SSO** | HIGH | OIDC-only blocks legacy enterprise IdPs |
| ❌ **Single global admin key** | HIGH | No per-user, per-service, or scoped keys; no rotation endpoint; no expiry |
| ❌ **MFA not mandatory** | MEDIUM | Enterprise buyer can't enforce MFA for all admins |
| ❌ **No SOC 2 report** | CRITICAL | Any procurement gate will fail here |
| ❌ **No pentest report** | CRITICAL | Same — nothing to share in security review |
| ❌ **No trust center** | HIGH | No single source of truth for security artifacts |
| ❌ **Team price 30x wrong on docs site** | HIGH | Procurement finds $49, not $1,500 |
| ❌ **Entity name in legal docs mismatched** | MEDIUM | Counsel flags in first 30 mins |
| ❌ **No real uptime SLA** | MEDIUM | SLA is support-response only, no availability target, no credits |
| ❌ **Backup covers 3 of 13+ stores** | HIGH | Billing state lost on disk failure |
| ❌ **No DR runbook** | MEDIUM | Customer can't self-recover |

---

## 16. Competitive Differentiation — ✅ 80/100

### Cutctx's defensible moat
| Advantage | Competitors | Gap |
|---|---|---|
| **Reversible compression (CCR)** | None have this | LeanCTX closest but no lossless retrieval |
| **5-source savings attribution** | None | CFO-grade answer: know exactly where savings come from |
| **Multi-format compressor pipeline** | RTK (shell-only), LeanCTX (text/code) | JSON+AST+logs+diffs+images+prose |
| **Cross-agent memory** | LeanCTX has CCP, but no cross-agent | Share memory across Claude/Codex/Gemini |
| **Cross-provider cache alignment** | None | CacheAligner makes KV cache discounts work |
| **Air-gap + offline licensing** | Few competitors | Enterprise compliance requirement |

### Competitive risks
| Risk | Detail |
|---|---|
| **Helicone/Portkey/Palo Alto adding compression** | Gateway feature absorption is highest threat |
| **LeanCTX reaching parity** | 3.1k stars, wider agent support (30+), 10 read modes |
| **RTK Cloud** | Waitlist at $15/dev/mo — narrow but cheap |
| **No verification/hallucination guard** | vs Entroly WITNESS (AUROC 0.844) — missing feature for enterprise |
| **No read-side intelligence** | vs LeanCTX's 10 read modes — Cutctx only does single-pass compression |

---

## Go/No-Go Recommendation

### ✅ CONDITIONAL GO — Design-Partner Pilot

**Target:** 1-5 named accounts, $18-42K/yr, founder-led, invoice-based (Net 30 wire transfer)

**Pre-conditions (must be resolved before first invoice lands):**

| # | Item | Effort | Owner |
|---|---|---|---|
| P0 | **Register cutctx.dev** + 1-page landing with Privacy/Terms/Security/Contact | 1-2 days | Product |
| P0 | **Wire Stripe Checkout directly** — bypass dead PitchToShip | 3-4 days | Engineering |
| P0 | **Fix license validation no-op** — `cutctx_ee/watermark.py:195` | 1 day | Engineering |
| P0 | **Fix cross-project memory leak** — tenant isolation sprint | 3-5 days | Engineering |
| P1 | Fix 5 HIGH auth endpoints (retrieve/feedback admin-gating) | 2-3 days | Engineering |
| P1 | Fix $49→$1,500 pricing on `docs/pricing.html` and `docs/enterprise.html` | 30 min | Docs |
| P1 | Fix entity name in `cutctx_ee` files (Payzli Inc. operating as Cutctx Labs) | 1 hour | Legal |
| P2 | Backup expansion to 13+ stores with verification | 2-3 days | Engineering |
| P2 | Real uptime SLA (99.9% target, credit structure) | 1-2 days | Product |

**Estimated: 2-3 weeks sprint. First invoice lands week 4.**

### ❌ NO-GO — Public Self-Serve

**Blockers:**
- No website (cutctx.dev NXDOMAIN)
- No working payment path
- No billing dashboard UI
- No social proof / case studies / community size
- 30x pricing contradiction published

**Estimated path:** 1-2 months of marketing surface work. Don't pursue until 5+ design partners signed.

### ❌ NO-GO — Enterprise Sales

**Blockers:**
- No SOC 2 report (6+ months minimum)
- No pentest report
- SAML SSO missing
- Multi-key admin API missing
- MFA not mandatory
- No CAIQ/SIG-Lite
- Backup gap (3 of 13+ stores)

**Estimated path:** 2-3 months engineering + 6 months SOC 2 observation period. Use design-partner revenue to fund.

---

## Recommended Path Forward

```
Week 1-3:    P0/P1 sprint → design-partner pilot is GO
Week 4-6:    First design partner onboards (14-day pilot)
Week 7-12:   3-5 design partners → $90-300K ARR
             Fund SOC 2 engagement ($45-70K)
             Fund pentest ($15-25K)
Week 13-26:  SOC 2 Type I report → enterprise GO
             SAML SSO + multi-key admin → enterprise GO
             Website + billing dashboard → public self-serve GO
             Real case studies from design partners → public self-serve GO

Net: 6 months to a fully-launchable product across all channels.
```

---

## Sources

This report synthesizes findings from:
- `audit/paying-customer-readiness-2026-07-06.md` (this file) — live probes + current worktree
- `audit/go-no-go-2026-07-02.md` — prior scenario analysis
- `audit/production-readiness-2026-07-02.md` — engineering readiness (76/100)
- `audit/qa-report.md` (2026-07-05) — 1344 passed, 19 remaining critical/high
- `audit/release-audit-verify-2026-07-04.md` — 83/100, verified improvements over prior audits
- `audit/competitor-report.md` (2026-07-04) — competitive landscape
- `audit/commercial-readiness-remediation-runbook.md` (2026-07-06) — actionable remediation tasks
- `audit/remaining-work-implementation-plan.md` (2026-07-06) — current workstream implementation spec
- `artifacts/pricing-sheet.md` — canonical tier prices
- `gtm/soc2-roadmap.md` — SOC 2 timeline
- Live probes: `dig cutctx.dev` → NXDOMAIN, `dig cutctx.com` → NXDOMAIN
