import { test, expect } from '@playwright/test';

test.describe('Overview Metrics & Panels', () => {
  test.beforeEach(async ({ page }) => {
    // Authenticate user
    await page.addInitScript(() => {
      window.localStorage.setItem('cutctxAdminKey', 'testkey');
    });
  });

  test('successfully loads and displays mocked stats data', async ({ page }) => {
    // Mock successful response with realistic dummy data
    await page.route('**/stats*', async route => {
      await route.fulfill({
        status: 200,
        contentType: 'application/json',
        body: JSON.stringify({
          summary: { cost: { without_cutctx_usd: 1.50, with_cutctx_usd: 0.25, total_saved_usd: 1.25 } },
          tokens: { saved: 5000, savings_usd: 1.25, savings_percent: 12.5 },
          requests: { total: 125, failed: 2, cached: 15 },
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

  test('gracefully handles 500 Internal Server Error', async ({ page }) => {
    // Mock 500 error
    await page.route('**/stats*', async route => {
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

  test('prefers live session savings over lifetime rollups and keeps attribution USD consistent', async ({ page }) => {
    await page.route('**/stats-history*', async route => {
      await route.fulfill({
        status: 200,
        contentType: 'application/json',
        body: JSON.stringify({ series: { hourly: [] } }),
      });
    });

    await page.route('**/stats*', async route => {
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
              },
              usd: {},
              total_tokens: 6357110,
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

    await expect(page.locator('.metric-card').filter({ hasText: 'Tokens saved' }).locator('.metric-value')).toHaveText('58.6k');
    await expect(page.locator('.metric-card').filter({ hasText: 'Requests' }).locator('.metric-value')).toHaveText('136');
    await expect(page.locator('.metric-card').filter({ hasText: 'Money saved' }).locator('.metric-value')).toHaveText('$0.615');

    const sourcePanel = page.locator('.panel').filter({ hasText: 'Where savings come from' });
    await expect(sourcePanel.getByText('Direct compression58,617 tokens · $0.1390.9%')).toBeVisible();
    await expect(sourcePanel.getByText('Provider prompt cache6,349,824 tokens · $0.47699.0%')).toBeVisible();

    const clientPanel = page.locator('.panel').filter({ hasText: 'Savings by client' });
    await expect(clientPanel.getByText('codex6,353,030 tokens· $0.615100%')).toBeVisible();

    const modelPanel = page.locator('.panel').filter({ hasText: 'Savings by model' });
    await expect(modelPanel.getByText('gpt-4o-mini0 tokens · 97 requests· $0.0000.0%')).toBeVisible();
  });
});
