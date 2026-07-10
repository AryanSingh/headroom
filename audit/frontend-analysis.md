# Cutctx Dashboard — Frontend Analysis

**Date:** 2026-07-10
**Scope:** `dashboard/src/` (React SPA, Vite 8 build)
**Total source lines:** ~10,900 across 22 files

---

## Frontend Rating: 🟡

The dashboard is functional and well-structured at the architectural level, but carries significant component duplication, a monolithic CSS file, and heavy inline styling that undermine maintainability. It ships a solid dark-mode-first experience with real-time polling, but the codebase is ripe for a shared component extraction pass.

---

## Key Strengths

- **Solid design token system** — `index.css:7-48` defines a complete spacing, typography, radius, and color token set with proper dark/light theme variables. This is the foundation a real design system needs.
- **Centralized data layer** — `dashboard-context.jsx` + `use-dashboard-data.js` provide a single context provider with polling (5s stats, 60s history), loading/error states, and a clean `useDashboardData()` hook. Every page consumes the same data source consistently.
- **Real-time polling with cleanup** — `dashboard-context.jsx:86-115` properly manages `setInterval` with cancellation flags and `clearInterval` on unmount. No leaked timers.
- **Responsive by default** — Three breakpoints (`@media` at 1200px, 1024px, 640px) in `index.css:2289-2559` handle tablet, collapsed-sidebar, and mobile layouts. The sidebar becomes a slide-out drawer on `<1024px`.
- **Dark/light theme with flash prevention** — `main.jsx:12-18` applies the theme class before React mounts, preventing the common dark-mode flash. Theme persists to localStorage.

---

## Critical Issues

### 1. Component Duplication — HIGH
**Files:** 5 pages define their own `MetricCard`, 3 pages define `StatusBullet`, 2 pages define `ToggleSwitch`, 2 pages define `SkeletonCard`.

| Component | Defined In | Line |
|-----------|-----------|------|
| `MetricCard` | `Overview.jsx:960`, `Savings.jsx:64`, `Memory.jsx:184`, `Firewall.jsx:287`, `Playground.jsx:395` | 5 copies |
| `StatusBullet` | `Firewall.jsx:300`, `Memory.jsx:197`, `Playground.jsx:408` | 3 copies |
| `ToggleSwitch` | `Capabilities.jsx:36`, `Orchestrator.jsx:14` | 2 copies |
| `SkeletonCard` | `Overview.jsx:43`, `Savings.jsx:42` | 2 copies |

**Impact:** Bug fixes and style changes must be replicated across 5 files. The `MetricCard` variants have subtly different prop signatures (`note` vs `footnote`, `iconColor` vs plain `icon`), making consolidation non-trivial but necessary.

**Recommendation:** Extract to `src/components/MetricCard.jsx`, `StatusBullet.jsx`, `ToggleSwitch.jsx`, `SkeletonCard.jsx`. Normalize prop interfaces.

---

### 2. Monolithic CSS File — HIGH
**File:** `index.css` — **3,040 lines**
**File:** `App.css` — **1 line** (just a comment: `/* All styles are in index.css */`)

All styles live in a single file. While well-organized with section comments (DESIGN TOKENS, DARK THEME, LIGHT THEME, LAYOUT, etc.), this creates:
- Merge conflicts when multiple developers edit different sections
- No co-location with components — styles are global and implicitly coupled
- Difficulty finding which styles belong to which page

**Recommendation:** Split into CSS modules or component-scoped CSS files. At minimum, extract page-specific styles (Overview has ~500 lines of unique CSS, Governance ~200 lines).

---

### 3. Excessive Inline Styles — MEDIUM
**Occurrences:** 100+ `style={}` instances across JSX files.

Worst offenders:
- `Overview.jsx` — 35+ inline style objects, many for layout (`display: 'grid'`, `gap: '12px'`)
- `Docs.jsx` — 25+ inline style objects for typography and spacing
- `Capabilities.jsx` — 8 inline style objects including the entire `ToggleSwitch` component

The `ToggleSwitch` in `Capabilities.jsx:36-72` and `Orchestrator.jsx:14-52` are almost entirely inline-styled, duplicating ~35 lines each.

**Recommendation:** Move to CSS classes. The `ToggleSwitch` already has a `.feature-toggle` CSS class defined in `index.css:2758-2800` but the JSX components don't use it — they use inline styles instead.

---

### 4. Overview.jsx Monolith — MEDIUM
**File:** `Overview.jsx` — **2,760 lines**

This single file contains:
- `SkeletonCard`, `SkeletonBar`, `EmptyState`, `MetricCard`, `QuickAction`, `AttributionMetricToggle`
- `TrendChart` (with SVG rendering, hover tooltips, axis labels)
- `SavingsPanel`, `SavingsSourceTable`, `SavingsModelTable`
- `ProviderStatusPanel`, `LearnedPoliciesPanel`
- Session savings computation logic
- Multiple data transformation functions

**Recommendation:** Extract `TrendChart`, `SavingsPanel`, and provider status components into separate files.

---

### 5. No Shared Component Library — MEDIUM
There is no `src/components/` directory. All components are defined inline within page files. This means:
- No reusable UI primitives (buttons, cards, alerts, badges)
- Each page reinvents layout patterns
- No Storybook or component documentation

---

## Quick Wins (Can Fix in <1 Week)

### 1. Extract shared components
Create `src/components/` directory and move:
- `MetricCard` → normalize to single prop interface (`icon`, `label`, `value`, `note`, optional `sparkline`)
- `StatusBullet` → identical across 3 files, trivial extraction
- `ToggleSwitch` → use existing `.feature-toggle` CSS class instead of inline styles
- `SkeletonCard` + `SkeletonBar` → identical implementations

**Estimated effort:** 2-3 hours

### 2. Normalize ToggleSwitch to use CSS
Both `Capabilities.jsx:36-72` and `Orchestrator.jsx:14-52` define `ToggleSwitch` with full inline styles. The CSS already has `.feature-toggle`, `.feature-toggle-on`, `.feature-toggle-off`, `.feature-toggle-knob` classes at `index.css:2758-2800`. Just wire them up.

**Estimated effort:** 30 minutes

### 3. Extract TrendChart from Overview.jsx
The `TrendChart` component (`Overview.jsx:850-957`) is self-contained with clear props. Moving it to `src/components/TrendChart.jsx` would reduce Overview.jsx by ~100 lines and make the chart reusable.

**Estimated effort:** 30 minutes

### 4. Add missing `alt` text and ARIA labels
Current accessibility audit:
- ✅ `aria-label` on navigation, search, theme toggle (`App.jsx:112,206,228`)
- ✅ `role="alert"` on error states
- ✅ `aria-hidden="true"` on decorative icons
- ❌ No `alt` text on `hero.png` asset (though not currently used in JSX)
- ❌ `SavingsPanel` bar charts lack `role="img"` or `aria-label`
- ❌ Trend chart bars lack keyboard accessibility (no `tabIndex`, no `onKeyDown`)

**Estimated effort:** 1-2 hours

---

## Detailed Analysis

### Component Architecture

**Structure:**
```
src/
├── App.jsx              (402 lines — routing, layout, sidebar, topbar)
├── main.jsx             (24 lines — entry point, theme flash prevention)
├── index.css            (3,040 lines — ALL styles)
├── App.css              (1 line — empty)
├── pages/
│   ├── Overview.jsx     (2,760 lines — ⚠️ monolith)
│   ├── Savings.jsx      (580 lines)
│   ├── Governance.jsx   (708 lines)
│   ├── Docs.jsx         (579 lines)
│   ├── Capabilities.jsx (349 lines)
│   ├── Orchestrator.jsx (491 lines)
│   ├── Firewall.jsx     (307 lines)
│   ├── Playground.jsx   (415 lines)
│   ├── Memory.jsx       (204 lines)
│   └── Replay.jsx       (142 lines)
├── lib/
│   ├── dashboard-context.jsx     (147 lines — data provider)
│   ├── dashboard-context-value.js (3 lines — context creation)
│   ├── use-dashboard-data.js     (152 lines — fetch utilities)
│   ├── theme-context.jsx         (64 lines — theme provider)
│   ├── api.js                    (30 lines — proxy URL helpers)
│   ├── admin-auth.js             (134 lines — key storage)
│   ├── format.js                 (88 lines — number formatting)
│   ├── period-stats.js           (135 lines — time aggregation)
│   └── savings-sources.js        (182 lines — savings computation)
└── data/
    └── capabilities.js           (68 lines — static capability data)
```

**Routing:** React Router v7 with 10 routes. Clean route definitions at `App.jsx:362-374`. Wildcard redirects to `/`.

**Layout:** CSS Grid shell (`app-shell`) with sidebar + topbar + main content area. Sidebar collapses to drawer on mobile.

**Error Handling:** `ErrorBoundary` class component at `App.jsx:37-60` wraps all routes. Each page has its own loading/error/empty states.

### CSS Quality

**Organization:** Excellent section comments with box-drawing separators. Logical grouping:
1. Design tokens (lines 7-48)
2. Dark theme (lines 54-98)
3. Light theme (lines 100-142)
4. Base/reset (lines 144-250)
5. Layout shell (lines 252-400)
6. Components (lines 400-2000)
7. Page-specific (lines 2000-2800)
8. Responsive (lines 2289-2559, 2901-3040)

**Token usage:** Consistent use of CSS custom properties for spacing (`--space-*`), typography (`--text-*`), colors (`--surface-*`, `--text-*`, `--accent`), and borders (`--border-*`). Very few hardcoded values.

**Responsive breakpoints:**
- `@media (max-width: 1200px)` — tablet grid adjustments
- `@media (max-width: 1024px)` — sidebar collapse, layout shifts
- `@media (max-width: 640px)` — mobile single-column, reduced padding
- `@media (prefers-reduced-motion: reduce)` — disables all transitions

**Theme system:** Dark mode default with `color-mix()` for subtle tints. Light mode inverts surface hierarchy. Both use the same accent color (`#2dd4bf` teal).

### Data Flow

**Primary data source:** `DashboardDataProvider` (`dashboard-context.jsx`) wraps the entire app and provides:
- `stats` — `/stats?cached=1` polled every 5 seconds
- `health` — `/health` polled every 5 seconds
- `configFlags` — `/config/flags` or `/admin/config/flags` (one-time fetch)
- `historyData` — `/stats-history` polled every 60 seconds
- `loading`, `error`, `lastUpdated` — standard async state

**Page-level fetching:** Some pages make additional fetches:
- `Memory.jsx:19` — `/v1/memory/query?limit=20` (one-time)
- `Firewall.jsx:43` — `/firewall/status` + `/audit/events?limit=20` (one-time)
- `Governance.jsx` — `/audit/events`, `/entitlements`, `/rbac/roles` (one-time)
- `Savings.jsx` — `/stats-history?series={duration}` (on duration change)
- `Playground.jsx` — `/v1/messages` (user-triggered POST)
- `Replay.jsx` — `/v1/sessions/{id}/replay` (user-triggered)

**No SSE/WebSocket:** All data is fetched via REST polling. No real-time push.

**Auth:** Admin key stored in localStorage, sessionStorage, cookie, and in-memory (`admin-auth.js`). Sent as `x-cutctx-admin-key` header. URL `?key=` param auto-adopted and stripped.

### State Management

- **React Context:** Two providers — `DashboardDataProvider` (data) and `ThemeProvider` (theme)
- **Local useState:** Each page manages its own loading/error/data states
- **No external stores:** No Redux, Zustand, Jotai, or similar
- **No React Query/SWR:** Manual caching via context, no deduplication or stale-while-revalidate

**Pattern:** Pages consume `useDashboardData()` for shared stats, then maintain local state for page-specific data. This works but means every page re-renders when any stats update (since the context value changes).

### Build & Dependencies

**Runtime dependencies (3):**
- `react` 19.2.6
- `react-dom` 19.2.6
- `react-router-dom` 7.18.0
- `lucide-react` 1.21.0 (icons)

**Dev dependencies:**
- `vite` 8.0.12 with `@vitejs/plugin-react` 6.0.1
- `eslint` 10.3.0
- `@playwright/test` 1.61.0 (E2E testing)
- `javascript-obfuscator` 5.4.3 (production bundle obfuscation, currently disabled)

**Notable:** No CSS framework (Tailwind, etc.) — pure hand-written CSS. No TypeScript. No component library (MUI, Chakra, etc.).

**Vite config** (`vite.config.js`): Custom proxy plugin routes API calls to local Cutctx proxy during dev. Source maps disabled in production. Obfuscation available but commented out.

### Visual Polish & UX

**Loading states:** Consistent skeleton patterns (`skeleton-card`, `skeleton-line`, `skeleton-value`) with CSS animations. Pages show skeletons while data loads.

**Empty states:** Custom illustrations for "no data" scenarios (`overview-empty` class with icon + text).

**Error states:** `alert-card` with `role="alert"` for fetch failures. Graceful degradation — pages show partial data when some endpoints fail.

**Transitions:** CSS transitions on hover states, sidebar open/close, theme toggle. `prefers-reduced-motion` respected.

**Responsive:** Three breakpoints handle desktop → tablet → mobile. Sidebar becomes overlay drawer. Metric grids collapse from 4→2→1 columns.

**Accessibility gaps:**
- Trend chart bars lack keyboard navigation
- Savings panel bars lack semantic meaning for screen readers
- No skip-to-content link
- No focus-visible styles beyond browser defaults

### Recent Changes (Since July 8)

**`c6bdbf85` — fix: dashboard current session shows $0 for money saved**
This was a data computation bug, not a UI issue. The fix was in the savings aggregation logic, ensuring session-level savings are properly summed from all sources (not just compression).

**`8e94a6f4` — Ship governance and routing audit fixes**
Governance page improvements and model routing fixes.

No CSS or component-level changes in the recent commits — all fixes were data/logic layer.

---

## Summary

| Area | Rating | Notes |
|------|--------|-------|
| Architecture | 🟢 | Clean context provider, good separation of concerns |
| CSS | 🟡 | Well-tokenized but monolithic, 3K lines in one file |
| Data Flow | 🟡 | Solid polling pattern, but no real-time push |
| State Management | 🟢 | Appropriate for scope, no over-engineering |
| Build | 🟢 | Modern Vite 8, minimal dependencies |
| Visual Polish | 🟡 | Good dark mode, but inline styles hurt consistency |
| Accessibility | 🟡 | Basics covered, missing keyboard nav and ARIA on charts |
| Maintainability | 🔴 | Component duplication and Overview.jsx monolith |

**Priority actions:**
1. Extract shared components (MetricCard, StatusBullet, ToggleSwitch, SkeletonCard)
2. Break up Overview.jsx into smaller files
3. Move inline styles to CSS classes
4. Add keyboard navigation to interactive charts
