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
});
