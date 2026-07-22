# Dashboard Metric Card Balance Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Balance narrow-screen Overview metric cards by using their right side for the icon and supporting detail.

**Architecture:** `MetricCard` gains semantic wrappers for primary and supporting content. Narrow-screen CSS makes the existing card surface a two-column grid, while a smaller-width fallback protects long values from overflow. No data transformation or navigation behavior changes.

**Tech Stack:** React 19, CSS, Node.js built-in test runner, Vite.

## Global Constraints

- Preserve the existing visual system, metric values, accessible labels, and desktop layout.
- Keep cards stacked on narrow screens; do not introduce a two-card mobile grid.
- Use CSS layout only; do not add dependencies.
- Validate at phone and desktop widths with the authenticated local dashboard.

---

### Task 1: Restructure Overview metric-card content and add responsive styling

**Files:**

- Modify: `dashboard/src/pages/Overview.jsx:994-1022`
- Modify: `dashboard/src/index.css:867-940,2829-2834`
- Test: `dashboard/tests/metric-card-layout.test.js`

**Interfaces:**

- Consumes: `MetricCard({ icon, iconColor, label, value, footnote, sparkline, sparklineColor, className })`.
- Produces: `.metric-primary` wrapping label/value/sparkline; `.metric-supporting` wrapping icon/footnote.

- [ ] **Step 1: Write the failing test**

Create `dashboard/tests/metric-card-layout.test.js`:

```js
import assert from 'node:assert/strict';
import { readFileSync } from 'node:fs';
import { resolve } from 'node:path';
import test from 'node:test';

const dashboardRoot = resolve(import.meta.dirname, '..');
const overviewSource = readFileSync(resolve(dashboardRoot, 'src/pages/Overview.jsx'), 'utf8');
const styles = readFileSync(resolve(dashboardRoot, 'src/index.css'), 'utf8');

test('MetricCard groups primary and supporting content for narrow layouts', () => {
  assert.match(overviewSource, /className="metric-primary"/);
  assert.match(overviewSource, /className="metric-supporting"/);
  assert.match(styles, /@media \(max-width: 640px\)[\s\S]*\.metric-card\s*\{[\s\S]*grid-template-columns:/);
});
```

- [ ] **Step 2: Run test to verify it fails**

Run: `cd dashboard && node --test tests/metric-card-layout.test.js`

Expected: FAIL because `MetricCard` does not yet render `.metric-primary` or `.metric-supporting`.

- [ ] **Step 3: Write minimal implementation**

Wrap label/value/sparkline in `<div className="metric-primary">` and icon/footnote in `<div className="metric-supporting">`. In the `max-width: 640px` media query, set `.metric-card` to a two-column grid (`minmax(0, 1fr) auto`), align `.metric-supporting` to the end, and add a `max-width: 360px` single-column fallback.

- [ ] **Step 4: Run test to verify it passes**

Run: `cd dashboard && node --test tests/metric-card-layout.test.js`

Expected: PASS.

- [ ] **Step 5: Commit**

Run: `git add dashboard/src/pages/Overview.jsx dashboard/src/index.css dashboard/tests/metric-card-layout.test.js && git commit -m "feat: balance dashboard metric cards on mobile"`

### Task 2: Verify dashboard behavior and build output

**Files:**

- Verify: `dashboard/tests/metric-card-layout.test.js`
- Verify: `dashboard/src/pages/Overview.jsx`
- Verify: `dashboard/src/index.css`

**Interfaces:**

- Consumes: the `MetricCard` layout from Task 1 and the authenticated local proxy at `127.0.0.1:8787`.
- Produces: evidence that the narrow-card layout is balanced, non-overflowing, and unchanged at desktop width.

- [ ] **Step 1: Run dashboard tests**

Run: `cd dashboard && npm test`

Expected: all tests pass, including `metric-card-layout.test.js`.

- [ ] **Step 2: Run production build**

Run: `cd dashboard && npm run build`

Expected: Vite completes successfully without build errors.

- [ ] **Step 3: Inspect authenticated UI at phone and desktop widths**

Open `http://127.0.0.1:5173/` with the configured local admin key. At up to 640 px, confirm each stacked card uses both sides, stays readable, and has no horizontal overflow. Above 1200 px, confirm cards retain their existing layout.

- [ ] **Step 4: Confirm repository scope**

Run: `git status --short && git log -1 --oneline`

Expected: the implementation commit is present and unrelated user changes remain unstaged.
