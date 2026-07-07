# Frontend Analysis — CutCtx Dashboard

**Date:** 2026-07-08
**Stack:** React 19, Vite 8, React Router 7, Lucide React, Custom CSS
**Files analyzed:** 14 JSX/JS modules, 1 CSS file (~2835 lines), 3 assets

---

## Architecture

The dashboard is a single-page app with 10 page routes (Overview, Savings, Governance, Firewall, Memory, Orchestrator, Capabilities, Playground, Replay, Docs) rendered inside a persistent shell with sidebar navigation and a top bar. Two React context providers sit above the router: `ThemeProvider` for dark/light toggle and `DashboardDataProvider` for centralized data fetching. No component library — every UI element is hand-rolled against a custom CSS design system. No Tailwind. No animation library.

The component tree is flat: `App` → `AppFrame` (sidebar + topbar + routes) → page components. There is no `components/` directory — every reusable piece (`MetricCard`, `StatusBullet`, `ToggleSwitch`, `SkeletonCard`) is defined locally inside individual page files and duplicated verbatim across 5+ pages.

---

## CSS & Design System

The entire design system lives in a single `index.css` (2835 lines). It defines CSS custom properties for spacing, typography, colors, radii, shadows, and surface tokens in `:root`, with dark mode overrides on `.dark` and `.light` classes. The palette is teal/cyan accent (`--accent: #14b8a6`) against near-black surfaces, with semantic colors for status states (green, amber, red, blue). Typography uses Space Grotesk for display and Inter for body — both loaded via Google Fonts.

**Strengths:** The token system is thorough and consistent. Surface layering (3 tiers) creates genuine depth. The trend chart is fully CSS-driven with hover tooltips, grid lines, and responsive reflow. Responsive breakpoints are well-structured: tablet (1200px), collapsed sidebar (1024px), mobile (640px) with progressive simplification.

**Weaknesses:** The single-file CSS approach means every new page adds rules to the same monolith. Some classes are defined in the "MISSING DASHBOARD CLASSES (Audit Fixes)" section (lines 2638-2723), suggesting organic growth without cleanup. The `.capability-panel` rule at line 2721 is empty. A few responsive rules duplicate selectors (`.trend-chart-container` height is set twice in the 640px block).

---

## State Management & Data Fetching

Data flows through `DashboardDataProvider`, which polls `/stats?cached=1` and `/health` every 5 seconds, plus `/stats-history` every 60 seconds. Config flags are fetched once on mount with fallback between `/config/flags` and `/admin/config/flags`. The provider memoizes its context value to avoid unnecessary re-renders. Pages consume data via `useDashboardData()` and make additional endpoint-specific fetches (firewall events, memory items, orchestrator routes, replay sessions) inside their own `useEffect` hooks with manual `cancelled` flags for cleanup.

**Strengths:** The polling model is pragmatic for a monitoring dashboard. The context avoids prop-drilling. Error handling distinguishes "endpoint doesn't exist" (404/501/503) from real failures.

**Weaknesses:** Every page independently manages its own loading/error/data states with raw `useState` + `useEffect` — there is no shared fetch hook, no caching, no deduplication. Firewall, Memory, Orchestrator, and Replay each duplicate identical loading skeleton and error display patterns. The `patchDashboardConfig` function has retry logic across endpoint variants but silently continues on "unknown key" responses, which could mask real misconfiguration.

---

## Component Duplication

The most significant code quality issue is component duplication. `MetricCard` is independently defined in Savings, Firewall, Memory, Playground, and Orchestrator with near-identical markup (icon header, value, footnote). `StatusBullet` appears in Firewall, Memory, Playground, and Governance. `ToggleSwitch` is duplicated in Orchestrator and Capabilities with inline styles instead of CSS classes. This adds roughly 300 lines of redundant code and creates maintenance risk — a style change to metric cards requires editing 5 files.

---

## Visualization of Stats & Savings

The dashboard visualizes compression savings through: (1) a hero stat card showing lifetime tokens saved and USD, (2) a duration-tabbed trend chart with hourly/daily/weekly/monthly granularity, (3) savings-by-source attribution bars, (4) savings-by-model and savings-by-client breakdowns, and (5) proxy request counts and input token totals. The `savings-sources.js` module defines 11 canonical savings sources (compression, cache, semantic cache, model routing, etc.) and `period-stats.js` aggregates time-bucketed data with proper windowing logic. The trend chart is a custom CSS bar chart with Y-axis labels, grid lines, hover tooltips, and responsive height adaptation (280px → 220px → 140px). No charting library — all hand-built.

---

## Responsiveness

Three breakpoints handle desktop, tablet, and mobile well. The sidebar collapses to a fixed overlay below 1024px with a backdrop dimmer. Metric grids reflow from 4→2→1 columns. The trend chart hides its Y-axis on mobile. The search bar goes full-width on small screens. `prefers-reduced-motion` disables all transitions.

---

## Bundle & Dependencies

Runtime dependencies are minimal: React 19, React Router 7, and Lucide React (tree-shaken icons). Vite 8 with obfuscation plugin for production. No charting library, no UI framework, no CSS-in-JS. The custom CSS approach keeps the bundle lean but the tradeoff is the 2835-line stylesheet that must be loaded upfront.

---

## Summary of Findings

| Area | Status |
|------|--------|
| Design token system | Strong — thorough, consistent |
| Visual polish | High — depth, hover states, responsive chart |
| Component reuse | Poor — 5+ duplicate component definitions |
| State management | Adequate but repetitive per-page fetch patterns |
| Data accuracy | Good — proper time-windowing, multi-source aggregation |
| Responsive design | Solid across 3 breakpoints |
| Bundle size | Lean — minimal dependencies |
| CSS maintainability | Risk — single 2835-line file, empty rules, audit-fix sections |

**Top priority improvements:** Extract `MetricCard`, `StatusBullet`, `ToggleSwitch`, and `SkeletonCard` into shared components. Consolidate per-page fetch logic into a reusable hook. Break `index.css` into scoped modules or at least logical sections with clear ownership.
