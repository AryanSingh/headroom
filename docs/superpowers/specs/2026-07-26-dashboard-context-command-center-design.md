# Context Command Center — Dashboard Visual Identity Design

**Date:** 2026-07-26  
**Branch:** `feat/dashboard-visual-identity` (from `main`)  
**Approach:** Hybrid Context Command Center (Helicone clarity + Portkey control-plane confidence + Langfuse state trust)  
**Decision authority:** User selected approach 3 and authorized best-judgment completion without further section gates.

## 1. Goal

Make every Cutctx operator dashboard surface best-in-class versus Helicone, Langfuse, Portkey, and LiteLLM by shipping a **new visual identity** plus consistent hierarchy, empty/loading/error states, and responsive shell behavior — while preserving existing routes, APIs, and verified functional behavior.

Success looks like:

1. A stranger can tell this is Cutctx (savings/evidence control plane), not a generic AI admin template.
2. Overview and Savings read as a command center in under 5 seconds.
3. Orchestrator / Governance / Security feel safe and deliberate (draft/live, labeled states).
4. Shared chrome, tokens, typography, panels, and states are identical across all 10 surfaces.
5. Mobile reflow works (sidebar drawer); WCAG 2.1 AA contrast and keyboard paths hold in dark and light.
6. Playwright + unit token tests pin the contracts; `audit/ui-review-report.md` records screenshot evidence.

## 2. Non-goals

- No new backend APIs or routing semantics.
- No drag-and-drop custom dashboards (Langfuse feature) in this pass.
- No product rename or marketing site work.
- No wholesale rewrite of Overview business logic — restyle and restructure reading order only where hierarchy requires it.

## 3. Competitive inspiration (steal patterns, not chrome)

| Source | Pattern we adopt |
|---|---|
| Helicone | Calm request/cost tape; low chrome; scannable tables |
| Langfuse | Home hierarchy; honest empty/loading; panels earn space |
| Portkey | Control-plane draft/live confidence; policy grouping |
| LiteLLM | Ops clarity for routing/spend labels |

Cutctx wedge expressed visually: **prove reversible context and savings decisions**.

## 4. Visual identity

### Tone

**Precision observatory** — industrial-refined, evidence-first, quiet confidence. Dense where operators need density; airy where decisions need calm.

### Typography

| Role | Family | Usage |
|---|---|---|
| Display | **Sora** (Google Fonts) | Page titles, hero metrics |
| Body | **IBM Plex Sans** | UI copy, tables, forms |
| Mono | **IBM Plex Mono** | IDs, traces, JSON, CLI |

Forbidden as primary stacks: Inter, Roboto, Arial, system-ui as hero, Space Grotesk, purple-gradient tropes.

Load via `index.html` Google Fonts preconnect + stylesheet. Fallbacks only after the chosen families.

### Color

Dark-first graphite canvas with cool temperature depth (no neon glow).

| Token | Dark | Light | Role |
|---|---|---|---|
| `--surface-0` | `#090A0E` | `#F7F8FA` | Canvas |
| `--surface-1` | `#0F1117` | `#FFFFFF` | Panel |
| `--surface-2` | `#161922` | `#EEF1F6` | Elevated |
| `--accent` | `#1FCBAA` | `#0F766E` | Savings/proof signal |
| `--text-primary` | `#E8EAF0` | `#12141A` | Primary text |
| `--text-secondary` | `#9AA3B5` | `#3A4254` | Secondary |
| Semantic red/amber/green/blue | Keep distinct from accent | Same | States |

No multi-layer glow shadows. Max one soft shadow + border for elevation.

### Shape & chrome

- Radius: sm 4 / md 8 / lg 12 (tighten; avoid pill chrome except true toggles).
- Panels by default; card chrome only for interactive containers.
- Sidebar 240px expanded / 64px collapsed; mobile drawer with overlay + Escape.

### Motion

Three intentional motions only:

1. Sidebar/drawer open-close (~180ms)
2. Panel fade/slide-in on route (~160ms, staggered ≤3 children)
3. Live health pulse on status dot (opacity only)

Honor `prefers-reduced-motion: reduce`.

## 5. Information architecture (per surface)

### Shell

- Nav labels unchanged; icons remain Lucide.
- Topbar: title + optional subtitle + health pill (text + color) + theme + search.
- Auth gate uses same tokens/fonts as app.

### Overview (command center)

Reading order:

1. Period + health strip
2. Primary savings hero (one composition, not four equal cards)
3. Supporting metrics row
4. Trend + recent requests (Helicone-style tape)
5. Attribution / quick links

### Savings

Period controls first; created vs observed clarity; source/model breakdowns as panels with empty states that explain next action.

### Orchestrator / Governance / Security

Portkey-style grouping: clear section headers, draft vs live labeling where applicable, form help text for risky controls, consistent `StatePanel` for loading/error/empty.

### Memory / Replay / Playground / Docs / Capabilities

Same shell, page header, panel language, empty/loading patterns. No one-off visual dialects.

## 6. Shared components contract

| Component | Contract |
|---|---|
| `PageHeader` | Title (display font), optional description, optional actions slot |
| `StatePanel` | tone: empty \| info \| success \| warning \| error; icon + title + children; `role="status"` or `alert` for error |
| Metric panel | `.metric-panel` (rename gradually from `.metric-card` via dual class if needed for tests) |
| Skeleton | Existing skeleton classes restyled to new surfaces |
| Trace drawer | Same identity; focus trap preserved |

## 7. Accessibility

- WCAG 2.1 AA contrast for text and non-text UI (1.4.3, 1.4.11)
- Reflow at 320–390px without horizontal content loss (1.4.10)
- Visible focus rings using `--border-focus`
- Status never color-only (1.4.1)
- Tabs: `aria-controls` + arrow-key pattern where tablists exist (Orchestrator)

## 8. Testing strategy (TDD)

1. **Unit (node:test):** CSS token contracts — required font families, accent, surface tokens, reduced-motion block, forbidden Inter as `--font-body`.
2. **Playwright:** shell identity classes, page headers, empty states, mobile drawer, theme toggle persistence, nav surfaces.
3. **Visual evidence:** screenshots under `audit/screenshots/` for ui-review-report.
4. Iron law: failing test first for each new contract before CSS/JSX changes.

## 9. Phased delivery

1. Tokens + fonts + shell chrome  
2. Shared panels / states / headers  
3. Overview + Savings  
4. Orchestrator + Governance + Security  
5. Remaining surfaces + audit report  

## 10. Risks

| Risk | Mitigation |
|---|---|
| Overview.jsx size (~115KB) | Prefer CSS + header/wrapper changes; surgical JSX only |
| Existing e2e class selectors | Dual-class during rename; update tests in same task |
| Font FOUT | `font-display: swap` + preconnect |
| Light theme regression | Explicit light token set + theme e2e |

## 11. Out-of-scope follow-ups

Customizable home widgets, new analytics charts library, marketing brand sync.
