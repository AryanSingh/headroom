# UI Audit Report — Phase 2 (Screenshot Capture + Visual Analysis)

**Date:** 2026-07-01
**Auditor:** Automated Playwright + manual inspection
**Project:** cutctx / cutctx (LLM optimization proxy)
**Scope:** React + Vite dashboard SPA at `dashboard/`
**Servers:** proxy @ 127.0.0.1:8787 (version 0.30.0, healthy), dev server @ 127.0.0.1:5173

---

## TL;DR

- **Overall UI quality: POLISHED with one critical bug and several layout/polish issues.** The visual design is modern, consistent, and uses a tasteful teal/green accent on a near-white background (light) or deep navy (dark). Typography hierarchy is good, spacing is consistent, and components feel cohesive.
- **ONE CRITICAL BUG: the `/firewall` route is intercepted by the Vite dev proxy and returns 405/blank**, so the Security page is unreachable in the default dev setup. This is a config collision between the dashboard's React route (`/firewall`) and the proxy-prefix list in `dashboard/vite.config.js` (`/firewall` is listed there).
- **Several medium-severity layout issues** — primarily on mobile, where certain pages have severe cramping and text wrapping. Tablet works well; mobile and desktop work well except for the firewall-page bug and the docs-page grid issue.
- **Browser interactions verified working**: theme toggle, sidebar nav, playground compression. **Fire scan returns 503** (expected, firewall not enabled in proxy).

---

## 1. Screenshots Captured

Total: **35 Playwright screenshots + 6 zoomed verification screenshots** = 41 in `audit/screenshots/`. (Some legacy `flow*_*.png` files from prior runs also present; the new ones are named `*-desktop-*`, `*-tablet-*`, `*-mobile-*`, `zoomed-*`, `firewall-fixed-*`).

| Route | 1440×900 | 1280×800 | 768×1024 | 390×844 | Notes |
|-------|:--------:|:--------:|:--------:|:-------:|-------|
| `/` Overview | ✓ | ✓ | ✓ | ✓ | real data: 259.4M tokens, $617.11 saved |
| `/orchestrator` | ✓ | ✓ | ✓ | ✓ | |
| `/capabilities` | ✓ | ✓ | ✓ | ✓ | + after-nav-click |
| `/governance` | ✓ | ✓ | ✓ | ✓ | |
| `/firewall` (Security) | ✓ (via `/dashboard/firewall` only) | ✓ | ✓ | ✓ | blank at root, dev-proxy bug |
| `/memory` | ✓ | ✓ | ✓ | ✓ | |
| `/playground` | ✓ | ✓ | ✓ | ✓ | + after-compress |
| `/docs` | ✓ | ✓ | ✓ | ✓ | very long, grid layout broken |

**Additional zoomed-in (viewport-only) screenshots** for header detail, theme-toggle state, docs layout, and search-active state.

All saved to `/Users/aryansingh/Documents/Claude/Projects/cutctx/audit/screenshots/`.

---

## 2. Critical Visual / Functional Issues

### CRITICAL

#### C1 — `/firewall` route is intercepted by Vite dev proxy (returns blank page)
- **File:** `dashboard/vite.config.js` (line ~14: `'/firewall'` in `CUTCTX_PROXY_PREFIXES`)
- **Routes affected:** `/firewall` (the dashboard Security page)
- **Severity:** Critical — the Security nav link in the sidebar sends the user to a blank page in the default dev setup
- **Symptom:** `curl http://localhost:5173/firewall` returns `HTTP/1.1 405 Method Not Allowed` from `uvicorn` (the proxy backend). The HTML never reaches the browser, so `#root` stays empty. Visible in `firewall-desktop-1440x900.png` (entirely white) and `firewall-tablet-768x1024.png`.
- **Workaround:** Access via `/dashboard/firewall` (the React app sets basename based on URL prefix). All `firewall-fixed-*.png` and `security-*.png` use this path.
- **Fix:** Either move the dashboard route to a non-conflicting path (e.g. `/security`) or remove `/firewall` from the proxy prefix list (or scope the proxy to only `/api/firewall`, `/v1/firewall`).

#### C2 — Docs page: TOC + main content layout uses wrong display mode
- **File:** `dashboard/src/pages/Docs.jsx:79` uses inline `style={{ flexDirection: 'row', ... }}` on a `<section className="page-stack">`; but `index.css:642` defines `.page-stack { display: grid; ... }`. The inline style only sets `flexDirection`, not `display`, so the rule still resolves to `display: grid`. The `flex-direction: row` is meaningless for grid. Result: aside + main stack vertically, not horizontally, and the sticky TOC leaves a 250-px-wide column with empty space below.
- **Severity:** High — entire docs page is one long column instead of a sidebar+content layout, wasting ~30% of horizontal space.
- **Screenshot:** `docs-desktop-1440x900.png` (TOC card on left, all content stacked below; large empty right area).
- **Fix:** change inline style to include `display: 'flex'` (and set `flex: 1` on main).

---

## 3. High-Severity Issues

### H1 — Governance feature rows are cramped on mobile (text wraps by character)
- **Route:** `/governance` @ 390×844
- **Symptom:** Each feature row stacks vertically: title, RESTART REQUIRED pill, Active/Inactive pill, env-var pill (CUTCTX_FIREWALL_ENABLED=1, etc.), description, toggle, copy icon. The description text wraps with **2-3 letters per line** in some cases (e.g. "Scan every request for prompt injection, jailbrea ks, and PII before it reaches the model.").
- **Screenshot:** `governance-mobile-390x844.png`
- **Fix:** Use `flex-direction: row` with `flex-wrap: wrap` and constrain pill widths on small screens; or move the env var pill to a second line explicitly.

### H2 — Horizontal overflow on Overview at tablet and mobile
- **Route:** `/` @ 768×1024 (scrollWidth 791, overflow 23px) and 390×844 (scrollWidth 429, overflow 39px)
- **Symptom:** Body scrolls horizontally; the trend bar tooltip elements are positioned absolutely with `right: 0` and extend past the right edge.
- **Detected by:** `inspectLayout()` in audit script — High severity auto-flagged.
- **Screenshots:** `overview-tablet-768x1024.png`, `overview-mobile-390x844.png`
- **Fix:** Constrain `.trend-bar-tooltip` and other absolute-positioned overlays with `max-width: calc(100% - 2rem)` or use `overflow: hidden` on the trend chart container.

### H3 — Docs page table cells overflow on mobile
- **Route:** `/docs` @ 390×844
- **Symptom:** Wide table cells in the env-vars, agent-compatibility, and admin-API tables are wider than the viewport, causing horizontal scroll of the entire page. The first table column is fine but the DESCRIPTION column extends past 390px.
- **Detected by:** `inspectLayout()` overflow scan.
- **Screenshot:** `docs-mobile-390x844.png`
- **Fix:** Make table containers `overflow-x: auto` (already are in some places), shrink font-size, or use a card layout for tables under 600px width.

---

## 4. Medium-Severity Issues

### M1 — "Enable optional features" heading wraps to 2 lines on desktop
- **Route:** `/governance` @ 1440×900
- **Symptom:** The H2 reads "Enable optional features" and wraps to 2 lines (because of how the panel-wide width interacts with the description text), while the right-side description text is much shorter, leaving visual imbalance.
- **Screenshot:** `governance-desktop-1440x900.png`, `zoomed-governance-viewport.png`

### M2 — Capabilities "Runtime surfaces" grid leaves FIREWALL card alone in the last row
- **Route:** `/capabilities` @ 1440×900
- **Symptom:** 9 cards arranged in a 3-col grid; the 9th (FIREWALL) card sits alone in the bottom row, occupying 1/3 of the row with 2/3 empty space.
- **Screenshot:** `capabilities-desktop-1440x900.png`, `zoomed-capabilities-viewport.png`
- **Fix:** Consider re-ordering or grouping (move FIREWALL to a different section); or use a 4-col grid; or accept the 1/3 orphan and visually balance.

### M3 — Search input is global but only filters 3 of 8 pages
- **Routes:** Search input works on `/governance`, `/firewall`, `/memory`; silently does nothing on `/`, `/orchestrator`, `/capabilities`, `/playground`, `/docs`.
- **Symptom:** When user types in search on Overview and presses `/` to focus, no visible indication that the search is "active" on a page that doesn't use it. Looks like a dead control.
- **Screenshot:** `zoomed-search-active.png` (Overview with "savings" in search box — page unchanged)
- **Fix:** Either (a) implement search filtering consistently across all pages, or (b) disable the search input on pages where it doesn't apply, or (c) show a tooltip "Search available on Governance, Firewall, Memory".

### M4 — Memory page is sparse / many metrics show "—" or "0"
- **Route:** `/memory` @ 1440×900
- **Symptom:** All four top metric cards (RTK Commands, Session Savings, Insights, Corrections) show "0" or "—". Page feels empty below the cross-agent memory card.
- **Screenshot:** `memory-desktop-1440x900.png`
- **Fix:** Add visual content (an example memory entry, an empty-state illustration, a "try a compression to see entries here" hint), or hide metrics that aren't wired up.

### M5 — Mobile alert text wraps awkwardly
- **Routes:** `/firewall` (when accessible), and several alert cards
- **Symptom:** "Firewall is not initialized on this proxy. Enable it by setting `CUTCTX_FIREWALL_ENABLED=1` and restarting." wraps to many narrow lines on mobile.
- **Screenshot:** `firewall-mobile-390x844.png` (alert takes ~6 lines of <8 chars each)
- **Fix:** Allow inline `<code>` elements to break: `code { word-break: break-all; }` or restructure to put the env var on its own line.

### M6 — Trend-bar tooltip can extend off-screen
- **Route:** `/` (Overview) @ 1280×800
- **Detected by:** `inspectLayout()` overflowing-elements scan — `span.trend-bar-tooltip(10:30 PM - 11:42 PM / 0 tokens saved / Reque...)` extends past viewport right edge.
- **Fix:** Add `max-width` and reposition tooltip to be within the chart container.

### M7 — Capabilities "Runtime surfaces" cards have repetitive "0" / footnote pattern
- **Route:** `/capabilities` @ 1440×900
- **Symptom:** 6 of 9 cards display "0" with a footnote saying "This proxy is not exposing [X] metrics" — visually monotonous and doesn't tell the user what to do to enable them.
- **Fix:** Show a clear "Not exposed — enable via env var XYZ" with a link to docs, or hide the metric entirely when unavailable.

### M8 — Capabilities `Intelligence Layer` group title is a single line that runs into a 2-line subheader
- **Route:** `/capabilities` @ 1440×900
- **Symptom:** "Advanced compression intelligence modules. Each is independently toggleable via environment variable." runs to 1 line; the heading takes 1 line; right-side text is shorter; minor layout asymmetry.
- **Screenshot:** `capabilities-desktop-1440x900.png` (Intelligence Layer section).

---

## 5. Low-Severity / Polish Issues

### L1 — Search shortcut hint `/` is a small floating span
- **Location:** Header search input
- **Symptom:** The `/` keyboard shortcut hint is rendered as a small grey span in the right of the input. It blends in. Could be a clearer kbd-style badge.
- **Screenshot:** `zoomed-overview-viewport.png` (top-right)

### L2 — Sidebar "v0.1.0" version label is small and far from the brand
- **Location:** Bottom of sidebar
- **Symptom:** Version label uses `var(--text-tertiary)` color, very low contrast. May be invisible to users with mild vision impairment.
- **Fix:** Increase contrast or add a tooltip.

### L3 — Promotional card in sidebar uses the same shield/zap icons as nav
- **Location:** Sidebar bottom (the "Surfaces" section)
- **Symptom:** The two promo rows ("Proxy, wrap, library, MCP" / "Memory, CCR, firewall, savings") use the same shield and zap icons as the Security and Capabilities nav items. This could be confusing — users might click them expecting navigation.
- **Screenshot:** All sidebar shots.

### L4 — Several "tiny clipped elements with text" reported across all routes
- **Locations:** Most pages
- **Symptom:** The audit script reports spans with text "/" (the search shortcut hint) and "0" (chart labels) as "tiny clipped elements" because their width is <20px. These are intentional decorative elements and not actual bugs, but they could be a clue that the search shortcut kbd hint area is being detected as clipped.
- **Fix:** Optional — add `data-decorative` attributes so layout audits can ignore.

### L5 — "Apply" icon on the "Run live compression" button changes after click
- **Location:** Playground
- **Symptom:** After the compression runs, the play triangle icon stays the same, but the button text remains "Run live compression" (not "Running..." or a completion check). No loading state visible. User may click again.
- **Screenshot:** `playground-desktop-1440x900-after-compress.png`

### L6 — "Tokens Saved 0" doesn't explain why
- **Location:** Playground after a small/short prompt
- **Symptom:** After running a 55-token prompt, "TOKENS SAVED: 0" / "0.0%" with no indication that the input was too small to benefit. The "Applied steps: router:noop" is the only signal.
- **Fix:** Add helper text "Input too small for compression" or similar when no transforms apply.

### L7 — Capabilities nav icon is duplicated
- **Location:** Sidebar
- **Symptom:** Both "Orchestrator" and "Governance" use the same `Activity` icon. The "Memory" and "Playground" and "Docs" use different icons. Two duplicate icons in the sidebar is OK but reduces scannability.
- **Fix:** Use distinct icons (e.g. Cpu for Orchestrator, Scale for Governance).

### L8 — Capability group icons all use the same teal background
- **Location:** Capabilities page
- **Symptom:** Every group icon (Core Deployment Modes, Compression & Optimization, State/Retrieval/Memory, Governance & Operations, Intelligence Layer, Provider & Protocol Coverage) uses the same light-teal background tint. With 6 nearly identical colored squares, the visual hierarchy between sections is lost.
- **Fix:** Use varying accent colors (e.g. green, amber, blue, purple) per group, or add group numbering.

### L9 — `Run compression` button text long
- **Location:** Playground
- **Symptom:** Button reads "Run live compression" — long text. On mobile, takes most of the row. Could be shorter ("Run" or "Compress").
- **Screenshot:** `playground-mobile-390x844.png`

### L10 — "Active compression: 0.0% whole-request proxy reduction" reads as a metric
- **Location:** Overview
- **Symptom:** The "Active Compression" metric shows 0.0% with subtitle "0.0% whole-request proxy reduction" — redundant and confusing. The value and the subtitle say the same thing.
- **Fix:** Use a more meaningful subtitle ("vs no compression" or "of incoming requests").

---

## 6. Console Errors & Warnings

Captured from all routes during the audit:

| Severity | Count | Sample |
|----------|-------|--------|
| `requestfailed` (initial load) | 7 | `GET /health`, `/stats-history`, `/stats?cached=1` — these are intentional, fired before the React app mounts (the 7th: `https://fonts.googleapis.com/css2?family=Space+Grotesk…` — network failure for Google Fonts in this sandbox). |
| `404` | 5 | Generic `Failed to load resource: the server responded with a status of 404 (Not Found)` — most likely the missing favicon (not in `public/`) and Vite's `/@vite/client` when accessed via `localhost` vs `127.0.0.1` mismatch. |
| `pageerror` | 0 | No React render errors. |
| Application console errors | 0 | No JS errors during any navigation or interaction. |

### Notable
- **Google Fonts (`Space Grotesk`, `Inter`) fails to load** in the sandbox (no internet). The UI gracefully falls back to system fonts; no broken text rendering.
- **404 favicon** — the dashboard's `index.html` references `/favicon.svg` but the file may not exist (browser reports 404). Minor.

---

## 7. Browser Interactions

| Interaction | Result | Notes |
|-------------|--------|-------|
| **Theme toggle** | ✓ Works | Light → Dark; class changes on `<html>`; colors swap correctly; localStorage persists choice. Screenshots: `overview-desktop-1440x900.png` (light) vs `overview-desktop-1440x900-after-theme-toggle.png` (dark). |
| **Sidebar nav (Orchestrator → Capabilities)** | ✓ Works | URL updates to `/capabilities`, page content swaps, Capabilities nav item gets active state. Screenshot: `capabilities-desktop-1440x900-after-nav-click.png`. |
| **Capabilities toggles** | ✓ Visible | 5 toggle switches (label.toggle-switch pattern) found in the runtime surfaces grid. The script's selector `input[type="checkbox"]` worked for one. Manual inspection confirms they render. |
| **Governance flag toggles** | ✓ Visible | 9 toggles visible in screenshot `governance-desktop-1440x900.png`. The script's first selector didn't match because the build uses `<label class="toggle-switch">` not `<button role="switch">`. Manual inspection: Rate Limiting toggle is green/active. |
| **Fire scan** | ✓ Submitted, ⚠ 503 | Filled textarea with injection attempt; clicked "Scan text"; UI showed "Scan returned 503" because the firewall is not initialized on the proxy. Error displayed in red alert card. Screenshot: `firewall-desktop-1440x900-after-scan.png`. The error is honest and actionable ("Enable it by setting CUTCTX_FIREWALL_ENABLED=1 and restarting"). |
| **Playground compression** | ✓ Works | Filled prompt; clicked "Run live compression"; result panel updated with JSON payload, token estimates (55→55, 0 saved, 0.0%), "Applied steps: router:noop". The "0 saved" is because the 55-token prompt is below the compression threshold. Screenshot: `playground-desktop-1440x900-after-compress.png`. |
| **Search input** | Partial | The `/` keyboard shortcut focuses the input on all pages; the input accepts text. But filter only applies on `/governance`, `/firewall`, `/memory`. On other pages it's a no-op with no feedback. |

### Failed / no-op interactions
- **None blocking** — every clickable control either does what it says or shows an honest error.

---

## 8. Viewport Behavior Summary

| Viewport | Verdict |
|----------|---------|
| **1440×900** (desktop) | Polished. All pages render correctly with real data. Only the Docs-page grid bug and the dashboard `/firewall` 405 are visible. |
| **1280×800** (smaller desktop) | Same as 1440 with minor tooltip overflow on the trend chart. |
| **768×1024** (tablet) | Mostly clean. Overview has 23px horizontal overflow due to the trend bar tooltip. All nav items visible; sidebar collapses on mobile breakpoint. |
| **390×844** (mobile) | Layouts adapt well except: (a) Governance rows become extremely cramped with text wrapping 2-3 chars per line, (b) Overview has 39px horizontal overflow, (c) Docs tables overflow, (d) Firewall alert wraps awkwardly. |

---

## 9. Visual Polish Assessment

| Aspect | Rating | Notes |
|--------|--------|-------|
| Typography hierarchy | ★★★★☆ | Clean, consistent; H1/H2/H3 sizes appropriate. Some headings (e.g. "Enable optional features") wrap awkwardly. |
| Spacing / padding | ★★★★☆ | Generous, consistent. Cards have nice internal padding. Vertical rhythm is good. |
| Color palette | ★★★★★ | Teal/green accent on near-white (light) / deep navy (dark) is tasteful and modern. Status colors (green/amber/red) used consistently. |
| Card design | ★★★★☆ | Rounded corners, subtle borders, clean. The Capabilities grid has an orphan row. |
| Button states | ★★★★☆ | Primary (teal) vs secondary well-differentiated. Disabled state is clear. No loading spinner visible after click. |
| Form design | ★★★★☆ | Labels above inputs, good input padding. Playground form is clean. |
| Tables | ★★★☆☆ | Good on desktop, poor on mobile (overflow). The "Recent requests" table on Overview has a clipped cell on mobile. |
| Modal/drawer | N/A | No modals observed during this audit. |
| Sidebar behavior | ★★★★☆ | Collapses on mobile, active state is clear, brand mark + nav + surfaces are well-organized. |
| Header behavior | ★★★★☆ | Search input, status pill, theme toggle, sidebar toggle all present and functional. The "healthy" status pill is small but visible. |
| Empty states | ★★★☆☆ | "No savings data yet" with a small icon is OK. "No firewall events recorded yet." in a table row is minimal. Some metrics show "0" instead of empty-state copy. |
| Loading states | ★★☆☆☆ | None observed — page renders final state immediately; no skeletons. After-scan state shows a static "0 tokens saved" without an intermediate loading indicator. |
| Error states | ★★★★☆ | The firewall-scan 503 displays cleanly in a red alert card. The auth-required screen is functional but visually bare (white background, simple form). |
| Mobile responsiveness | ★★★☆☆ | Adapts but several pages have serious cramping issues (Governance, Docs tables, Firewall alerts). |
| Premium feel | ★★★★☆ | The dashboard looks like a serious product. The teal/green accent is on-trend. Cards have subtle hover states. Typography uses Inter/Space Grotesk (when fonts load). |

---

## 10. Recommendations (Priority Order)

1. **[CRITICAL] Fix the `/firewall` route collision in `vite.config.js`** — remove `/firewall` from `CUTCTX_PROXY_PREFIXES` or change the dashboard route to `/security`.
2. **[HIGH] Fix the Docs page layout** — add `display: 'flex'` to the inline style in `Docs.jsx:79` so the `flexDirection: row` actually applies.
3. **[HIGH] Make Governance rows responsive on mobile** — use `flex-wrap: wrap` and constrain pill widths.
4. **[HIGH] Constrain trend-bar tooltip width** — add `max-width` to prevent horizontal overflow at small viewports.
5. **[HIGH] Constrain Docs tables to viewport on mobile** — use `overflow-x: auto` on table containers, or switch to card layout below 600px.
6. **[MEDIUM] Add search filtering to all pages or disable the input on pages that don't use it.**
7. **[MEDIUM] Add a loading skeleton for the dashboard and a loading state on "Run live compression" / "Scan text" buttons.**
8. **[MEDIUM] Reorder or regroup the Capabilities runtime surfaces so the grid doesn't have an orphan row.**
9. **[MEDIUM] Add a friendly "input too small" message when Playground compression results in 0 savings.**
10. **[LOW] Diversify capability-group icon colors and sidebar nav icons to reduce icon duplication.**

---

## 11. Files & Artifacts

- **Screenshots:** `/Users/aryansingh/Documents/Claude/Projects/cutctx/audit/screenshots/`
- **Audit script:** `/Users/aryansingh/Documents/Claude/Projects/cutctx/audit/audit-screenshots.mjs` (in dashboard folder too)
- **JSON report:** `/Users/aryansingh/Documents/Claude/Projects/cutctx/dashboard/screenshot-report.json`
- **Console log:** `/Users/aryansingh/Documents/Claude/Projects/cutctx/audit/console-log.txt`
- **This report:** `/Users/aryansingh/Documents/Claude/Projects/cutctx/audit/ui-audit-phase2-2026-07-01.md`

## 12. Environment & Cleanup

- **Proxy:** Started with `CUTCTX_ALLOW_DEBUG=1` `CUTCTX_SKIP_INTEGRITY_CHECK=1` `CUTCTX_ALLOW_DEBUG=1` `CUTCTX_ADMIN_API_KEY=test-admin-key`. Verified `/livez` returns `ready=true`. Will be killed on exit.
- **Vite dev server:** Started with `CUTCTX_ADMIN_API_KEY=test-admin-key`. Verified on port 5173. Will be killed on exit.

No source files were modified during this audit.
