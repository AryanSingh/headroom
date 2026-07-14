import { test, expect } from '@playwright/test';

test.describe('Orchestrator Modes', () => {
  test.beforeEach(async ({ page }) => {
    await page.addInitScript(() => {
      window.localStorage.setItem('cutctxAdminKey', 'testkey');
    });
    
    await page.route('**/health', async route => {
      await route.fulfill({
        status: 200,
        contentType: 'application/json',
        body: JSON.stringify({ status: 'healthy', ready: true }),
      });
    });

    await page.route('**/stats?*', async route => {
      await route.fulfill({
        status: 200,
        contentType: 'application/json',
        body: JSON.stringify({
          config: { orchestrator: false },
          model_routing: {
            mode: 'off',
            requested: false,
            available: true,
            configured_routes: 0,
            preset: null,
          },
        }),
      });
    });

    await page.route('**/v1/orchestration/routing/evidence*', async route => {
      await route.fulfill({
        status: 200,
        contentType: 'application/json',
        body: JSON.stringify({
          schema_version: 1,
          status: 'collecting',
          samples: 7,
          sample_progress: { observed: 7, required: 20, fraction: 0.35 },
          constraints: {
            minimum_samples: 20,
            minimum_mean_quality: 0.9,
            maximum_unsafe_rate: 0.01,
            quality_floor: 0.8,
          },
          recommendation: null,
          frontier: [],
          segmented: { minimum_segment_samples: 20, dimensions: {} },
          shadow: { enabled: true, sample_rate: 0.1 },
          scorer: { status: 'promoted', configured: true, training_samples: 200, minimum_confidence: 0.91 },
        }),
      });
    });
  });

  test('selecting a routing mode posts orchestrator_mode', async ({ page }) => {
    const postUrls = [];
    const postedBodies = [];
    await page.route('**/config/flags*', async route => {
      if (route.request().method() === 'POST') {
        postUrls.push(new URL(route.request().url()).pathname);
        postedBodies.push(route.request().postDataJSON());
        await route.fulfill({
          status: 200,
          contentType: 'application/json',
          body: JSON.stringify({ applied_live: { orchestrator_mode: { mode: 'balanced' } } }),
        });
        return;
      }
      await route.fulfill({ status: 200, contentType: 'application/json', body: JSON.stringify({}) });
    });

    await page.goto('/orchestrator');
    
    await expect(page.locator('h2').filter({ hasText: 'Routing mode control' })).toBeVisible();
    await expect(page.getByRole('button', { name: 'Off' })).toBeVisible();
    await expect(page.getByRole('button', { name: 'Balanced' })).toBeVisible();
    await expect(page.getByRole('button', { name: 'Aggressive' })).toBeVisible();
    await expect(page.getByText('Routing evidence', { exact: true })).toBeVisible();
    await expect(page.getByText('Collecting evidence', { exact: true })).toBeVisible();
    await expect(page.getByText('7 / 20 samples', { exact: true })).toBeVisible();
    await expect(page.getByText('Promoted calibrated scorer', { exact: true })).toBeVisible();
    await expect(page.getByText('200 training samples · minimum confidence 0.91', { exact: true })).toBeVisible();

    await page.getByRole('button', { name: 'Balanced' }).click();

    await expect.poll(() => postUrls.length).toBe(1);
    await expect(postUrls).toEqual(['/config/flags']);
    await expect(postedBodies[0]).toMatchObject({ orchestrator_mode: 'balanced' });
  });

  test('shows the authenticated harness contract without implying model compatibility', async ({ page }) => {
    await page.route('**/v1/orchestration/config*', async route => {
      await route.fulfill({ status: 200, contentType: 'application/json', body: JSON.stringify({ roles: [], bindings: [], settings: {} }) });
    });
    await page.route('**/v1/orchestration/providers*', async route => {
      await route.fulfill({ status: 200, contentType: 'application/json', body: JSON.stringify({ catalog: [], accounts: [] }) });
    });
    await page.route('**/v1/orchestration/models*', async route => {
      await route.fulfill({ status: 200, contentType: 'application/json', body: JSON.stringify({ models: [] }) });
    });
    await page.route('**/v1/orchestration/executions*', async route => {
      await route.fulfill({ status: 200, contentType: 'application/json', body: JSON.stringify({ executions: [] }) });
    });
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

  test('keeps routing controls available when the harness manifest cannot load', async ({ page }) => {
    await page.route('**/v1/orchestration/config*', async route => {
      await route.fulfill({ status: 200, contentType: 'application/json', body: JSON.stringify({ roles: [], bindings: [], settings: {} }) });
    });
    await page.route('**/v1/orchestration/providers*', async route => {
      await route.fulfill({ status: 200, contentType: 'application/json', body: JSON.stringify({ catalog: [], accounts: [] }) });
    });
    await page.route('**/v1/orchestration/models*', async route => {
      await route.fulfill({ status: 200, contentType: 'application/json', body: JSON.stringify({ models: [] }) });
    });
    await page.route('**/v1/orchestration/executions*', async route => {
      await route.fulfill({ status: 200, contentType: 'application/json', body: JSON.stringify({ executions: [] }) });
    });
    await page.route('**/v1/orchestration/harness-compatibility*', async route => {
      await route.fulfill({ status: 503, contentType: 'application/json', body: JSON.stringify({ detail: 'unavailable' }) });
    });

    await page.goto('/orchestrator');
    await expect(page.getByRole('tab', { name: 'Routing' })).toBeVisible();
    await page.getByRole('tab', { name: 'Harnesses' }).click();
    await expect(page.getByText('Harness compatibility is unavailable.')).toBeVisible();
  });

  test('shows route eligibility evidence in the deterministic preview', async ({ page }) => {
    await page.route('**/v1/orchestration/config*', async route => {
      await route.fulfill({
        status: 200,
        contentType: 'application/json',
        body: JSON.stringify({
          roles: [{ id: 'worker', name: 'Worker' }],
          bindings: [{ id: 'worker', role: 'worker', model: 'openai:account-a:shared' }],
          settings: { mode: 'strict', policy: 'role_locked', retries: 1, timeout_seconds: 120 },
        }),
      });
    });
    await page.route('**/v1/orchestration/providers*', async route => {
      await route.fulfill({ status: 200, contentType: 'application/json', body: JSON.stringify({ catalog: [], accounts: [] }) });
    });
    await page.route('**/v1/orchestration/models*', async route => {
      await route.fulfill({ status: 200, contentType: 'application/json', body: JSON.stringify({ models: [] }) });
    });
    await page.route('**/v1/orchestration/executions*', async route => {
      await route.fulfill({ status: 200, contentType: 'application/json', body: JSON.stringify({ executions: [] }) });
    });
    await page.route('**/v1/orchestration/harness-compatibility*', async route => {
      await route.fulfill({ status: 200, contentType: 'application/json', body: JSON.stringify({ harnesses: [] }) });
    });
    await page.route('**/v1/orchestration/route*', async route => {
      await route.fulfill({
        status: 200,
        contentType: 'application/json',
        body: JSON.stringify({
          provider: 'openai',
          actual_model: 'shared',
          reason: 'equivalent_deployment_selected',
          fallback_used: false,
          required_capabilities: ['tool_calling'],
          policy_constraints: { allowed_providers: ['openai'], allowed_regions: [], allowed_data_classifications: [] },
          selection_evidence: {
            scores: [{ deployment: 'openai:account-b:shared', score: 0.94 }],
            rejected: [{ model: 'openai:account-a:shared', reason: 'cooling_down' }],
          },
        }),
      });
    });

    await page.goto('/orchestrator');
    await page.getByRole('tab', { name: 'Routing' }).click();
    await page.locator('.route-preview select').selectOption('worker');
    await page.getByRole('button', { name: 'Preview' }).click();

    await expect(page.getByText('Candidate scores', { exact: true })).toBeVisible();
    await expect(page.getByText('openai:account-b:shared', { exact: true })).toBeVisible();
    await expect(page.getByText('Score 0.94', { exact: true })).toBeVisible();
    await expect(page.getByText('Rejected candidates', { exact: true })).toBeVisible();
    await expect(page.getByText('cooling_down', { exact: true })).toBeVisible();
    await expect(page.getByText('Required capabilities', { exact: true })).toBeVisible();
    await expect(page.getByText('tool_calling', { exact: true })).toBeVisible();
    await expect(page.getByText('Provider policy: openai', { exact: true })).toBeVisible();
  });

  test('exposes deployment cooldown beside retries and timeout', async ({ page }) => {
    await page.route('**/v1/orchestration/config*', async route => {
      await route.fulfill({
        status: 200,
        contentType: 'application/json',
        body: JSON.stringify({
          roles: [],
          bindings: [],
          settings: { mode: 'strict', policy: 'role_locked', retries: 1, timeout_seconds: 120, deployment_cooldown_seconds: 45 },
        }),
      });
    });
    await page.route('**/v1/orchestration/providers*', async route => {
      await route.fulfill({ status: 200, contentType: 'application/json', body: JSON.stringify({ catalog: [], accounts: [] }) });
    });
    await page.route('**/v1/orchestration/models*', async route => {
      await route.fulfill({ status: 200, contentType: 'application/json', body: JSON.stringify({ models: [] }) });
    });
    await page.route('**/v1/orchestration/executions*', async route => {
      await route.fulfill({ status: 200, contentType: 'application/json', body: JSON.stringify({ executions: [] }) });
    });
    await page.route('**/v1/orchestration/harness-compatibility*', async route => {
      await route.fulfill({ status: 200, contentType: 'application/json', body: JSON.stringify({ harnesses: [] }) });
    });

    await page.goto('/orchestrator');
    await page.getByRole('tab', { name: 'Routing' }).click();

    await expect(page.getByLabel('Deployment cooldown (seconds)')).toHaveValue('45');
  });

  test('shows weighted equivalent allocation evidence in the route preview', async ({ page }) => {
    await page.route('**/v1/orchestration/config*', async route => {
      await route.fulfill({ status: 200, contentType: 'application/json', body: JSON.stringify({ roles: [{ id: 'worker', name: 'Worker' }], bindings: [], settings: {} }) });
    });
    await page.route('**/v1/orchestration/providers*', async route => {
      await route.fulfill({ status: 200, contentType: 'application/json', body: JSON.stringify({ catalog: [], accounts: [] }) });
    });
    await page.route('**/v1/orchestration/models*', async route => {
      await route.fulfill({ status: 200, contentType: 'application/json', body: JSON.stringify({ models: [] }) });
    });
    await page.route('**/v1/orchestration/executions*', async route => {
      await route.fulfill({ status: 200, contentType: 'application/json', body: JSON.stringify({ executions: [] }) });
    });
    await page.route('**/v1/orchestration/harness-compatibility*', async route => {
      await route.fulfill({ status: 200, contentType: 'application/json', body: JSON.stringify({ harnesses: [] }) });
    });
    await page.route('**/v1/orchestration/route*', async route => {
      await route.fulfill({
        status: 200,
        contentType: 'application/json',
        body: JSON.stringify({
          provider: 'openai', actual_model: 'shared', reason: 'equivalent_deployment_selected', fallback_used: false,
          selection_evidence: {
            strategy: 'equivalent_weighted',
            cohort_fraction: 0.42,
            eligible_weights: [{ deployment: 'openai:account-b:shared', weight: 0.25 }],
            rejected: [],
          },
        }),
      });
    });

    await page.goto('/orchestrator');
    await page.getByRole('tab', { name: 'Routing' }).click();
    await page.locator('.route-preview select').selectOption('worker');
    await page.getByRole('button', { name: 'Preview' }).click();

    await expect(page.getByText('Weighted allocation', { exact: true })).toBeVisible();
    await expect(page.getByText('Cohort 0.42', { exact: true })).toBeVisible();
    await expect(page.getByText('Weight 0.25', { exact: true })).toBeVisible();
  });
});
