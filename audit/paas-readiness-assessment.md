# Cutctx — Paying-Customer Readiness Assessment (Re-Audit)

**Date:** 2026-07-04 (updated re-audit)  
**Product version:** v0.30.0 (unreleased — HEAD is 121 commits past v0.27.0)  
**Working tree:** `feature/dx-improvements` branch, 447 dirty files  
**Prior scores:** Commercial readiness 6.3/10 (Jul 3), Production readiness 72/100 (Jul 3), Product maturity 7.2/10 (Jul 3)  
**This assessment:** **Conditional Go** (OSS/local only) — **No-Go** for full commercial launch

---

## Executive Summary

Since the prior audit, the engineering team has made **real, significant progress on code-level security and deployment infrastructure**: 5/5 critical security items fixed, Stripe webhooks hardened with idempotency and replay protection, K8s deployment blockers resolved (port, UID, persistent storage, Helm EE secrets), OTel wired into the Python proxy, and extensive brand/domain cleanup.

**However, the five critical business blockers from the first audit remain unaddressed**, and two new regressions have appeared. The delta is net-positive on engineering but net-zero on business readiness.

### Fixes vs Remaining Gaps

| Area | Fixed since prior audit | Still broken |
|------|------------------------|--------------|
| **Billing** | Stripe webhook: subscription.deleted deactivates, invoice.paid extends, idempotency, replay protection, seats from Price IDs. EE license routes auth-gated. | **No self-serve checkout.** PitchToShip checkout is "dead." `docs/pricing.html` Team CTA still points to it. `customer.subscription.created` handler still missing. |
| **Domain/Brand** | `cutctx.dev`→`cutctx.com` migration, `chopratejas`→`cutctx` org rename, brand casing consistent | **`cutctx.com` is still NXDOMAIN.** `github.com/cutctx` org doesn't exist. Email infrastructure still stubbed to local spool. |
| **Deployment** | K8s port/UID/version fixed, PVC added, Helm EE secrets templated, image tag 0.30.0 | **Backup CronJob regressed** (wrong PVC name). Fluent Bit still stdout-only. PrometheusRules still dead config. No alerting. |
| **Security** | 5/5 criticals fixed (HMAC chain, CORS, stats/reset, webhook auth, EgressEnforcer). Keyring validation added. | No SOC 2, no bug bounty, no security.txt, no PGP key. New version-header leak. 10 new medium-severity findings. |
| **Legal** | — | TERMS.md still a draft. FAQ.md, MIGRATION.md missing. No CLA infrastructure. |
| **Onboarding/UX** | Dashboard Orchestrator stalled-state detection | No welcome wizard. Invisible 14-day trial. Auth-gate still has no help text. `pip install cutctx` typo in docs. |
| **Competitive** | — | **New competitor Condense.chat launched yesterday.** Edgee emerged as real threat. lean-ctx shipping at 1 release/2-3 days. |

---

## Delta Since Prior Audit

### ✅ FIXED (15+ items)

**Security-critical (5/5 from prior launch-readiness report now closed):**
1. **HMAC audit chain** — was plain SHA-256, now HMAC-SHA256 over canonical length-prefixed fields
2. **CORS wildcard + credentials** — `credentials=False` when `origins=["*"]`
3. **`/stats/reset` audit logging** — was silently swallowed, now logged; loopback-restricted
4. **Stripe tier from Price IDs** — was client-controllable `metadata.seats` (`seats=9999` attack), now reads from `TIER_SEAT_LIMITS`
5. **EgressEnforcer** — wired at 15+ call sites

**Billing & licensing:**
- Stripe webhook: `subscription.deleted` now calls `db.deactivate_license()` (was log-only)
- Stripe webhook: `invoice.paid` now calls `db.extend_license()` (was log-only)
- Webhook idempotency via `processed_events` table with `check_processed_event` + `mark_event_processed`
- Stripe signature verification: constant-time `hmac.compare_digest` + 300s replay window + timestamp validation
- License email: no longer a silent `logger.info`, now spools to `~/.cutctx/mail_spool/`
- `/v1/license/*` and `/webhooks/stripe` now admin-auth + `license.write` RBAC gated (was completely unauthenticated — Critical security finding)
- `/webhooks/stripe`: 503 refusal when `STRIPE_WEBHOOK_SECRET` empty in `CUTCTX_BILLING_STRICT_MODE=1` (was silent skip — allowed forged events)
- Locking webhook: **already existed** for status transitions

**Deployment infrastructure:**
- **Port mismatch fixed:** K8s deployment now `containerPort: 8787` (was 8080 — proxy never started)
- **UID mismatch fixed:** `runAsUser/runAsGroup/fsGroup` now `1000` (was 65534 — EACCES on `~/.cutctx`)
- **Image tag fixed:** `v0.30.0` (was `v0.29.0`)
- **Persistent storage added:** New `k8s/pvc.yaml` (10Gi, ReadWriteOnce) + mount in deployment
- **Helm EE secrets:** licenseKey, auditSecretKey, upstreamApiKey now templated (was crash-on-first-request)
- **Helm PVC:** New `templates/pvc.yaml` + `persistence:` values block
- **Helm image tag bumped** to 0.30.0

**Observability:**
- **Python OTel wired:** `cutctx/observability/metrics.py` (584 lines) with Counter/Histogram/UpDownCounter wrapper; `cutctx/observability/tracing.py` (228 lines) with Langfuse tracing integration — both wired into FastAPI lifespan (startup + shutdown)

**Code quality:**
- `cutctx/proxy/server.py`: 54 `pass`→`logger.exception` changes (previously silent)
- Auth keyring validation: `cutctx/proxy/auth_keyring.py` validates OS credential manager for API keys (commit 8106b218)
- New regression tests: `test_ee_audit_store_hmac.py` (21KB), `test_auth_keyring.py` (+26 lines)
- Version-contract test: `test_commercial_surface_truthfulness.py` — 8/8 passing

**Brand/docs cleanup:**
- `cutctx.dev` URLs → `cutctx.com` (8 occurrences in README)
- `chopratejas/kompress-v2-base` → `cutctx/kompress-v2-base` (3 occurrences)
- `hello@cutctx.dev` → `hello@cutctx.com` (ENTERPRISE.md)
- `CutCtx` → `Cutctx` brand casing consistent across HTML surfaces
- Blog CTAs no longer point to dead `cutctx.sh`
- Security questionnaire more honest about evidence status
- SECURITY.md reflects current supported release line
- Docker-native install docs point to canonical `cutctx/cutctx`

### ❌ STILL BROKEN (no change)

**Critical blockers (P0):**
1. **`cutctx.com` is NXDOMAIN** — no product website, no email delivery infrastructure
2. **`github.com/cutctx` org 404** — repos under `headroomlabs-ai` or personal namespace
3. **No self-serve checkout** — PitchToShip checkout described as "dead" in CHANGELOG
4. **TERMS.md still a draft** ("must be reviewed by qualified legal counsel")
5. **No support portal** (no Zendesk/Intercom/Freshdesk)
6. **No log aggregation** — Fluent Bit outputs to stdout only
7. **No alerting** — no Slack/PagerDuty/OpsGenie integration
8. **No SOC 2 / HIPAA / ISO 27001 / bug bounty / security.txt / PGP key**
9. **14-day trial is invisible** until features silently degrade

**Medium blockers (P1-P2):**
10. **No onboarding wizard** — dashboard assumes proxy is running, auth-gate has no help text
11. **No welcome screen, no first-run detection, no guided setup**
12. **FAQ.md, MIGRATION.md, UPGRADE.md, SUPPORT.md** all missing
13. **wiki/api.md still hand-written** (no mkdocstrings)
14. **wiki/getting-started.md:11/14/17** still says `pip install cutctx` (not `cutctx-ai`)
15. **No CLA infrastructure** — all code must be in-house to enforce commercial license
16. **GTM pricing stale** — acquisition plan lists Team at $499/mo (authoritative: $1,500/mo)
17. **Missing legal drafts:** `PRIVACY_POLICY_DRAFT.md`, `TERMS_OF_SERVICE_DRAFT.md` referenced but absent
18. **Mail delivery stubbed** to `~/.cutctx/mail_spool/` — no SMTP/SendGrid/Mailgun
19. **No SAML SSO** (OIDC only), **no WebAuthn** (TOTP only)
20. **`codecov.yml` still auto-target** (no fixed threshold)
21. **Spend ledger has no org filter** (cross-tenant data leakage)
22. **Backup CronJob has no AWS creds** (serviceAccountName, secretRef all missing)

### 🔴 NEW REGRESSIONS

1. **Backup CronJob PVC name mismatch** — new PVC is `cutctx-pvc`, CronJob mounts `cutctx-data` → job will fail to start
2. **`docs/pricing.html` Team CTA still points to dead pitchtoship.com** — CHANGELOG claimed it was fixed but only `artifacts/license-portal.html` and `artifacts/openapi-management.yaml` were scrubbed. The main public pricing page was missed.
3. **Dashboard assets return 404** — proxy doesn't serve `/assets/` paths; 3 Playwright E2E tests fail (release-blocking)
4. **No release tag for HEAD** — 121 commits past v0.27.0, despite CHANGELOG claiming v0.30.0
5. **Working tree very dirty** — 447 changes (374 modified, 9 untracked, 4 deleted)
6. **168 fewer tests collected** than prior audit (working-tree churn)
7. **Version header leaked** in every response (new medium-severity security finding)
8. **`.env.local` exists in repo** (131 lines — potential secret leak risk)
9. **NetworkPolicy allows egress to 0.0.0.0/0** (medium severity)
10. **License DB world-readable** (medium severity)
11. **422 fewer Python tests** in CI (was 7,960; now ~7,538)

### 🆕 COMPETITIVE LANDSCAPE CHANGES

| Competitor | Prior assessment | Current assessment | Threat change |
|-----------|-----------------|-------------------|---------------|
| **Condense.chat** | Not tracked | **Launched Jul 3, 2026** — direct peer with named models (Adeline 1 + Helene 1), 64% token reduction, 100M free tokens, faithfulness leaderboard | 🔴 **NEW — HIGH** |
| **Edgee** | Footnote | Real shipping product: free compression, edge-deployed, MCP-aware tool-surface reduction, v0.2.10, 23 releases | 🟡 Elevated to MEDIUM-HIGH |
| **lean-ctx** | Medium | 1 release/2-3 days pace, v3.8.18, Hermione integration, Cognition v2, reversibility framing, 3K stars | 🟡 Elevated to HIGH |
| **The Token Company** | $70M seed threat | Sub-$1M raised, solo 18-yo founder, YC C-tier rating | 🟢 Downgraded — much weaker |
| **Portkey** | Medium competitor | **Acquired by PANW $140M** (90-day S2A→exit), repositioned as security product | 🟢 Vacuum — audience up for grabs |
| **Helicone** | Medium | **Acquired by Mintlify, maintenance mode** — no new features | 🟢 Vacuum — audience up for grabs |
| **Compresr** | Medium | Phantom Tools (CCR-like), PhD moat, but **no cache-aware compression** — CacheAligner still Headroom's wedge | ➖ Unchanged |
| **llmtrim, cctx, ContextOS, Kompact** | Small | No major updates | ➖ Unchanged |

**Net threat change: INCREASED.** Two new credible peers (Condense, Edgee) plus lean-ctx's acceleration offset the positive news of Portkey/Helicone exiting and Token Co. proving weak.

---

## Updated Go/No-Go Analysis

### Can sell today:
| Customer type | Ready? | Why |
|--------------|--------|-----|
| **Individual OSS users** | ✅ **Yes** | Free tier works well; 15+ engineering fixes since last audit |
| **Design partners (Team tier, founder-led)** | ✅ **Yes** (easier than before) | License route auth fixed, Stripe webhook hardened, deployment blockers resolved |
| **Enterprise POCs (engineering-led)** | ⚠️ **Conditional** | SSO/RBAC/audit works; HA/DR gaps remain; no SOC 2 |

### Cannot sell today:
| Customer type | Ready? | Why |
|--------------|--------|-----|
| **Self-serve Team/Business (credit card)** | 🔴 **No** | No self-serve checkout; `docs/pricing.html` still links to dead PitchToShip; regressions in dashboard/backup |
| **Enterprise with procurement (SOC 2 required)** | 🔴 **No** | No SOC 2; TERMS.md a draft; no support portal; cutctx.com NXDOMAIN |
| **HIPAA-regulated customers** | 🔴 **No** | No HIPAA readiness |
| **Prospective customers searching "Cutctx"** | 🔴 **No** | cutctx.com NXDOMAIN; github.com/cutctx 404 |

### What changed vs prior audit
| Customer type | Prior | Now | Delta |
|--------------|-------|-----|-------|
| Design partners | Conditional Go | ✅ **Easier Go** | License auth, Stripe hardening, K8s fixes removed friction |
| Enterprise POCs | Conditional | ⚠️ **Same** | 5 deployment blockers fixed but still no SOC 2 |
| Self-serve | No | 🔴 **Worse** | PitchToShip link NOT fixed despite CHANGELOG claim; pricing.html regression |
| Competitive positioning | Strong | ⚠️ **More pressure** | Condense launched; Edgee emerged; lean-ctx accelerated |

---

## Recommended Action Plan

### Week 1-2: Fix regressions (blocking release)
1. Fix `docs/pricing.html` Team CTA — remove dead PitchToShip link
2. Fix `k8s/backup-cronjob.yaml` PVC name (`cutctx-data`→`cutctx-pvc`)
3. Fix dashboard asset 404 (proxy routing for `/assets/*`)
4. Tag v0.30.0 properly
5. Commit or rebase `feature/dx-improvements` (447 dirty files is not sustainable)

### Week 2-4: Business-critical (blocks any sale)
6. **Stand up cutctx.com** — DNS + landing page + marketing site + docs hosting
7. **Fix self-serve checkout** — fix Stripe webhook `subscription.created` handler, or switch to Paddle/Lemon Squeezy
8. **Finalize TERMS.md** with legal counsel
9. **Set up support portal** — Intercom or Zendesk minimum viable

### Week 4-8: Enterprise-blocking (blocks deals >$18K)
10. **Wire log aggregation** — Fluent Bit → Loki (or CloudWatch)
11. **Configure Alertmanager** — at minimum Slack alert for 5xx rate > 5%
12. **Fix PrometheusRules** to use real metric names
13. **Rebuild + sign EE `.so` files** for distribution

### Week 8-12: Self-serve enablers
14. Visible trial state with upgrade CTA in dashboard
15. Dashboard onboarding wizard (connect first agent, admin key discoverability)
16. Publish the 3 blog drafts

**Full commercial launch target:** September 2026 (unchanged from prior audit)

### Competitive urgency
The Condense.chat launch (yesterday) makes September a tighter window than it was 24 hours ago. The "Compresr → CacheAligner wedge" is still open (Condense hasn't answered the cache-invalidation critique either), but Headroom should publish its own faithfulness/replay benchmarks publicly within 2 weeks to own the comparison narrative.
