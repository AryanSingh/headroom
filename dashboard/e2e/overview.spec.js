import { test, expect } from '@playwright/test';

test.describe('Overview Metrics & Panels', () => {
  test.beforeEach(async ({ page }) => {
    // Authenticate user
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
  });

  test('successfully loads and displays mocked stats data', async ({ page }) => {
    // Mock successful response with realistic dummy data
    await page.route('**/stats?*', async route => {
      await route.fulfill({
        status: 200,
        contentType: 'application/json',
        body: JSON.stringify({
          summary: { cost: { without_cutctx_usd: 1.50, with_cutctx_usd: 0.25, total_saved_usd: 1.25 } },
          tokens: { saved: 5000, savings_usd: 1.25, savings_percent: 12.5 },
          requests: { total: 125, failed: 2, cached: 15 },
          persistent_savings: {
            lifetime: {
              requests: 125,
              tokens_saved: 5000,
              total_input_tokens: 40000,
              total_savings_usd: 1.25,
            },
            display_session: {
              requests: 20,
              tokens_saved: 800,
              total_input_tokens: 6000,
              total_savings_usd: 0.2,
            },
          },
          router: {
            route_counts: {
              user_msg: 100,
              small: 20,
              content_blocks: 5
            }
          }
        }),
      });
    });

    await page.goto('/dashboard');

    // Wait for data to load
    await expect(page.locator('.topbar-title-row h2')).toHaveText('Dashboard');

    // Check Tokens Saved card
    await expect(page.locator('.metric-card').filter({ hasText: 'Tokens saved' }).locator('.metric-value')).toHaveText('5.0k');
    
    // Check Requests card
    await expect(page.locator('.metric-card').filter({ hasText: 'Requests' }).locator('.metric-value')).toHaveText('125');
    
    // Check Money Saved card
    await expect(page.locator('.metric-card').filter({ hasText: 'Money saved' }).locator('.metric-value')).toHaveText('$1.250');

    // Check RouterDiagnosticsPanel renders
    const diagnosticsPanel = page.locator('.panel').filter({ hasText: 'Bypassed Messages' });
    await expect(diagnosticsPanel).toBeVisible();
    await expect(diagnosticsPanel.getByText('small: 20')).toBeVisible();
    await expect(diagnosticsPanel.getByText('content_blocks: 5')).toBeVisible();
  });

  test('overview search filters summary panels as well as requests', async ({ page }) => {
    await page.route('**/stats?*', async route => {
      await route.fulfill({
        status: 200,
        contentType: 'application/json',
        body: JSON.stringify({
          summary: { cost: { without_cutctx_usd: 8.0, with_cutctx_usd: 2.0, total_saved_usd: 6.0 } },
          tokens: {
            saved: 3000,
            savings_usd: 6.0,
            savings_percent: 30,
            total_before_compression: 10000,
          },
          requests: { total: 40, failed: 1, cached: 7 },
          prefix_cache: {
            diagnostics: {
              findings: [
                {
                  code: 'cache-reuse-low',
                  title: 'Cache reuse is low',
                  detail: 'Prompt cache could save more.',
                  recommendation: 'Repeat a request.',
                  severity: 'info',
                },
              ],
              by_provider: [
                {
                  provider: 'anthropic',
                  status: 'degraded',
                  reason: 'cache busts',
                  requests: 10,
                  hit_rate: 10,
                  bust_count: 2,
                },
              ],
            },
          },
          knowledge_graph: {
            status: 'ready',
            requested: true,
            available: true,
            active: true,
            interceptor_registered: true,
            version: '1.2.3',
            node_count: 12,
            edge_count: 18,
          },
          feature_availability: {
            model_routing: { available: true, reason: 'enabled' },
            audio: { available: true, compression: 'pass-through', reason: 'pass-through' },
          },
          intelligence: {
            autopilot: {
              enabled: true,
              min_level: 1,
              max_level: 5,
              hysteresis_window: 10,
              task_levels: {
                summarize: 4,
              },
              task_stats: {
                summarize: {
                  signal_count: 3,
                  adjustment_count: 1,
                },
              },
              recent_levels: [4, 4, 5],
              recent_adjustments: [
                {
                  task_type: 'summarize',
                  old_level: 3,
                  new_level: 4,
                  signal_kind: 'quality_drop',
                },
              ],
            },
            policies: {
              enabled: true,
              count: 2,
              total_samples: 9,
              by_aggressiveness: {
                aggressive: 2,
              },
              by_algorithm_hint: {
                gpt_54_mini_high: 4,
              },
            },
          },
          recent_requests: [
            {
              request_id: 'req-1',
              timestamp: '2026-07-02T04:30:00Z',
              model: 'gpt-5.4',
              input_tokens_original: 206658,
              total_saved_tokens: 205112,
              tokens_saved: 952,
              cache_saved_tokens: 204160,
            },
          ],
          persistent_savings: {
            lifetime: { requests: 40, tokens_saved: 3000, total_input_tokens: 10000, total_savings_usd: 6.0 },
            display_session: { requests: 10, tokens_saved: 1000, total_input_tokens: 3000, total_savings_usd: 1.2 },
          },
        }),
      });
    });

    await page.goto('/dashboard');
    const search = page.locator('input[aria-label="Search"]');
    await expect(search).toBeVisible();
    await search.fill('autopilot');

    await expect(page.getByText('Compression autopilot', { exact: true })).toBeVisible();
    await expect(page.getByText('Savings by client', { exact: true })).toHaveCount(0);
    await expect(page.getByText('Feature availability', { exact: true })).toHaveCount(0);
    await expect(page.getByText('Knowledge graph status', { exact: true })).toHaveCount(0);
    await expect(page.getByText('Learned policies', { exact: true })).toHaveCount(0);
  });

  test('gracefully handles 500 Internal Server Error', async ({ page }) => {
    // Mock 500 error
    await page.route('**/stats?*', async route => {
      await route.fulfill({
        status: 500,
        contentType: 'application/json',
        body: JSON.stringify({ detail: "Internal Server Error" }),
      });
    });

    await page.goto('/dashboard');

    // Wait for the red error banner
    const errorBanner = page.locator('.alert-card');
    await expect(errorBanner).toBeVisible();
    await expect(errorBanner).toContainText('Failed to load data: /stats?cached=1 returned 500');

    // Stats should be 0 or empty
    await expect(page.locator('.metric-card').filter({ hasText: 'Tokens saved' }).locator('.metric-value')).toHaveText('0');
  });

  test('renders activity and attribution empty states', async ({ page }) => {
    await page.route('**/stats?*', async route => {
      await route.fulfill({
        status: 200,
        contentType: 'application/json',
        body: JSON.stringify({
          summary: { saved: 0, input: 0, savings_percent: 0 },
          tokens: { saved: 0, input: 0, total_before_compression: 0, savings_percent: 0 },
          requests: { total: 0, failed: 0, cached: 0 },
          recent_requests: [],
          persistent_savings: { lifetime: {}, display_session: {} },
        }),
      });
    });

    await page.goto('/dashboard');
    await expect.soft(page.getByTestId('overview-no-activity')).toHaveAttribute('role', 'status');

    await page.goto('/dashboard/savings');
    await expect.soft(page.getByTestId('savings-no-attribution')).toContainText(
      'Savings will appear after requests flow through Cutctx.',
    );
  });

  test('prefers live session savings over lifetime rollups and keeps attribution USD consistent', async ({ page }) => {
    await page.route('**/stats-history*', async route => {
      await route.fulfill({
        status: 200,
        contentType: 'application/json',
        body: JSON.stringify({ series: { hourly: [] } }),
      });
    });

    await page.route('**/stats?*', async route => {
      await route.fulfill({
        status: 200,
        contentType: 'application/json',
        body: JSON.stringify({
          summary: {
            saved: 58617,
            input: 6812017,
            savings_percent: 0.86,
          },
          tokens: {
            saved: 58617,
            input: 6812017,
            total_before_compression: 6812017,
            proxy_compression_saved: 58617,
            active_savings_percent: 0.86,
            proxy_savings_percent: 0.86,
            savings_percent: 0.86,
          },
          requests: {
            total: 136,
            by_model: {
              'gpt-4o-mini': 97,
              'gpt-5.4-mini': 2,
              'gpt-5.4': 36,
              'passthrough:models': 1,
            },
          },
          cost: {
            total_tokens_saved: 58617,
            total_input_tokens: 6832224,
            total_input_cost_usd: 3.7059,
            savings_usd: 0.1387,
            compression_savings_usd: 0.1387,
            cache_savings_usd: 0.4762,
              savings_by_source: {
                tokens: {
                  semantic_cache: 4080,
                  cutctx_compression: 3206,
                  provider_prompt_cache: 6349824,
                  normalization: 4080,
                  batch_routing: 2000,
                  memoization: 1500,
                  output_optimization: 900,
                },
                usd: {
                  normalization: 1.0,
                  batch_routing: 2.0,
                  memoization: 3.0,
                  output_optimization: 4.0,
                },
                total_tokens: 6365590,
              },
            savings_by_client: {
              codex: {
                tokens: {
                  cutctx_compression: 3206,
                  provider_prompt_cache: 6349824,
                },
                usd: {},
                total_tokens: 6353030,
                total_usd: 0,
              },
            },
            per_model: {
              'gpt-4o-mini': {
                requests: 176,
                tokens_saved: 0,
                savings_usd: 0,
              },
              'gpt-5.4': {
                requests: 36,
                tokens_saved: 54109,
                savings_usd: 0.1353,
              },
              'gpt-5.4-mini': {
                requests: 2,
                tokens_saved: 4508,
                savings_usd: 0.0034,
              },
              'passthrough:models': {
                requests: 1,
                tokens_saved: 0,
                savings_usd: 0,
              },
            },
          },
          prefix_cache: {
            totals: {
              cache_read_tokens: 6349824,
              net_savings_usd: 0.4762,
            },
          },
          recent_requests: [
            {
              request_id: 'req-1',
              timestamp: '2026-07-02T04:30:00Z',
              model: 'gpt-5.4',
              input_tokens_original: 206658,
              total_saved_tokens: 205112,
              tokens_saved: 952,
              cache_saved_tokens: 204160,
            },
          ],
          persistent_savings: {
              lifetime: {
                requests: 19910,
                tokens_saved: 264746130,
                compression_savings_usd: 631.743039,
                normalization_savings_usd: 1.0,
                batch_routing_savings_usd: 2.0,
                memoization_savings_usd: 3.0,
                output_optimization_savings_usd: 4.0,
                total_input_tokens: 757435929,
              },
            display_session: {
              requests: 178,
              tokens_saved: 1425064,
              compression_savings_usd: 4.234312,
              total_input_tokens: 8046754,
              savings_percent: 15.05,
            },
          },
        }),
      });
    });

    await page.goto('/dashboard');

    await expect(page.locator('.metric-card').filter({ hasText: 'Tokens saved' }).locator('.metric-value')).toHaveText('264.7M');
    await expect(page.locator('.metric-card').filter({ hasText: 'Requests' }).locator('.metric-value')).toHaveText('19,910');
    await expect(page.locator('.metric-card').filter({ hasText: 'Money saved' }).locator('.metric-value')).toHaveText('$641.74');

    const sourcePanel = page.locator('.panel').filter({ hasText: 'Where savings come from' });
  await expect(sourcePanel.getByText('Direct compression', { exact: true })).toBeVisible();
  await expect(sourcePanel.getByText('Provider prompt cache', { exact: true })).toBeVisible();
  await expect(sourcePanel.getByText('Tokenizer normalization', { exact: true })).toBeVisible();
  await expect(sourcePanel.getByText('Batch routing', { exact: true })).toBeVisible();
  await expect(sourcePanel.getByText('Tool memoization', { exact: true })).toBeVisible();
  await expect(sourcePanel.getByText('Output optimization', { exact: true })).toBeVisible();

  const clientPanel = page.locator('.panel').filter({ hasText: 'Savings by client' });
  await expect(clientPanel.getByText('codex', { exact: true })).toBeVisible();
  await expect(clientPanel.getByText('100%', { exact: true })).toBeVisible();

  const modelPanel = page.locator('.panel').filter({ hasText: 'Savings by model' });
  await expect(modelPanel.getByText('gpt-4o-mini', { exact: true })).toBeVisible();
  });

  test('renders compression autopilot status when WS19 data is present', async ({ page }) => {
    await page.route('**/stats-history*', async route => {
      await route.fulfill({
        status: 200,
        contentType: 'application/json',
        body: JSON.stringify({ series: { hourly: [] } }),
      });
    });

    await page.route('**/stats?*', async route => {
      await route.fulfill({
        status: 200,
        contentType: 'application/json',
        body: JSON.stringify({
          summary: { saved: 1000, input: 8000, savings_percent: 12.5 },
          tokens: { saved: 1000, input: 8000, total_before_compression: 8000, active_savings_percent: 12.5 },
          requests: { total: 8, failed: 0, cached: 0 },
          recent_requests: [],
          persistent_savings: { lifetime: {}, display_session: {} },
          intelligence: {
            autopilot: {
              enabled: true,
              min_level: 1,
              max_level: 5,
              hysteresis_window: 10,
              task_levels: { code: 4, summarize: 5 },
              task_stats: {
                code: { signal_count: 6, clean_count: 5, adjustment_count: 1 },
                summarize: { signal_count: 3, clean_count: 3, adjustment_count: 0 },
              },
              recent_levels: [
                { task_type: 'code', level: 5, timestamp: '2026-07-02T04:20:00Z' },
                { task_type: 'code', level: 4, timestamp: '2026-07-02T04:25:00Z' },
                { task_type: 'summarize', level: 5, timestamp: '2026-07-02T04:30:00Z' },
              ],
              recent_adjustments: [
                {
                  task_type: 'code',
                  old_level: 5,
                  new_level: 4,
                  signal_kind: 'retrieval',
                  timestamp: '2026-07-02T04:25:00Z',
                },
              ],
            },
          },
        }),
      });
    });

    await page.goto('/dashboard');

    const autopilotPanel = page.locator('.panel').filter({ hasText: 'Compression autopilot' });
    await expect(autopilotPanel.getByText('Active')).toBeVisible();
    await expect(autopilotPanel.getByText('Code', { exact: true })).toBeVisible();
    await expect(autopilotPanel.getByText('Summaries', { exact: true })).toBeVisible();
    await expect(autopilotPanel.getByText('Latest adjustment: Code moved from L5 to L4 after a retrieval signal.')).toBeVisible();
  });
  test('renders all recent requests without capping and uses scrollable container', async ({ page }) => {
    // Generate 12 mock requests to exceed the previous 8-item limit
    const mockRequests = Array.from({ length: 12 }, (_, i) => ({
      request_id: `req-${i}`,
      timestamp: `2026-07-02T04:${30 + i}:00Z`,
      model: `gpt-4o-mini-${i}`,
      input_tokens_original: 1000,
      total_saved_tokens: 500,
      tokens_saved: 100,
      cache_saved_tokens: 400,
    }));

    await page.route('**/stats?*', async route => {
      await route.fulfill({
        status: 200,
        contentType: 'application/json',
        body: JSON.stringify({
          summary: { cost: { total_saved_usd: 1.0 } },
          tokens: { saved: 5000 },
          recent_requests: mockRequests,
          persistent_savings: { lifetime: {}, display_session: {} },
        }),
      });
    });

    await page.goto('/dashboard');

    // Wait for the panel
    const recentRequestsSection = page.locator('section.panel').filter({ hasText: 'Recent requests' });
    await expect(recentRequestsSection).toBeVisible();

    // Verify the scrollable container class is applied
    const tableShell = recentRequestsSection.locator('.request-table-shell');
    await expect(tableShell).toBeVisible();

    // Verify all 12 items are rendered (previously it was capped at 8)
    const rows = tableShell.locator('tbody tr');
    await expect(rows).toHaveCount(12);
  });
});
