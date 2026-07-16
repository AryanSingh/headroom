# Dashboard Authentication Error Priority Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Ensure a dashboard authentication failure is surfaced even when another concurrent initial request fails first.

**Architecture:** Continue fetching statistics and health concurrently, switch aggregation to settled results, and select errors deterministically with authentication failures first. Make the existing Playwright authentication suite fully fixture-backed so it cannot fall through to the development proxy.

**Tech Stack:** React 19, JavaScript modules, Playwright, Node test runner, Vite, ESLint.

## Global Constraints

- Do not touch port 8787.
- Keep `/stats?cached=1` and `/health` concurrent.
- Preserve statistics-first error selection when neither request returns 401.
- Add no dependencies and make no unrelated dashboard changes.

---

### Task 1: Reproduce and fix authentication error priority

**Files:**
- Modify: `dashboard/e2e/auth.spec.js`
- Modify: `dashboard/src/lib/dashboard-context.jsx`
- Create: `dashboard/src/lib/dashboard-load-results.js`
- Test: `dashboard/e2e/auth.spec.js`

**Interfaces:**
- Consumes: two `PromiseSettledResult`-shaped objects for statistics and health requests.
- Produces: `resolveDashboardLoadResults(statsResult, healthResult)`, returning `{ statsData, healthData }` or throwing the selected request error.

- [ ] **Step 1: Write the failing Playwright regression**

In the unauthorized test, fulfill `/health` immediately with 502, delay `/stats` briefly before returning 401, and fulfill `/stats-history` with an empty JSON payload. Mock healthy `/health` and `/stats-history` responses in the remaining authentication tests.

- [ ] **Step 2: Run the regression and verify RED**

Run: `cd dashboard && npm exec playwright test e2e/auth.spec.js -- --project=chromium --workers=1`

Expected: the unauthorized case fails because the current `Promise.all` path renders `/health returned 502` instead of `authentication-surface`.

- [ ] **Step 3: Implement deterministic settled-result selection**

Create `resolveDashboardLoadResults(statsResult, healthResult)` with the following behavior:

```js
const rejected = (result) => result.status === 'rejected';

export function resolveDashboardLoadResults(statsResult, healthResult) {
  const authenticationFailure = [statsResult, healthResult].find(
    (result) => rejected(result) && Number(result.reason?.status) === 401,
  );
  if (authenticationFailure) throw authenticationFailure.reason;
  if (rejected(statsResult)) throw statsResult.reason;
  if (rejected(healthResult)) throw healthResult.reason;
  return { statsData: statsResult.value, healthData: healthResult.value };
}
```

Update `DashboardDataProvider.loadCurrent` to await `Promise.allSettled` and resolve the results through this helper before publishing state.

- [ ] **Step 4: Run focused verification and verify GREEN**

Run: `cd dashboard && npm exec playwright test e2e/auth.spec.js -- --project=chromium --workers=2`

Expected: 3 passed.

- [ ] **Step 5: Run dashboard and contract regression suites**

Run:

```bash
cd dashboard && npm test
cd dashboard && npm run lint
cd dashboard && npm run build
cd dashboard && npm exec playwright test -- --project=chromium
uv run pytest tests/test_dashboard_embedded_build.py tests/test_dashboard_audit.py tests/test_product_contracts.py tests/test_product_operator_contracts.py -q
git diff --check
```

Expected: every command passes; Chromium reports 49 passed.

- [ ] **Step 6: Commit, push, and verify GitHub Actions**

Stage the design, plan, test, helper, and context files. Commit with `fix: prioritize dashboard authentication failures`, push `main`, and monitor all workflows for the resulting SHA. If a workflow fails, inspect its failed log and continue the repair loop.
