# Accessibility Analysis — CutCtx Project

**Date:** 2026-07-08
**Scope:** Dashboard (React), CLI output, MkDocs documentation
**Standard:** WCAG 2.1 AA

---

## Executive Summary

The CutCtx dashboard demonstrates solid foundational accessibility work — semantic HTML, ARIA labels on interactive elements, and a global focus ring. However, several gaps prevent full WCAG AA compliance: missing skip-to-content navigation, incomplete reduced-motion handling, tertiary text contrast concerns, and inconsistent focus indicator treatment on interactive chart elements.

---

## 1. Dashboard — Semantic HTML & Structure

### HTML Entry Point (`dashboard/index.html`)

| Finding | Severity | Details |
|---------|----------|---------|
| `lang="en"` present | ✅ OK | Correctly declares document language |
| Page title is generic | **MEDIUM** | `<title>dashboard</title>` should be descriptive: "Cutctx Dashboard" or similar |
| No meta description | **LOW** | Missing `<meta name="description">` — minor for an internal tool |
| No skip-to-content link | **HIGH** | Keyboard users must tab through the entire sidebar on every page load to reach main content |

### Landmark Regions (`App.jsx`)

| Finding | Severity | Details |
|---------|----------|---------|
| `<nav>` with `aria-label="Main Navigation"` | ✅ OK | Properly labeled navigation landmark |
| `<aside>` for sidebar | ✅ OK | Correct landmark usage |
| `<main>` wrapping page content | ✅ OK | Primary content area is identifiable |
| `<h1>` for brand name | ✅ OK | Heading hierarchy starts correctly |

**Recommendation (HIGH):** Add a visually-hidden skip link as the first focusable element in the DOM:

```jsx
<a href="#main-content" className="skip-link">
  Skip to main content
</a>
```

With corresponding CSS to show it on focus:

```css
.skip-link {
  position: absolute;
  top: -40px;
  left: 0;
  padding: 8px 16px;
  background: var(--accent);
  color: var(--surface-0);
  z-index: 100;
  transition: top 0.15s ease;
}
.skip-link:focus {
  top: 0;
}
```

---

## 2. ARIA Attributes & Screen Reader Support

### Strengths

- **Error messages** use `role="alert"` — screen readers announce them immediately
- **Status messages** use `role="status"` — polite live region for non-critical updates
- **Loading states** use `aria-busy={loading}` — communicates dynamic content updates
- **Search input** has `aria-label="Search dashboard"` — clear purpose for screen readers
- **Theme toggle** has dynamic `aria-label` describing current action
- **Sidebar toggle** has `aria-label="Toggle sidebar"` — controls are labeled
- **Decorative sidebar overlay** uses `aria-hidden="true"` — correctly hidden from assistive tech

### Gaps

| Finding | Severity | Details |
|---------|----------|---------|
| Nav card icons not marked decorative | **MEDIUM** | Lucide icons inside nav links lack `aria-hidden="true"` — screen readers may announce them as unlabeled images |
| Metric icons not consistently hidden | **MEDIUM** | `.metric-icon` containers with Lucide icons should be `aria-hidden` when paired with text |
| Tab groups lack ARIA roles | **LOW** | Duration picker tabs (`.tab-group`) use divs/buttons without `role="tablist"` / `role="tab"` / `role="tabpanel"` |

**Recommendation (MEDIUM):** Add `aria-hidden="true"` to all decorative Lucide icon instances within text-bearing elements:

```jsx
<Icon size={16} aria-hidden="true" />
```

---

## 3. Keyboard Navigation

### Strengths

- All navigation links are native `<a>` elements via React Router's `<NavLink>` — inherently focusable
- Sidebar toggle and theme toggle are `<button>` elements — keyboard accessible
- Search input is a native `<input>` — receives focus normally
- `useRef` manages focus for sidebar toggle and search input programmatically

### Gaps

| Finding | Severity | Details |
|---------|----------|---------|
| No Escape key to close mobile sidebar | **MEDIUM** | Overlay click handler exists but no keyboard listener for Escape |
| No visible keyboard shortcut for search | **LOW** | `.search-shortcut` displays "⌘K" but no `onKeyDown` handler implements it |
| Trend bar charts not fully keyboard navigable | **MEDIUM** | `.trend-bar` elements are focusable but lack `role="button"` or `tabIndex` in some contexts |

**Recommendation (MEDIUM):** Add Escape key handler to close the mobile sidebar:

```jsx
useEffect(() => {
  if (!sidebarOpen || !isMobile) return;
  const handler = (e) => { if (e.key === 'Escape') setSidebarOpen(false); };
  document.addEventListener('keydown', handler);
  return () => document.removeEventListener('keydown', handler);
}, [sidebarOpen, isMobile]);
```

---

## 4. Focus Indicators

### Strengths

- **Global focus ring:** `:focus-visible` applies a2px solid teal outline with2px offset — excellent default
- **Search shell:** `.search-shell:focus-within` shows accent-colored border and 3px box-shadow ring
- **Form inputs:** `.field input:focus` gets accent border + box-shadow — consistent with search
- **Trend bar tooltips** appear on `:focus-visible` — charts are keyboard discoverable

### Gaps

| Finding | Severity | Details |
|---------|----------|---------|
| `.trend-bar:focus-visible` sets `outline: none` | **HIGH** | Removes the default focus ring without replacing it — trend bars become invisible to keyboard users |
| Search input `outline: none` | **LOW** | Relies on parent `.search-shell:focus-within` for visual feedback — acceptable but indirect |

**Recommendation (HIGH):** Restore focus visibility on trend bars. Either remove the `outline: none` override or add an equivalent visual indicator:

```css
.trend-bar:focus-visible {
  opacity: 1;
  transform: translateY(-2px);
  box-shadow: 0 10px 24px rgba(20, 184, 166, 0.2), 0 0 0 2px var(--border-focus);
  outline: none; /* Keep this only if box-shadow provides sufficient indication */
}
```

---

## 5. Color Contrast

### Dark Theme (Default)

| Element | Foreground | Background | Ratio (est.) | WCAG AA |
|---------|-----------|------------|-------------|---------|
| Primary text | `#f0f0f4` | `#0c0d12` | ~16:1 | ✅ Pass |
| Secondary text | `#a9b1c7` | `#0c0d12` | ~8:1 | ✅ Pass |
| Tertiary text | `#8b95a5` | `#0c0d12` | ~5:1 | ✅ Pass (AA large) / ⚠️ Borderline (AA normal) |
| Accent on dark | `#2dd4bf` | `#0c0d12` | ~10:1 | ✅ Pass |

### Light Theme

| Element | Foreground | Background | Ratio (est.) | WCAG AA |
|---------|-----------|------------|-------------|---------|
| Primary text | `#111318` | `#ffffff` | ~18:1 | ✅ Pass |
| Secondary text | `#5c6175` | `#ffffff` | ~5.5:1 | ✅ Pass |
| Tertiary text | `#70778c` | `#ffffff` | ~4.3:1 | ⚠️ Fail (AA normal text requires 4.5:1) |

### Concern

| Finding | Severity | Details |
|---------|----------|---------|
| Light theme tertiary text fails WCAG AA | **MEDIUM** | `#70778c` on white is ~4.3:1 — used for metric labels, eyebrow text, footnotes, and metadata at small sizes (0.6875rem–0.8125rem) |

**Recommendation (MEDIUM):** Darken the light theme tertiary color to at least `#636980` (~4.8:1) to pass AA for normal text.

---

## 6. Reduced Motion

### Current Implementation

```css
@media (prefers-reduced-motion: reduce) {
  * {
    transition: none !important;
  }
}
```

| Finding | Severity | Details |
|---------|----------|---------|
| Transitions disabled | ✅ OK | All CSS transitions are suppressed |
| Animations still run | **MEDIUM** | `@keyframes shimmer` (skeleton loading) is not disabled — it uses `animation`, not `transition` |
| No JS animation respect | **LOW** | If any JS-driven animations exist (e.g., staggered reveals), they won't be affected |

**Recommendation (MEDIUM):** Extend the reduced-motion query to also disable animations:

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

---

## 7. Color-Only Indicators

| Finding | Severity | Details |
|---------|----------|---------|
| Status dots use color alone | **MEDIUM** | `.status-dot` and `.status-dot.ok` convey status purely through background color (amber/green) — no text label or icon alternative |
| Metric trends include text | ✅ OK | `.metric-trend.up` / `.down` include arrow characters alongside color |
| Severity cards include labels | ✅ OK | `.severity-high`, `.severity-medium`, `.severity-info` have text labels |

**Recommendation (MEDIUM):** Add a visually-hidden text label or icon to status dots, or pair them with text that screen readers can announce.

---

## 8. CLI Output (`cutctx/cli/_utils/formatting.py`)

| Finding | Severity | Details |
|---------|----------|---------|
| Rich library tables are text-based | ✅ OK | Screen readers receive structured text output |
| Error/success/warning prefixed with text labels | ✅ OK | `[bold red]Error:[/bold red]` means the word "Error" appears regardless of color |
| No `NO_COLOR` env var support | **LOW** | Rich Console doesn't set `no_color=True` when `NO_COLOR` is set — users with color vision deficiencies cannot disable colors |

**Recommendation (LOW):** Initialize the shared Console with color detection:

```python
import os
console = Console(no_color=os.environ.get("NO_COLOR") is not None)
```

---

## 9. MkDocs Documentation

| Finding | Severity | Details |
|---------|----------|---------|
| Material theme is generally accessible | ✅ OK | Includes semantic HTML, ARIA landmarks, keyboard-navigable search |
| TOC with permalinks | ✅ OK | Anchor links allow deep linking and screen reader navigation |
| Light/dark toggle via `prefers-color-scheme` | ✅ OK | Respects system preference with manual override |
| No accessibility-specific plugins | **LOW** | No `mkdocs-a11y` or similar plugin configured |
| Empty `docs/overrides/` directory | **LOW** | No custom templates to review — relies entirely on Material defaults |

---

## Summary by Severity

### HIGH (3 findings)

1. **Missing skip-to-content link** — keyboard users must tab through the full sidebar on every page
2. **`.trend-bar:focus-visible` removes outline** — interactive chart elements lose keyboard visibility
3. **Generic page title** — `<title>dashboard</title>` provides no context for screen reader users or browser tabs

### MEDIUM (7 findings)

4. Light theme tertiary text (`#70778c`) fails WCAG AA contrast for normal text
5. Nav card icons not marked `aria-hidden="true"`
6. Metric icons not consistently marked decorative
7. No Escape key to close mobile sidebar
8. `@keyframes shimmer` animation not disabled under `prefers-reduced-motion`
9. Status dots rely on color alone
10. Trend bar charts lack full ARIA tab roles

### LOW (5 findings)

11. No meta description in HTML entry point
12. Search keyboard shortcut not implemented
13. CLI missing `NO_COLOR` support
14. No accessibility plugins in MkDocs config
15. No JS animation respect in reduced-motion query

---

## Overall Rating

**Partial WCAG AA compliance.** The dashboard has strong bones — semantic landmarks, ARIA labels, focus management, and a solid color system. The three HIGH findings (skip link, focus ring removal, page title) are straightforward fixes that would significantly improve the experience for keyboard and screen reader users. The contrast and reduced-motion gaps are systematic but addressable with targeted CSS changes.
