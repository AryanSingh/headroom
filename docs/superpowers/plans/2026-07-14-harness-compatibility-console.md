# Harness Compatibility Console Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Show the existing server-authoritative harness compatibility contract in the Orchestration Studio without changing route selection.

**Architecture:** The React studio loads the existing authenticated `GET /v1/orchestration/harness-compatibility` endpoint together with its current configuration data. A new read-only Harnesses tab renders the manifest as cards, clearly separating harness support from model deployment availability. The routing engine and proxy transport checks remain unchanged.

**Tech Stack:** React, Playwright, FastAPI orchestration API, pytest.

## Global Constraints

- Preserve fail-closed provider/account/wire-mode checks.
- Do not initiate provider calls to display compatibility.
- Fetches use the existing `orchestrationApi` authenticated helper.
- A manifest load failure must not hide existing configuration controls.
- Use test-driven development: observe each test fail before production code.

---

### Task 1: Display server-authoritative harness compatibility

**Files:**

- Modify: `dashboard/e2e/orchestrator.spec.js`
- Modify: `dashboard/src/components/OrchestrationStudio.jsx`

**Interfaces:**

- Consumes: `GET /v1/orchestration/harness-compatibility` returning `{ manifest_version: number, harnesses: Array<{ id: string, support_level: string, routing: boolean, artifact_handoffs: boolean, hidden_session_sharing: boolean, notes: string }> }`.
- Produces: a `Harnesses` orchestration tab containing cards for every returned harness.

- [ ] **Step 1: Write the failing browser test**

Add this test to `dashboard/e2e/orchestrator.spec.js`:

```javascript
test('shows the authenticated harness contract without implying model compatibility', async ({ page }) => {
  await page.route('**/v1/orchestration/harness-compatibility*', async route => {
    await route.fulfill({
      status: 200,
      contentType: 'application/json',
      body: JSON.stringify({
        manifest_version: 1,
        harnesses: [{
          id: 'codex',
          support_level: 'native',
          routing: true,
          artifact_handoffs: true,
          hidden_session_sharing: false,
          notes: 'Use native adapter/proxy paths.',
        }],
      }),
    });
  });

  await page.goto('/orchestrator');
  await page.getByRole('tab', { name: 'Harnesses' }).click();

  await expect(page.getByRole('heading', { name: 'Harness compatibility' })).toBeVisible();
  await expect(page.getByText('Codex', { exact: true })).toBeVisible();
  await expect(page.getByText('Native', { exact: true })).toBeVisible();
  await expect(page.getByText('Routing supported', { exact: true })).toBeVisible();
  await expect(page.getByText('Model deployment availability is verified separately.', { exact: true })).toBeVisible();
});
```

- [ ] **Step 2: Run the test to verify it fails**

Run: `rtk test npm run test:e2e -- --grep "shows the authenticated harness contract"`

Expected: FAIL because no `Harnesses` tab exists.

- [ ] **Step 3: Implement the minimum UI**

In `dashboard/src/components/OrchestrationStudio.jsx`:

```javascript
const TABS = [
  // existing tabs,
  ['harnesses', 'Harnesses', Network],
];

const [harnesses, setHarnesses] = useState([]);

const [nextConfig, nextProviders, nextModels, nextExecutions, nextHarnesses] = await Promise.all([
  orchestrationApi('/config'),
  orchestrationApi('/providers'),
  orchestrationApi('/models'),
  orchestrationApi('/executions?limit=50'),
  orchestrationApi('/harness-compatibility').catch(() => ({ harnesses: [] })),
]);
setHarnesses(Array.isArray(nextHarnesses?.harnesses) ? nextHarnesses.harnesses : []);
```

Render a `tab === 'harnesses'` pane with an `h3` titled `Harness compatibility`, the exact explanatory sentence in the test, and one card per manifest item. Use `harness.id.replaceAll('_', ' ')` for a title, a support-level badge, and explicit positive/negative text for the three boolean properties. Use the existing orchestration card classes; do not add a new data model or change routing code.

- [ ] **Step 4: Run the focused test to verify it passes**

Run: `rtk test npm run test:e2e -- --grep "shows the authenticated harness contract"`

Expected: PASS.

### Task 2: Keep the control plane usable when compatibility data is unavailable

**Files:**

- Modify: `dashboard/e2e/orchestrator.spec.js`
- Modify: `dashboard/src/components/OrchestrationStudio.jsx`

**Interfaces:**

- Consumes: an optional manifest request that can fail independently.
- Produces: a non-blocking empty-state message while all existing orchestration tabs continue to load.

- [ ] **Step 1: Write the failing browser test**

```javascript
test('keeps routing controls available when the harness manifest cannot load', async ({ page }) => {
  await page.route('**/v1/orchestration/harness-compatibility*', async route => {
    await route.fulfill({ status: 503, contentType: 'application/json', body: JSON.stringify({ detail: 'unavailable' }) });
  });

  await page.goto('/orchestrator');
  await expect(page.getByRole('tab', { name: 'Routing' })).toBeVisible();
  await page.getByRole('tab', { name: 'Harnesses' }).click();
  await expect(page.getByText('Harness compatibility is unavailable.')).toBeVisible();
});
```

- [ ] **Step 2: Run the test to verify it fails**

Run: `rtk test npm run test:e2e -- --grep "keeps routing controls available"`

Expected: FAIL because an empty manifest has no explanatory state.

- [ ] **Step 3: Implement the minimum empty state**

Keep an explicit `harnessManifestAvailable` React state. Set it to `false` only when the endpoint fetch fails; render `Harness compatibility is unavailable.` only in the Harnesses pane in that state. An intentionally empty successful manifest must instead render `No harness contracts are configured.`.

- [ ] **Step 4: Run the focused test to verify it passes**

Run: `rtk test npm run test:e2e -- --grep "keeps routing controls available"`

Expected: PASS.

### Task 3: Verify regression safety and document the operator boundary

**Files:**

- Modify: `docs/content/docs/model-routing-presets.mdx`
- Verify: `tests/test_orchestration_platform.py`
- Verify: `tests/test_orchestration_api.py`
- Verify: `dashboard/e2e/orchestrator.spec.js`

**Interfaces:**

- Documents: harness compatibility is separate from target deployment eligibility.

- [ ] **Step 1: Write the documentation assertion as a review checklist**

Confirm the new documentation says: “A supported harness does not authorize cross-provider routing by itself; an enabled deployment and verified adapter compatibility are required.”

- [ ] **Step 2: Add the concise operator note**

Add a short `Harness compatibility` section to `docs/content/docs/model-routing-presets.mdx` with the sentence from Step 1 and a reference to the Orchestrator’s Harnesses and Models tabs.

- [ ] **Step 3: Run focused regression suites**

Run:

```bash
rtk pytest tests/test_orchestration_platform.py tests/test_orchestration_api.py -q
rtk test npm run test:e2e -- --grep "Orchestrator Modes|authenticated harness contract|keeps routing controls available"
```

Expected: all selected tests pass.

- [ ] **Step 4: Run quality checks**

Run:

```bash
rtk test npm run lint
rtk test npm run build
rtk git diff --check
```

Expected: every command exits 0.

- [ ] **Step 5: Commit only this feature’s files**

```bash
rtk git add dashboard/e2e/orchestrator.spec.js dashboard/src/components/OrchestrationStudio.jsx docs/content/docs/model-routing-presets.mdx
rtk git commit -m "feat: show harness routing compatibility"
```
