# Frontend / UX / Accessibility — Reconciliation

**Generated:** 2026-07-29
**Source audits:** 5 documents spanning 2026-07-10 → 2026-07-27
**Verification:** Live codebase spot-checks against `dashboard/src/` and `website/`

---

## Audit Inventory

| # | Document | Date | Scope |
|---|----------|------|-------|
| 1 | `frontend-analysis.md` | 2026-07-10 | Dashboard React SPA architecture, CSS, components |
| 2 | `ux-analysis.md` | 2026-07-10 | CLI first-run experience, command discoverability, error messages |
| 3 | `accessibility-analysis.md` | 2026-07-10 | WCAG 2.1 AA compliance on dashboard |
| 4 | `ui-ux-audit-2026-07-18.md` | 2026-07-18 | Live interactive audit — all routes, controls, failure modes |
| 5 | `ui-ux-review-aie-commercial.md` | 2026-07-27 | AIE commercial branch — website, docs, buyer report UX |

---

## Cross-Audit Summary

### Overall Ratings

| Surface | Rating | Source |
|---------|--------|--------|
| Dashboard SPA (architecture) | 🟡 | frontend-analysis |
| Dashboard SPA (live) | 🟢 Ready | ui-ux-audit-2026-07-18 |
| CLI / first-run UX | 🟡 | ux-analysis |
| Accessibility (WCAG AA) | 🟡 62% | accessibility-analysis |
| AIE commercial branch | 🟡 | ui-ux-review-aie-commercial |

### What Each Audit Found

| Category | frontend (7/10) | ux (7/10) | a11y (7/10) | live-audit (7/18) | aie-review (7/27) |
|----------|-----------------|-----------|-------------|-------------------|-------------------|
| **Strengths** | Token system, data layer, polling, responsive, dark mode | `setup` wizard, `wrap` command, lazy CLI, exception hierarchy | Semantic landmarks, `lang`, `role="alert"`, ARIA labels, `aria-busy` | Every route verified, 8 bugs fixed, 0 crashes, auto-recovery | Honest buyer report, skills preservation, attributed ROI |
| **Critical** | Component duplication (5× MetricCard) | 38+ commands overwhelm first-run | No skip-to-content link | Trace inspector froze proxy (backend) | Dual homepage positioning |
| **High** | Monolithic 3K-line CSS | No `from_env()` factory | Shimmer animation not reduced-motion-safe | `/health` 503 flapping (backend) | Buyer report leads with combined totals |
| **Medium** | Inline styles inconsistency | CLI help not grouped by phase | Trend chart missing ARIA roles | Gated toggles failed silently | `Cutctx` vs `CutCtx` brand casing |
| **Low** | Overview.jsx monolith | Setup vs init confusion | Docs sidebar icon `aria-hidden` | Currency `$0.000` format | Missing `data-cta` attributes |

---

## Unified Issue Tracker

### FIXED (verified in codebase)

| ID | Issue | Fixed In | Verification |
|----|-------|----------|--------------|
| F-1 | No skip-to-content link | `App.jsx:383` — `<a className="skip-link" href="#main-content">` | ✅ Present, `.skip-link` + `.skip-link:focus-visible` in `index.css:772-789` |
| F-2 | Shimmer animation under `prefers-reduced-motion` | `index.css:3510-3523` — `animation: none !important` global + `.skeleton { animation: none }` | ✅ Verified |
| F-3 | Gated feature toggles failed silently | `Governance.jsx` — `patchDashboardConfig` attaches structured error; row renders `role="alert"` | ✅ E2e-pinned |
| F-4 | Trace inspector froze proxy | `request_logger.py` — bounded 500-entry window + 32 MB byte cap + `asyncio.to_thread` | ✅ 404 in 16 ms |
| F-5 | `/health` 503 flapping | `server.py` — cache both success/failure outcomes | ✅ 6/6 stable 200s |
| F-6 | Raw reason codes in Recent requests | Shared operator copy with tooltip for raw code | ✅ Humanized labels |
| F-7 | Dev-proxy allowlist gaps | `vite.config.js` — `/policy`, `/transformations`, `/entitlements` added | ✅ Panels render data |
| F-8 | `$0.000` currency format | `formatCurrency` — exact zero → `$0.00`; sub-millidollar → `< $0.01` | ✅ Verified |
| F-9 | `WHEN` header mid-word wrap | `white-space: nowrap` | ✅ Verified |
| F-10 | Roles tab blank when empty | Real empty state added | ✅ Verified |
| F-11 | Generic page titles | Dynamic per-route titles via `Topbar` `useEffect` | ✅ Verified |
| F-12 | Escape key for mobile sidebar | `App.jsx:298` keydown handler | ✅ Verified |
| F-13 | Search keyboard shortcut | `/` key implemented in `App.jsx:316` | ✅ Verified |

### NOT FIXED (still present)

| ID | Issue | Source Audit | Severity | Location | Notes |
|----|-------|-------------|----------|----------|-------|
| **N-1** | Component duplication — MetricCard defined 5× | frontend-analysis | HIGH | `Overview.jsx:994`, `Savings.jsx:62`, `Memory.jsx:212`, `Firewall.jsx:314`, `Playground.jsx:400` | Each has slightly different props (`note` vs `footnote`, `iconColor` vs plain `icon`) |
| **N-2** | StatusBullet defined 3× | frontend-analysis | MEDIUM | `Memory.jsx:225`, `Firewall.jsx:327`, `Playground.jsx:413` | Identical interface, trivial to extract |
| **N-3** | ToggleSwitch defined 2× | frontend-analysis | MEDIUM | `Capabilities.jsx:39`, `Orchestrator.jsx:14` | Different prop names |
| **N-4** | SkeletonCard defined 2× | frontend-analysis | LOW | `Overview.jsx:44`, `Savings.jsx:44` | Identical |
| **N-5** | Monolithic `index.css` — 3,936 lines | frontend-analysis | HIGH | `dashboard/src/index.css` | Well-sectioned but one file |
| **N-6** | `Cutctx` vs `CutCtx` brand casing on website | aie-review | HIGH | `website/index.html:87` — "Cutctx" vs site-wide "CutCtx" | Looks unintentional |
| **N-7** | Dual homepage positioning | aie-review | MEDIUM | Hero = "context efficiency + routing"; `#context-plane` = "context control plane" | Two frames in first scroll |
| **N-8** | Buyer report leads with "Combined savings" before caveat | aie-review | HIGH | `cutctx/cli/report.py` | Skimmers miss honesty metrics |
| **N-9** | `skills.mdx` not cross-linked from onboarding docs | aie-review | MEDIUM | `global-routing.mdx`, `mcp.mdx`, quickstart | Feature discovery gap |
| **N-10** | Missing `data-cta` on new homepage buttons | aie-review | LOW | `website/index.html:93` | Analytics gap |
| **N-11** | CLI help lists 38+ commands alphabetically | ux-analysis | HIGH | `cutctx/cli/main.py:141-159` | First-run wall of commands |
| **N-12** | No `CutctxClient.from_env()` factory | ux-analysis | HIGH | `cutctx/client.py` | API friction |
| **N-13** | Error messages explain *what* but not *what to do* | ux-analysis | MEDIUM | `cutctx/cli/proxy.py`, `cutctx/exceptions.py` | Missing remediation steps |
| **N-14** | Trend chart bars lack keyboard navigation | accessibility-analysis | MEDIUM | Overview trend chart | No `tabindex` or arrow-key handling |
| **N-15** | Savings panel bars lack semantic meaning | accessibility-analysis | MEDIUM | Savings page | No ARIA roles on chart bars |
| **N-16** | No focus-visible styles beyond browser defaults | frontend-analysis | LOW | Global | Browser defaults vary; custom ring would unify |
| **N-17** | Overview.jsx monolith | frontend-analysis | MEDIUM | `Overview.jsx` — largest page file | Should be split into sub-components |

---

## Priority Matrix

### P0 — Must fix before commercial launch

| # | Issue | Effort | Impact | Owner |
|---|-------|--------|--------|-------|
| 1 | N-6: Fix `Cutctx` → `CutCtx` on website | 5 min | Brand trust | Frontend |
| 2 | N-8: Reorder buyer report — caveat + eligible/created vs observed above combined totals | 1 hr | Buyer clarity | CLI |
| 3 | N-1: Extract shared MetricCard component | 2-3 hrs | Maintainability | Frontend |
| 4 | N-11: Group CLI help by user phase | 4 hrs | First-run UX | CLI |

### P1 — High value, should fix soon

| # | Issue | Effort | Impact | Owner |
|---|-------|--------|--------|-------|
| 5 | N-12: Add `CutctxClient.from_env()` factory | 1 hr | API ergonomics | Backend |
| 6 | N-9: Cross-link `skills.mdx` from onboarding docs | 30 min | Feature discovery | Docs |
| 7 | N-13: Add "What to do" to common errors | 2-3 hrs | Error recovery | CLI |
| 8 | N-5: Break up `index.css` into partials | 4-6 hrs | Maintainability | Frontend |
| 9 | N-7: Unify homepage positioning (hero + context-plane) | 2 hrs | Messaging clarity | Marketing |

### P2 — Polish and competitive lift

| # | Issue | Effort | Impact | Owner |
|---|-------|--------|--------|-------|
| 10 | N-2: Extract StatusBullet to shared component | 1 hr | Consistency | Frontend |
| 11 | N-3: Extract ToggleSwitch to shared component | 1 hr | Consistency | Frontend |
| 12 | N-14: Add keyboard navigation to trend charts | 3-4 hrs | A11y | Frontend |
| 13 | N-15: Add ARIA roles to savings chart bars | 2 hrs | A11y | Frontend |
| 14 | N-17: Split Overview.jsx into sub-components | 4 hrs | Maintainability | Frontend |
| 15 | N-10: Add `data-cta` to homepage buttons | 15 min | Analytics | Frontend |
| 16 | N-16: Add custom focus-visible ring | 1 hr | A11y polish | Frontend |

---

## Accessibility Compliance Roadmap

### Current: 62% WCAG AA

| Phase | Target | Items | Est. Time |
|-------|--------|-------|-----------|
| **Phase 1** | 75% | N-14 (trend chart keyboard nav), N-15 (savings ARIA), fix remaining `aria-hidden` on decorative icons | 1-2 days |
| **Phase 2** | 85% | Light theme tertiary text contrast audit, heading hierarchy standardization, tooltip dismiss (Escape) | 3-5 days |
| **Phase 3** | 90%+ | Focus-visible custom ring, toggle switch input method review, Docs sidebar icons | 1 week |

### Previously Fixed (from accessibility-analysis re-check)

- ✅ Generic page title → dynamic per-route
- ✅ Escape key for mobile sidebar → keyboard handler
- ✅ Search keyboard shortcut → `/` key
- ✅ Skip-to-content link → present in `App.jsx`
- ✅ Shimmer under reduced-motion → `animation: none !important`

---

## Dashboard Release Readiness

Per `ui-ux-audit-2026-07-18.md`, the dashboard is **ready for release**:

- Every route renders with real data in both themes and three viewports
- Every interactive control works or explains itself
- Failure modes are honest and self-healing
- 28 dashboard e2e + 46 backend + 12 JS unit tests green
- Bundle: largest chunk (Overview) ~67 KB gz

**Remaining (not blockers):**
- Link tier-locked panels to plans page
- Virtualization if Recent requests exceeds ~50 rows
- Surface Safe Savings flag in Governance for discoverability

---

## AIE Commercial Branch Status

Per `ui-ux-review-aie-commercial.md`, the branch is **good direction, needs IA and copy tightening**:

**Strongest wins:**
- Honest buyer report with eligible vs all-traffic rates
- Skills preservation documentation
- Attributed ROI (more honest than most infra vendors)

**Before commercial launch (P0):**
1. Unify homepage positioning
2. Fix brand casing
3. Reorder buyer report sections
4. Add glossary line to buyer report

---

## Summary

| Area | Current State | Trend |
|------|---------------|-------|
| Dashboard architecture | Solid context provider, good separation | Stable |
| Component duplication | 5× MetricCard, 3× StatusBullet, 2× ToggleSwitch | Needs extraction |
| CSS maintainability | 3,936 lines in one file, well-sectioned | Needs splitting |
| Accessibility | 62% WCAG AA, skip link + reduced-motion fixed | Improving |
| CLI first-run UX | 38+ commands overwhelming | Needs grouping |
| Brand consistency | `Cutctx` vs `CutCtx` on website | Needs fix |
| Buyer report honesty | Excellent attribution model, poor information design | Needs reorder |
| Dashboard release readiness | ✅ Ready | — |
| Commercial readiness | Good direction, needs polish | In progress |

**Bottom line:** The dashboard is release-ready with strong foundations. The highest-impact remaining work is (1) extracting shared components to reduce duplication, (2) fixing brand casing on the website, (3) reordering the buyer report to lead with honesty metrics, and (4) grouping CLI help by user phase. These four items would move the overall rating from 🟡 to 🟢 across all surfaces.
