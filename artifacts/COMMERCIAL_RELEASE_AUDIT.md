# Commercial Release Readiness Audit — CutCtx

**Date:** 2026-06-18  
**Product:** CutCtx (formerly Headroom) v0.26.0  
**Auditor:** Multi-role review (PM, SWE, QA, UX, Platform, CS)  
**Verdict:** ⚠️ NOT READY — 4 Critical, 8 High, 12 Medium, 9 Low issues

> Historical note: this audit predates later launch-page fixes. Pricing alignment, enterprise feature badges, and published legal docs have since been updated in the repo. Treat the issue list below as a snapshot of the pre-fix state, not a live blocker list.

---

## Product Understanding

| Attribute | Value |
|-----------|-------|
| **Purpose** | Context compression layer for AI agents — compresses LLM API payloads 60-95% |
| **Target audience** | Engineering teams using AI coding agents (Claude Code, Codex, Cursor, etc.) |
| **Core workflows** | `cutctx proxy` (zero-code), `cutctx wrap <agent>` (one-line), library `compress()` |
| **Value prop** | "Same answers, fraction of the tokens" — local-first, reversible, multi-provider |
| **Pricing** | Builder (Free), Team ($49/mo on pricing.html, $1,500/mo on enterprise.html), Enterprise (Custom) |
| **Differentiators** | Rust core (only one), CCR reversibility (unique), 12 algorithms, 6 providers |

---

## Critical Issues (4) — Launch Blockers

### C1: Pricing Contradiction Between Pages
- **Where:** `docs/pricing.html` line 110 vs `docs/enterprise.html` line 469
- **Impact:** Team tier shows **$49/mo** on pricing.html and **$1,500/mo** on enterprise.html
- **Severity:** Critical — destroys trust, may violate consumer protection laws
- **Fix:** Decide on actual price. If $49/mo, fix enterprise.html. If $1,500/mo, fix pricing.html. These MUST match.
- **Verification:** `grep -n '\$[0-9]' docs/pricing.html docs/enterprise.html`

### C2: No Self-Service Checkout Flow
- **Where:** `docs/pricing.html` line 124, `docs/enterprise.html` line 480
- **Impact:** Both pages link to `mailto:hello@headroomlabs.ai` — no Stripe checkout, no trial signup form, no in-app purchase
- **Severity:** Critical — kills conversion for self-serve users
- **Fix:** Either wire up a Stripe checkout link or a trial signup form. At minimum, the Team "Start Free Trial" button should go to a signup page, not an email link.
- **Verification:** Click the "Start Free Trial" button on pricing.html

### C3: TERMS.md and PRIVACY.md Don't Exist
- **Where:** README.md lines 32-33 link to `TERMS.md` and `PRIVACY.md`
- **Impact:** 404 on click. Legal pages required for any commercial offering. Drafts exist at `artifacts/legal/TERMS_OF_SERVICE_DRAFT.md` and `artifacts/legal/PRIVACY_POLICY_DRAFT.md` but are not published.
- **Severity:** Critical — legal liability, broken trust signal
- **Fix:** Move draft files to repo root as `TERMS.md` and `PRIVACY.md`, or remove links from README
- **Verification:** `ls TERMS.md PRIVACY.md` should exist

### C4: Enterprise Page Shows SSO/RBAC/Audit as "Coming Soon"
- **Where:** `docs/enterprise.html` lines 429-443
- **Impact:** The enterprise page shows SSO, RBAC, and Audit Logs as "Coming Soon" badges — but they are **already implemented** (27 SSO tests, 18 RBAC tests, 25 audit tests pass). This tells buyers the features don't exist when they do.
- **Severity:** Critical — actively discourages enterprise buyers
- **Fix:** Remove "Coming Soon" badges, change to "Available" or simply remove the section since features are listed in the comparison table above
- **Verification:** Check that `tests/test_sso.py`, `tests/test_rbac.py`, `tests/test_audit.py` all pass

---

## High Issues (8)

### H1: Stale Branding — "Headroom" / "headroomlabs.ai" in Enterprise Page
- **Where:** `docs/enterprise.html` — 9 occurrences of "Headroom", 8 of `hello@headroomlabs.ai`
- **Impact:** Product was rebranded to CutCtx. Enterprise page still says "Headroom" in title, nav, hero, steps, comparison, security, pricing, footer.
- **Fix:** Replace all "Headroom" → "CutCtx" and `hello@headroomlabs.ai` → `hello@cutctx.dev` in enterprise.html

### H2: Stale Branding — README.md References Old Repo/Badges
- **Where:** `README.md` — 37 references to `chopratejas/headroom` (old GitHub org/repo)
- **Impact:** All CI badges, Docker images, clone URLs, star history, trendshift badge point to `chopratejas/headroom` instead of `AryanSingh/cutcxt`
- **Fix:** Replace all `chopratejas/headroom` → `AryanSingh/cutcxt` in README.md

### H3: License CLI Uses "headroom" Command Names
- **Where:** `headroom/cli/license.py` lines 27-29, 55-56, 124, 128
- **Impact:** Help text says `headroom license activate` instead of `cutctx license activate`. Also references `headroomlabs.ai` URLs.
- **Fix:** Replace `headroom license` → `cutctx license`, `headroomlabs.ai` → `cutctx.dev`

### H4: K8s Deployment Uses Wrong Health Endpoint
- **Where:** `k8s/deployment.yaml` line 76
- **Impact:** Liveness probe hits `/healthz` but Python proxy exposes `/livez` (not `/healthz`). Will cause pod restarts.
- **Fix:** Change liveness probe path from `/healthz` to `/livez`

### H5: K8s Deployment Port Mismatch
- **Where:** `k8s/deployment.yaml` lines 46-48 vs Dockerfile line 98
- **Impact:** K8s container exposes port 8080 but Dockerfile ENTRYPOINT defaults to port 8787. Config says `--listen-addr 0.0.0.0:8080` which matches K8s, but is inconsistent with Dockerfile.
- **Fix:** Ensure K8s deployment args and Dockerfile CMD are consistent. Document the port difference.

### H6: Helm Image Reference Non-Existent Registry
- **Where:** `helm/cutctx/values.yaml` line 8
- **Impact:** Image is `ghcr.io/chopratejas/cutctx` — this GHCR path may not exist. Also uses old org name.
- **Fix:** Update to actual image path or use a placeholder with clear comment

### H7: Docs Link to Non-Existent Pages
- **Where:** `docs/pricing.html` lines 188-193
- **Impact:** Footer links to `/security` (doesn't exist), nav links to `/docs` (may be external). `docs/enterprise.html` line 191 links to `https://cutctx.dev/docs` which is external.
- **Fix:** Create `/security` page or remove link. Ensure all internal nav links resolve.

### H8: billing/__init__.py is Empty
- **Where:** `headroom/billing/__init__.py`
- **Impact:** The billing package exists but has no actual implementations. `stripe_webhook.py` and `license_db.py` are in `headroom_ee/billing/` which requires the EE distribution.
- **Fix:** Either populate `headroom/billing/` with stubs or clearly document that billing requires `headroom_ee`

---

## Medium Issues (12)

### M1: Version Number Inconsistency
- **Where:** `pyproject.toml` line 7 says `0.25.0`, Helm Chart.yaml says `0.26.0`, CHANGELOG says `v0.26.0`
- **Impact:** PyPI package shows 0.25.0 but CHANGELOG says 0.26.0. Confusing for users.
- **Fix:** Bump pyproject.toml to `0.26.0`

### M2: Setup CLI References Old Package Name
- **Where:** `headroom/cli/setup.py` lines 17, 47-48, 66, 119
- **Impact:** `_check_cutctx_installed()` checks for `headroom-ai` not `cutctx-ai`. Setup flow says "Install with: pip install headroom-ai" instead of "pip install cutctx-ai".
- **Fix:** Update all `headroom-ai` references to `cutctx-ai`

### M3: Enterprise Page Navigation Missing Links
- **Where:** `docs/enterprise.html` line 31
- **Impact:** Nav only has Features, Pricing, Security, Docs, GitHub. Missing: Home, Terms, Privacy.
- **Fix:** Add Home and Terms/Privacy links

### M4: README Still Says "Headroom" in Multiple Places
- **Where:** README.md lines 43-45, 89, 129, 193, 216, 223-236, 243-245, 260-273, 288, 321
- **Impact:** While the README explains the naming, the inconsistency is confusing. Package install says `pip install headroom-ai`, Docker says `ghcr.io/chopratejas/headroom`.
- **Fix:** Add clear "CutCtx (formerly Headroom)" branding header and update Docker/PiPy references

### M5: No Deployment Port Documentation
- **Where:** K8s uses 8080, Docker uses 8787, Helm uses 8080
- **Impact:** Users deploying across environments may hit port conflicts
- **Fix:** Add a port reference table to deployment docs

### M6: Admin Dashboard Has No Authentication Instructions
- **Where:** `docs/admin-dashboard.html` — no mention of how to set admin key
- **Impact:** Users won't know they need `HEADROOM_ADMIN_API_KEY` env var to access the dashboard
- **Fix:** Add a setup note or link to docs on the dashboard page

### M7: Missing `cutctx-ai` PyPI Package
- **Where:** README links to `pypi.org/project/headroom-ai/`
- **Impact:** The rebranded package `cutctx-ai` may not exist on PyPI yet
- **Fix:** Either publish `cutctx-ai` to PyPI or keep `headroom-ai` and document both

### M8: Docker Image Name Inconsistency
- **Where:** `Dockerfile` entrypoint says `cutctx proxy` but image is built as `cutctx-proxy:latest` (K8s) or unspecified (Docker)
- **Impact:** No clear image naming convention
- **Fix:** Document the canonical image name: `ghcr.io/aryansingh/cutctx:latest`

### M9: Enterprise Page Pricing Discrepancy with Pricing Page
- **Where:** `docs/enterprise.html` line 469 ($1,500/mo) vs `docs/pricing.html` line 110 ($49/mo)
- **Impact:** Different prices for the same tier depending on which page you visit
- **Fix:** Unify pricing across all pages

### M10: Enterprise Page Footer Says "Headroom Labs"
- **Where:** `docs/enterprise.html` line 513
- **Impact:** © 2026 Headroom Labs. Apache 2.0. — should be CutCtx Labs or CutCtx Contributors
- **Fix:** Update copyright

### M11: README CI Badge Points to Old Repo
- **Where:** `README.md` line 14
- **Impact:** `github.com/chopratejas/headroom/actions` — badge may be broken if repo moved
- **Fix:** Update to `github.com/AryanSingh/cutcxt/actions`

### M12: No `cutctx` Binary Published
- **Where:** README says `cutctx` but the Rust binary is named `cutctx` only after Cargo.toml rename. PyPI package installs as `headroom` CLI.
- **Impact:** Users may be confused about which CLI command works
- **Fix:** Ensure both `cutctx` and `headroom` are documented as available CLI names

---

## Low Issues (9)

### L1: README Documentation Links Use External Domain
- **Where:** `README.md` lines 297-302
- **Impact:** Links to `headroom-docs.vercel.app` — should be `cutctx.dev/docs`
- **Fix:** Update all doc links

### L2: Changelog Says "Unreleased (v0.26.0)" 
- **Where:** `CHANGELOG.md` line 9
- **Impact:** Version is marked as unreleased but should be released
- **Fix:** Update to released version

### L3: Enterprise Page Missing Terms/Privacy Links
- **Where:** `docs/enterprise.html` footer
- **Impact:** No legal links in footer
- **Fix:** Add Terms and Privacy links

### L4: Pricing Page Missing Comparison to Competitors
- **Where:** `docs/pricing.html`
- **Impact:** No competitor comparison table (unlike enterprise.html)
- **Fix:** Add a comparison section

### L5: Admin Dashboard CCR Browser Section Has No Backend
- **Where:** `docs/admin-dashboard.html` line 114
- **Impact:** CCR Browser section exists in UI but there's no corresponding API endpoint for browsing CCR content
- **Fix:** Either implement the API or remove the section

### L6: README Says "6 algorithms" but Product Has 12+
- **Where:** README.md line 11
- **Impact:** "6 algorithms · local-first · reversible" — actual count is 12+ (SmartCrusher, CodeCompressor, DiffCompressor, LogCompressor, SearchCompressor, ImageCompressor, AudioCompressor, Kompress-base, CacheAligner, etc.)
- **Fix:** Update count

### L7: Docker Compose Service Name Still "headroom-proxy"
- **Where:** `docker-compose.yml`
- **Impact:** Service name may still reference old branding
- **Fix:** Verify and update

### L8: Enterprise Page GitHub Link Points to Wrong Repo
- **Where:** `docs/enterprise.html` line 163
- **Impact:** Links to `github.com/cutctx/cutctx` — should be `github.com/AryanSingh/cutcxt`
- **Fix:** Update URL

### L9: Missing CHANGELOG Entry for v0.26.0 Release
- **Where:** CHANGELOG.md
- **Impact:** No formal release date or tag
- **Fix:** Add release date when shipping

---

## Launch Recommendation

### ❌ NOT READY FOR COMMERCIAL LAUNCH

**Evidence:**

1. **4 Critical issues** must be fixed before launch:
   - Pricing contradiction ($49 vs $1,500) — legal risk
   - No self-serve checkout — conversion killer
   - Missing legal pages (Terms, Privacy) — compliance risk
   - Enterprise page showing implemented features as "Coming Soon" — sales blocker

2. **8 High issues** will hurt adoption:
   - Stale branding across all customer-facing pages (enterprise, README, CLI)
   - K8s deployment uses wrong health endpoint (will cause pod crashes)
   - Missing security page

3. **12 Medium issues** reduce professional appearance:
   - Version number inconsistency
   - Package name confusion
   - Missing deployment documentation

**Recommended Actions (in priority order):**
1. Fix pricing contradiction immediately
2. Remove "Coming Soon" badges from enterprise page
3. Publish TERMS.md and PRIVACY.md
4. Complete branding pass (Headroom → CutCtx) across all pages
5. Fix K8s health endpoint
6. Create self-serve checkout or trial signup flow
7. Bump version to 0.26.0 in pyproject.toml
8. Update all GitHub URLs to AryanSingh/cutcxt

**Estimated time to fix all Critical + High:** 2-4 hours of focused work.
