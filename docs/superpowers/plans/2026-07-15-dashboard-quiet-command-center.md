# Dashboard Quiet Command Center Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Evolve every Cutctx dashboard route into a calm, premium operator console while preserving its API contracts, route inventory, and workflows.

**Architecture:** Add two small presentational primitives (`PageHeader` and `StatePanel`) and a coherent token/utility layer that existing route components can compose. Refine the shared app shell and progressively migrate every route to the primitives, retaining all data fetching and mutation logic. Extend the existing Playwright audit matrix with authenticated, error, and responsive visual-state coverage.

**Tech Stack:** React 19, React Router 7, Lucide React, CSS custom properties, Vite, Playwright.

## Global Constraints

- Preserve the ten existing dashboard routes and their URL paths.
- Do not change proxy APIs, response schemas, or configuration mutation semantics.
- Preserve user-owned modifications in `dashboard/src/index.css`, `dashboard/src/pages/Overview.jsx`, and `dashboard/e2e/overview.spec.js`; review overlapping hunks before editing.
- Retain keyboard navigation, skip link, search shortcut, Escape drawer behavior, and visible focus.
- Keep both dark and light themes and respect `prefers-reduced-motion`.
- Avoid horizontal viewport overflow at desktop, tablet, and phone widths.
- Use the existing teal identity as a signal color, not a default decorative fill.

---

### Task 1: Establish Shared Visual Tokens and Primitives

**Files:**
- Create: `dashboard/src/components/PageHeader.jsx`
- Create: `dashboard/src/components/StatePanel.jsx`
- Modify: `dashboard/src/index.css`
- Create: `dashboard/e2e/quiet-command-center.spec.js`

**Interfaces:**
- `PageHeader({ eyebrow, title, description, actions, status })` renders a semantic route header.
- `StatePanel({ tone, icon: Icon, title, children, action, compact })` renders `role="status"` except `tone="error"`, which renders `role="alert"`.
- Existing route components may pass React nodes to `actions` and `action` without changing data flow.

- [ ] **Step 1: Write the failing primitive and state tests**

```js
test('uses a distinct error role and an operator action', async ({ page }) => {
  await page.goto('/dashboard/replay');
  await expect(page.getByTestId('replay-empty-state')).toHaveAttribute('role', 'status');
  await page.getByLabel('Session ID').fill('missing-session');
  await page.getByRole('button', { name: 'Load replay' }).click();
  await expect(page.getByRole('alert')).toBeVisible();
});
```

- [ ] **Step 2: Run the focused test and verify it fails**

Run: `cd dashboard && npx playwright test e2e/quiet-command-center.spec.js -g "distinct error role"`
Expected: FAIL because no shared state panel or `replay-empty-state` exists.

- [ ] **Step 3: Add the primitives and token layer**

```jsx
export function PageHeader({ eyebrow, title, description, actions, status }) {
  return (
    <header className="page-header">
      <div className="page-header-copy">
        {eyebrow ? <span className="eyebrow">{eyebrow}</span> : null}
        <div className="page-header-title-row">
          <h1>{title}</h1>
          {status ? <div className="page-header-status">{status}</div> : null}
        </div>
        {description ? <p>{description}</p> : null}
      </div>
      {actions ? <div className="page-header-actions">{actions}</div> : null}
    </header>
  );
}

export function StatePanel({ tone = 'neutral', icon: Icon, title, children, action, compact = false }) {
  const role = tone === 'error' ? 'alert' : 'status';
  return (
    <div className={`state-panel state-panel-${tone}${compact ? ' state-panel-compact' : ''}`} role={role}>
      {Icon ? <div className="state-panel-icon"><Icon size={20} aria-hidden="true" /></div> : null}
      <div className="state-panel-copy">
        <strong>{title}</strong>
        {children ? <div>{children}</div> : null}
      </div>
      {action ? <div className="state-panel-action">{action}</div> : null}
    </div>
  );
}
```

Add `--surface-canvas`, `--surface-panel`, `--surface-elevated`, `--text-muted`, and state signal tokens to both themes. Add `.page-header`, `.page-header-actions`, `.state-panel`, `.state-panel-error`, `.state-panel-empty`, and focus-visible rules; build on existing tokens rather than replacing them.

- [ ] **Step 4: Run focused tests and lint**

Run: `cd dashboard && npx playwright test e2e/quiet-command-center.spec.js -g "distinct error role" && npm run lint`
Expected: PASS with no ESLint warnings.

- [ ] **Step 5: Commit the foundation**

```bash
git add dashboard/src/components/PageHeader.jsx dashboard/src/components/StatePanel.jsx dashboard/src/index.css dashboard/e2e/quiet-command-center.spec.js
git commit -m "feat(dashboard): add quiet command center primitives"
```

### Task 2: Refine the Shell and Authentication Surface

**Files:**
- Modify: `dashboard/src/App.jsx`
- Modify: `dashboard/src/index.css`
- Modify: `dashboard/e2e/auth.spec.js`
- Modify: `dashboard/e2e/ui.spec.js`

**Interfaces:**
- `AppFrame` retains its routes and `Sidebar`/`Topbar` props.
- Authentication remains triggered only when `error.includes('401')`.

- [ ] **Step 1: Add failing auth and shell assertions**

```js
await expect(page.getByTestId('authentication-surface')).toBeVisible();
await expect(page.getByRole('heading', { name: 'Connect to Cutctx' })).toBeVisible();
await expect(page.getByRole('navigation', { name: 'Main Navigation' })).toBeVisible();
```

- [ ] **Step 2: Run `auth.spec.js` and `ui.spec.js` to verify failures**

Run: `cd dashboard && npx playwright test e2e/auth.spec.js e2e/ui.spec.js`
Expected: FAIL on the new authentication-surface and heading assertions.

- [ ] **Step 3: Replace inline auth styling with the shared shell treatment**

Use `PageHeader`/`StatePanel`-compatible CSS classes in `App.jsx`; retain the API-key label, password input, saved-key behavior, and reload. Update sidebar, topbar, active navigation, collapsed sidebar, and mobile drawer styles with the new three-level surface hierarchy. Do not alter route definitions or keyboard handlers.

- [ ] **Step 4: Verify desktop and mobile shell behavior**

Run: `cd dashboard && npx playwright test e2e/auth.spec.js e2e/ui.spec.js`
Expected: PASS; authentication, navigation, theme control, and Escape drawer behavior remain covered.

- [ ] **Step 5: Commit the shell refinement**

```bash
git add dashboard/src/App.jsx dashboard/src/index.css dashboard/e2e/auth.spec.js dashboard/e2e/ui.spec.js
git commit -m "feat(dashboard): refine operator shell and auth"
```

### Task 3: Migrate Dashboard and Savings States

**Files:**
- Modify: `dashboard/src/pages/Overview.jsx`
- Modify: `dashboard/src/pages/Savings.jsx`
- Modify: `dashboard/src/index.css`
- Modify: `dashboard/e2e/overview.spec.js`

**Interfaces:**
- `Overview({ searchQuery })` and `Savings()` preserve their existing data transformations and period controls.
- Existing `.metric-card`, `.panel`, and table selectors remain available for current E2E coverage.

- [ ] **Step 1: Add failing overview and savings state assertions**

```js
await expect(page.getByTestId('overview-no-activity')).toHaveAttribute('role', 'status');
await expect(page.getByTestId('savings-no-attribution')).toContainText('Savings will appear after requests flow through Cutctx.');
```

- [ ] **Step 2: Verify failures against mocked empty data**

Run: `cd dashboard && npx playwright test e2e/overview.spec.js e2e/quiet-command-center.spec.js -g "activity|attribution"`
Expected: FAIL because the state-panel hooks and copy are not present.

- [ ] **Step 3: Apply summary/data/state panel variants**

Preserve current metric and chart calculations. Replace duplicated empty/error containers with `StatePanel`, add `PageHeader` where a page lacks route context, and use `.panel-summary`, `.panel-data`, `.panel-diagnostic`, and `.metric-card-emphasis` to clarify scan order. Reconcile all changes against the user’s existing Overview/CSS hunks instead of overwriting them.

- [ ] **Step 4: Verify populated, empty, error, and search states**

Run: `cd dashboard && npx playwright test e2e/overview.spec.js e2e/dashboard-audit.spec.js`
Expected: PASS across all overview fixtures and route audit projects.

- [ ] **Step 5: Commit the analytics pages**

```bash
git add dashboard/src/pages/Overview.jsx dashboard/src/pages/Savings.jsx dashboard/src/index.css dashboard/e2e/overview.spec.js dashboard/e2e/quiet-command-center.spec.js
git commit -m "feat(dashboard): refine savings and overview states"
```

### Task 4: Migrate Configuration, Security, and Memory Surfaces

**Files:**
- Modify: `dashboard/src/pages/Capabilities.jsx`
- Modify: `dashboard/src/pages/Governance.jsx`
- Modify: `dashboard/src/pages/Firewall.jsx`
- Modify: `dashboard/src/pages/Memory.jsx`
- Modify: `dashboard/src/index.css`
- Modify: `dashboard/e2e/capabilities.spec.js`
- Modify: `dashboard/e2e/governance.spec.js`
- Modify: `dashboard/e2e/firewall.spec.js`

**Interfaces:**
- Existing flag update handlers, entitlement checks, and scanner behavior remain unchanged.
- Configuration rows continue to expose native labels, buttons, and disabled states.

- [ ] **Step 1: Add failing state and control tests**

```js
await expect(page.getByTestId('memory-enterprise-state')).toHaveAttribute('role', 'status');
await expect(page.getByRole('button', { name: /retry/i })).toBeVisible();
await expect(page.locator('.feature-config-row').first()).toBeVisible();
```

- [ ] **Step 2: Run the focused route tests**

Run: `cd dashboard && npx playwright test e2e/capabilities.spec.js e2e/governance.spec.js e2e/firewall.spec.js`
Expected: FAIL on the new semantic-state assertions.

- [ ] **Step 3: Apply the shared visual patterns without changing behavior**

Use page headers for route context, elevated panels for live controls and scanner inputs, state panels for unavailable enterprise and no-event cases, and data-panel styles for capability/configuration rows and security tables. Keep all toggle, copy, scan, and retry callbacks intact.

- [ ] **Step 4: Verify interaction and keyboard coverage**

Run: `cd dashboard && npx playwright test e2e/capabilities.spec.js e2e/governance.spec.js e2e/firewall.spec.js e2e/dashboard-audit.spec.js`
Expected: PASS with no console errors or horizontal-overflow audit failures.

- [ ] **Step 5: Commit the operational surfaces**

```bash
git add dashboard/src/pages/Capabilities.jsx dashboard/src/pages/Governance.jsx dashboard/src/pages/Firewall.jsx dashboard/src/pages/Memory.jsx dashboard/src/index.css dashboard/e2e/capabilities.spec.js dashboard/e2e/governance.spec.js dashboard/e2e/firewall.spec.js dashboard/e2e/quiet-command-center.spec.js
git commit -m "feat(dashboard): refine operational control surfaces"
```

### Task 5: Migrate Orchestrator, Replay, and Playground Workflows

**Files:**
- Modify: `dashboard/src/pages/Orchestrator.jsx`
- Modify: `dashboard/src/components/OrchestrationStudio.jsx`
- Modify: `dashboard/src/pages/Replay.jsx`
- Modify: `dashboard/src/pages/Playground.jsx`
- Modify: `dashboard/src/index.css`
- Modify: `dashboard/e2e/orchestrator.spec.js`
- Modify: `dashboard/e2e/replay.spec.js`
- Modify: `dashboard/e2e/playground.spec.js`

**Interfaces:**
- Keep the existing routing-mode mutations, replay endpoint, and playground submission behavior.
- Replay must continue to call `GET /v1/sessions/{encodeURIComponent(sessionId)}/replay`.

- [ ] **Step 1: Add failing async-workflow state tests**

```js
await expect(page.getByTestId('replay-empty-state')).toContainText('Enter a session ID');
await expect(page.getByRole('button', { name: 'Load replay' })).toBeDisabled();
await expect(page.getByTestId('playground-result-state')).toHaveAttribute('aria-busy', 'false');
```

- [ ] **Step 2: Run workflow tests and verify failures**

Run: `cd dashboard && npx playwright test e2e/orchestrator.spec.js e2e/replay.spec.js e2e/playground.spec.js`
Expected: FAIL on new state-panel test IDs and asynchronous state semantics.

- [ ] **Step 3: Clarify workflow progression**

Use the page header and elevated input panels to distinguish setup from output. Apply state panels to unstarted, loading, error, and completed-but-empty results. Preserve button labels, disabled logic, forms, route preview evidence, tabs, and API calls; no data or config logic moves into the presentation primitives.

- [ ] **Step 4: Verify async states, tab behavior, and route audit**

Run: `cd dashboard && npx playwright test e2e/orchestrator.spec.js e2e/replay.spec.js e2e/playground.spec.js e2e/dashboard-audit.spec.js`
Expected: PASS across loading, error, and successful fixture paths.

- [ ] **Step 5: Commit workflow surfaces**

```bash
git add dashboard/src/pages/Orchestrator.jsx dashboard/src/components/OrchestrationStudio.jsx dashboard/src/pages/Replay.jsx dashboard/src/pages/Playground.jsx dashboard/src/index.css dashboard/e2e/orchestrator.spec.js dashboard/e2e/replay.spec.js dashboard/e2e/playground.spec.js dashboard/e2e/quiet-command-center.spec.js
git commit -m "feat(dashboard): refine interactive operator workflows"
```

### Task 6: Migrate Docs and Complete Visual QA

**Files:**
- Modify: `dashboard/src/pages/Docs.jsx`
- Modify: `dashboard/src/index.css`
- Modify: `dashboard/e2e/dashboard-audit.spec.js`
- Modify: `dashboard/e2e/fixtures/dashboard-audit.js`
- Modify: `dashboard/e2e/quiet-command-center.spec.js`

**Interfaces:**
- Docs anchors and existing content stay unchanged.
- `audit.assertLayoutAndAccessibility()` remains the shared no-overflow/accessibility guard.

- [ ] **Step 1: Add route-wide light-theme and narrow-viewport tests**

```js
await page.getByRole('button', { name: /Switch to light mode/i }).click();
await expect(page.locator('html')).toHaveClass(/light/);
await expect(page.locator('main')).toBeVisible();
await audit.assertLayoutAndAccessibility();
```

- [ ] **Step 2: Run audit matrix and verify the new assertions fail**

Run: `cd dashboard && npx playwright test e2e/dashboard-audit.spec.js e2e/quiet-command-center.spec.js`
Expected: FAIL until the updated docs surface and theme state assertions are supported.

- [ ] **Step 3: Finish docs and responsive token rules**

Give documentation navigation, code blocks, tables, and sections the same data-panel and page-header hierarchy. Consolidate duplicated responsive rules in `index.css`, ensuring `min-width: 0`, wrapping, and scroll containers are explicit at <=1024px and <=640px. Keep the existing reduced-motion block and expand it only for newly added transitions.

- [ ] **Step 4: Run the full dashboard verification suite**

Run: `cd dashboard && npm run lint && npm run build && npx playwright test`
Expected: lint clean, Vite build succeeds, and all E2E projects pass.

- [ ] **Step 5: Perform browser visual checks**

Use the local Vite server and inspect Dashboard, Governance, Security, Playground, Replay, and Docs at 1280px and 375px. Check dark/light themes, auth, empty/error states, navigation, focus visibility, and absence of viewport overflow. Save screenshots only under `output/playwright/` and do not commit them.

- [ ] **Step 6: Commit the completion pass**

```bash
git add dashboard/src/pages/Docs.jsx dashboard/src/index.css dashboard/e2e/dashboard-audit.spec.js dashboard/e2e/fixtures/dashboard-audit.js dashboard/e2e/quiet-command-center.spec.js
git commit -m "feat(dashboard): complete quiet command center refresh"
```

## Plan Self-Review

- Spec coverage: tasks 1-2 cover tokens, shell, auth, themes, focus, and motion; tasks 3-5 cover all operational routes and their loading/empty/error states; task 6 covers Docs, responsive behavior, and full visual verification.
- Placeholder scan: no deferred requirements or unspecified testing steps remain; every task identifies files, behavior, verification, and a commit boundary.
- Interface consistency: `PageHeader` and `StatePanel` signatures are defined in task 1 and referenced consistently by later route migrations. Route data contracts remain unchanged throughout.
