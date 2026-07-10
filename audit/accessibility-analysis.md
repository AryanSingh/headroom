# Accessibility Analysis — CutCtx Dashboard

**Date:** 2026-07-10 (re-audit)
**Previous audit:** 2026-07-08
**Scope:** Dashboard React SPA (`dashboard/src/`)
**Standard:** WCAG 2.1 AA

---

## Accessibility Rating

🟡 **Yellow** — Solid foundation with several critical gaps remaining

## WCAG AA Compliance Estimate

**62%** — Strong structural foundation, but missing skip link, shimmer animation under reduced-motion, and inconsistent focus treatment prevent full compliance.

---

## Key Strengths

- ✅ **`lang="en"` on `<html>`** — Document language is correctly declared
- ✅ **Semantic landmark structure** — `<nav aria-label="Main Navigation">`, `<aside>`, `<main>`, `<header>` are all used correctly in `App.jsx`
- ✅ **Global `:focus-visible` ring** — `index.css:216` defines a 2px solid focus outline on all focusable elements
- ✅ **Dynamic page titles** — `Topbar` component sets `document.title` per route (e.g., "Dashboard — Cutctx") via `useEffect` at `App.jsx:176`
- ✅ **`role="alert"` on error messages** — All error states use `role="alert"` for screen reader announcements (Firewall, Memory, Playground, Governance, etc.)
- ✅ **ARIA labels on icon-only buttons** — Theme toggle (`App.jsx:228`), sidebar toggle (`App.jsx:187`), copy buttons (`Governance.jsx:245`), and feature toggles (`Governance.jsx:259`) all have descriptive `aria-label`
- ✅ **`aria-hidden="true"` on decorative elements** — Sparkline SVGs (`Overview.jsx:728`), sidebar overlay (`App.jsx:100`), trend chart gridlines/axes are marked decorative
- ✅ **Form labels via `<label>` wrapping** — Playground, Replay, Firewall all use `<label className="field">` with `<span>` for visible label text
- ✅ **`aria-busy` on loading states** — Metric grids use `aria-busy={loading}` (e.g., `Firewall.jsx:84`, `Memory.jsx:65`)
- ✅ **Escape key closes mobile sidebar** — `App.jsx:298` handles Escape keydown to dismiss the sidebar drawer
- ✅ **Keyboard shortcut `/` focuses search** — `App.jsx:316` implements the `/` key shortcut for search focus
- ✅ **Responsive layout** — CSS media queries at 1200px, 1024px, and 640px breakpoints ensure content reflows without horizontal scrolling

---

## Critical Issues

### CRITICAL

| ID | WCAG Criterion | Description | File:Line |
|----|----------------|-------------|-----------|
| C-1 | 2.4.1 Bypass Blocks | **No skip-to-content link.** Keyboard users must Tab through the entire sidebar navigation (9 links + footer) on every page load before reaching main content. The previous audit flagged this and it remains unfixed. | `App.jsx` (missing) |

### HIGH

| ID | WCAG Criterion | Description | File:Line |
|----|----------------|-------------|-----------|
| H-1 | 2.3.3 Animation from Interactions | **`@keyframes shimmer` not disabled under `prefers-reduced-motion`.** The `prefers-reduced-motion: reduce` block at `index.css:2913` only sets `transition: none !important` but does NOT cancel the `animation` property on `.skeleton` elements. Users with vestibular disorders will see continuous shimmer animation. | `index.css:1359-1374`, `index.css:2913-2917` |
| H-2 | 1.4.3 Contrast (Minimum) | **`.trend-bar:focus-visible` removes outline (`outline: none`)** at `index.css:2221` while adding `box-shadow` instead. The box-shadow (`0 10px 24px rgba(20,184,166,0.2)`) is decorative and does NOT provide a visible focus indicator meeting 3:1 contrast. Keyboard users navigating the trend chart lose visible focus. | `index.css:2217-2222` |
| H-3 | 1.4.3 Contrast (Minimum) | **Light theme tertiary text contrast concern.** CSS variable `--text-tertiary` is used extensively for metric labels, footnotes, and secondary text. While the dark theme values appear adequate, the light theme values (visible in the CSS variable definitions) for tertiary text may fall below the 4.5:1 minimum for normal text on white/light backgrounds. Needs manual verification with a contrast checker. | `index.css:7` (`:root` variables) |
| H-4 | 4.1.2 Name, Role, Value | **Trend chart bars lack ARIA roles.** The trend chart (`Overview.jsx:927`) renders interactive `<button>` elements for bars but does not use `role="tab"`, `aria-selected`, or `role="slider"` with `aria-valuemin`/`aria-valuemax`/`aria-valuenow`. Screen readers cannot convey the chart's interactive purpose or current selection state. | `Overview.jsx:927-935` |

### MEDIUM

| ID | WCAG Criterion | Description | File:Line |
|----|----------------|-------------|-----------|
| M-1 | 1.3.1 Info and Relationships | **Nav card icons not consistently marked `aria-hidden`.** Sidebar nav icons (`App.jsx:124`) use Lucide `<Icon size={16} />` inside `.nav-card-icon` without `aria-hidden="true"`. While the text label follows, the icon could cause duplicate or confusing screen reader output. | `App.jsx:123-125` |
| M-2 | 1.3.1 Info and Relationships | **Metric card icons not consistently decorative.** Some metric icons (e.g., `MetricCard` in `Savings.jsx:69`) render `<Icon size={18} />` without `aria-hidden`, while others like `Sparkline` (`Overview.jsx:728`) correctly use it. Inconsistent treatment. | `Savings.jsx:68-70` |
| M-3 | 1.4.1 Use of Color | **Status dots rely on color alone.** The `.status-dot` element (`index.css:533-538`) uses only background color (green/amber) to indicate health status. While the adjacent text ("healthy"/"degraded") provides non-color context, the dot itself is purely decorative color. Consider adding an icon or pattern for colorblind users. | `index.css:533-543`, `App.jsx:197` |
| M-4 | 2.1.1 Keyboard | **Feature toggle buttons lack visible focus.** The `FeatureToggle` component (`Governance.jsx:255-263`) renders a `<button>` but the CSS for `.feature-toggle` (`index.css:2758-2800`) does not define a `:focus-visible` style. The global focus ring should apply, but the button's custom styling (border-radius, no border) may make it hard to see. | `Governance.jsx:255`, `index.css:2758` |
| M-5 | 1.4.13 Content on Hover or Focus | **Tooltip on trend bars appears on hover/focus but has no dismiss mechanism.** The `.trend-bar-tooltip` (`index.css:2224-2255`) shows on hover and focus but cannot be dismissed with Escape. Users cannot move the tooltip out of the way. | `Overview.jsx:927`, `index.css:2224` |
| M-6 | 2.4.6 Headings and Labels | **Page heading hierarchy inconsistency.** Most pages use `<h1>` for the page title (Savings, Overview) but some pages (Firewall, Memory) jump directly to `<h2>` sections without an `<h1>`. The topbar uses `<h2>` for the current page label, creating a potential heading level skip. | Multiple pages |
| M-7 | 4.1.2 Name, Role, Value | **Toggle switch components use `<label>` wrapping `<input type="checkbox">` with visually hidden input (`opacity: 0, width: 0, height: 0`).** While the `aria-label` is present, hiding the input with `width: 0; height: 0` can cause issues with some screen readers. Consider using a visible `<input>` styled with `sr-only` class instead. | `Capabilities.jsx:49-55`, `Orchestrator.jsx:27-33` |

### LOW

| ID | WCAG Criterion | Description | File:Line |
|----|----------------|-------------|-----------|
| L-1 | 2.4.4 Link Purpose | **Docs sidebar nav links have icons without `aria-hidden`.** The Docs page sidebar (`Docs.jsx:104`) renders `<Icon size={13} />` inside anchor tags. Icons are decorative since the label text follows, but should be marked `aria-hidden`. | `Docs.jsx:104` |
| L-2 | 1.4.4 Resize Text | **No explicit text resize handling.** The dashboard uses `rem` units which is good, but there's no `rem`-based root font size adjustment or user-scalable viewport meta. The viewport meta `width=device-width, initial-scale=1.0` is correct and does NOT block zoom. | `index.html:6` |
| L-3 | 3.1.2 Language of Parts | **No `lang` attribute changes for code blocks.** Code samples in Docs page contain mixed English/code which is fine, but no `lang` attribute adjustments are needed for monospace content. | `Docs.jsx` |
| L-4 | 2.4.7 Focus Visible | **Search input focus ring relies on `.search-shell:focus-within` box-shadow.** This is adequate but the `input` inside has `outline: none` (`index.css:609`). The parent container's focus ring is visible, but the input itself has no outline. This is acceptable since the parent provides the visual indicator. | `index.css:601-604`, `index.css:609` |

---

## Verification of Previous Issues (July 8 Audit)

| Previous Issue | Status | Evidence |
|----------------|--------|----------|
| **Missing skip-to-content link** | ❌ **NOT FIXED** | No skip link found in `App.jsx` or any component. No `.skip-link` class in CSS. |
| **`.trend-bar:focus-visible` removes outline** | ❌ **NOT FIXED** | `index.css:2221` still has `outline: none` on `.trend-bar:focus-visible`. Box-shadow is decorative, not a focus indicator. |
| **Generic page title** | ✅ **FIXED** | `App.jsx:177` now sets `document.title = currentNav ? \`${currentNav.label} — Cutctx\` : 'Cutctx Dashboard'` |
| **`@keyframes shimmer` not disabled under `prefers-reduced-motion`** | ❌ **NOT FIXED** | `index.css:2913` only disables `transition`, not `animation`. The `.skeleton` class at `index.css:1373` still applies `animation: shimmer 1.5s infinite ease-in-out` regardless of motion preference. |
| **No Escape key to close mobile sidebar** | ✅ **FIXED** | `App.jsx:298-305` now handles `Escape` keydown to close the sidebar on mobile. |
| **Search keyboard shortcut not implemented** | ✅ **FIXED** | `App.jsx:316` implements the `/` key to focus the search input. |

---

## Detailed Findings Table

| ID | WCAG Criterion | Severity | Description | File:Line |
|----|----------------|----------|-------------|-----------|
| C-1 | 2.4.1 Bypass Blocks | CRITICAL | No skip-to-content link | `App.jsx` (missing) |
| H-1 | 2.3.3 Animation | HIGH | Shimmer animation not disabled under prefers-reduced-motion | `index.css:1359-1374`, `index.css:2913` |
| H-2 | 1.4.3 Contrast | HIGH | Trend bar focus indicator is decorative box-shadow, not visible focus ring | `index.css:2217-2222` |
| H-3 | 1.4.3 Contrast | HIGH | Light theme tertiary text contrast may fail AA (needs manual check) | `index.css:7` (`:root` vars) |
| H-4 | 4.1.2 Name, Role, Value | HIGH | Trend chart bars lack ARIA roles for screen readers | `Overview.jsx:927-935` |
| M-1 | 1.3.1 Info and Relationships | MEDIUM | Nav card icons not marked aria-hidden | `App.jsx:123-125` |
| M-2 | 1.3.1 Info and Relationships | MEDIUM | Metric icons inconsistently decorative | `Savings.jsx:68-70` |
| M-3 | 1.4.1 Use of Color | MEDIUM | Status dots rely on color alone | `index.css:533-543` |
| M-4 | 2.1.1 Keyboard | MEDIUM | Feature toggle buttons lack visible focus style | `Governance.jsx:255`, `index.css:2758` |
| M-5 | 1.4.13 Content on Hover | MEDIUM | Trend bar tooltip has no dismiss mechanism | `Overview.jsx:927`, `index.css:2224` |
| M-6 | 2.4.6 Headings | MEDIUM | Inconsistent heading hierarchy across pages | Multiple pages |
| M-7 | 4.1.2 Name, Role, Value | MEDIUM | Toggle switch inputs hidden with width/height 0 | `Capabilities.jsx:49`, `Orchestrator.jsx:27` |
| L-1 | 2.4.4 Link Purpose | LOW | Docs sidebar icons not aria-hidden | `Docs.jsx:104` |
| L-2 | 1.4.4 Resize Text | LOW | No explicit text resize handling (rem usage is good) | Global |
| L-3 | 3.1.2 Language of Parts | LOW | No lang attribute changes for code blocks | `Docs.jsx` |
| L-4 | 2.4.7 Focus Visible | LOW | Search input outline: none (parent provides indicator) | `index.css:609` |

---

## Quick Wins (Immediate Fixes)

### 1. Add Skip-to-Content Link (5 minutes)
Add to `App.jsx`, as the first child of the outermost `<div>`:

```jsx
<a href="#main-content" className="skip-link">
  Skip to main content
</a>
```

Add to `index.css`:
```css
.skip-link {
  position: absolute;
  top: -40px;
  left: 0;
  padding: 8px 16px;
  background: var(--accent);
  color: var(--surface-0);
  font-weight: 600;
  font-size: var(--text-sm);
  z-index: 100;
  border-radius: 0 0 var(--radius-md) 0;
  text-decoration: none;
}
.skip-link:focus {
  top: 0;
}
```

Add `id="main-content"` to the `<main>` element at `App.jsx:360`:
```jsx
<main className="page-shell" id="main-content">
```

### 2. Fix Shimmer Under Reduced Motion (2 minutes)
Update the `prefers-reduced-motion` block in `index.css:2913`:

```css
@media (prefers-reduced-motion: reduce) {
  *,
  *::before,
  *::after {
    animation-duration: 0.01ms !important;
    animation-iteration-count: 1 !important;
    transition-duration: 0.01ms !important;
    scroll-behavior: auto !important;
  }
}
```

### 3. Fix Trend Bar Focus Indicator (2 minutes)
In `index.css:2217-2222`, replace the decorative box-shadow with a real focus ring:

```css
.trend-bar:focus-visible {
  opacity: 1;
  transform: translateY(-2px);
  outline: 2px solid var(--border-focus);
  outline-offset: 2px;
}
```

### 4. Add `aria-hidden` to Nav Icons (3 minutes)
In `App.jsx:124`, add `aria-hidden="true"` to the icon wrapper:
```jsx
<div className="nav-card-icon" aria-hidden="true">
  <Icon size={16} />
</div>
```

---

## Remediation Roadmap

### Phase 1: Critical & High (Target: 1-2 days)
1. **Add skip-to-content link** — C-1
2. **Fix shimmer animation under prefers-reduced-motion** — H-1
3. **Fix trend bar focus indicator** — H-2
4. **Add ARIA roles to trend chart** — H-4

### Phase 2: Medium (Target: 3-5 days)
5. **Audit light theme tertiary text contrast** — H-3
6. **Add aria-hidden to all decorative icons** — M-1, M-2
7. **Add focus-visible styles to feature toggles** — M-4
8. **Add tooltip dismiss mechanism (Escape key)** — M-5
9. **Standardize heading hierarchy** — M-6

### Phase 3: Low (Target: 1 week)
10. **Add aria-hidden to Docs sidebar icons** — L-1
11. **Review toggle switch input hiding method** — M-7

---

## Summary by Severity

| Severity | Count | Status |
|----------|-------|--------|
| CRITICAL | 1 | 0 fixed, 1 remaining |
| HIGH | 4 | 0 fixed, 4 remaining |
| MEDIUM | 7 | 0 fixed, 7 remaining |
| LOW | 4 | 0 fixed, 4 remaining |
| **Total** | **16** | **3 of 7 previous issues fixed** |

### Previous Issues Re-Check
- ✅ Generic page title — **FIXED** (dynamic per-route titles)
- ✅ Escape key for mobile sidebar — **FIXED** (keyboard handler added)
- ✅ Search keyboard shortcut — **FIXED** (`/` key implemented)
- ❌ Skip-to-content link — **NOT FIXED**
- ❌ Trend bar focus ring — **NOT FIXED**
- ❌ Shimmer animation under reduced-motion — **NOT FIXED**

---

*Generated by accessibility audit — 2026-07-10*
