import { test, expect } from '@playwright/test';

const statsEndpoint = /\/stats(?:\?.*)?$/;

async function mockAuxiliaryDashboardRequests(page, { healthStatus = 200 } = {}) {
  await page.route('**/health', async route => {
    await route.fulfill({
      status: healthStatus,
      contentType: 'application/json',
      body: JSON.stringify(
        healthStatus === 200
          ? { status: 'ok', ready: true }
          : { detail: 'Proxy unavailable' },
      ),
    });
  });
  await page.route('**/stats-history*', async route => {
    await route.fulfill({
      status: 200,
      contentType: 'application/json',
      body: JSON.stringify([]),
    });
  });
}

test.describe('Authentication Flow', () => {
  test.beforeEach(async () => {
    // We will clear localStorage in each test before goto
  });

  test('displays Auth Overlay on 401 Unauthorized', async ({ page }) => {
    await mockAuxiliaryDashboardRequests(page, { healthStatus: 502 });

    // Delay the 401 so the unrelated health failure arrives first. The
    // authentication surface must still win regardless of response timing.
    await page.route(statsEndpoint, async route => {
      await new Promise(resolve => setTimeout(resolve, 100));
      await route.fulfill({
        status: 401,
        contentType: 'application/json',
        body: JSON.stringify({ detail: "Unauthorized" }),
      });
    });

    await page.goto('/dashboard');
    await page.evaluate(() => window.localStorage.clear());
    await page.reload();

    // Check that the auth surface is visible
    await expect(page.getByTestId('authentication-surface')).toBeVisible();
    await expect(page.getByRole('heading', { name: 'Connect to Cutctx' })).toBeVisible();

    // Check that the input and button are visible
    const input = page.getByPlaceholder('Enter CUTCTX_ADMIN_API_KEY');
    await expect(input).toBeVisible();

    const saveButton = page.getByRole('button', { name: 'Save & Reload' });
    await expect(saveButton).toBeVisible();
  });

  test('saves key to localStorage and reloads page on submit', async ({ page }) => {
    let mockStatus = 401;
    await mockAuxiliaryDashboardRequests(page);

    // Route will return 401 first, then 200 after page reloads if it has the right header
    await page.route(statsEndpoint, async route => {
      if (route.request().headers()['x-cutctx-admin-key'] === 'testkey') {
        mockStatus = 200;
        await route.fulfill({
          status: 200,
          contentType: 'application/json',
          body: JSON.stringify({}),
        });
      } else {
        await route.fulfill({
          status: mockStatus,
          contentType: 'application/json',
          body: JSON.stringify({ detail: "Unauthorized" }),
        });
      }
    });

    await page.goto('/dashboard');
    await page.evaluate(() => window.localStorage.clear());
    await page.reload();

    // Fill in the key
    const input = page.getByPlaceholder('Enter CUTCTX_ADMIN_API_KEY');
    await input.fill('testkey');

    // Click Save & Reload
    const saveButton = page.getByRole('button', { name: 'Save & Reload' });
    
    // Wait for reload navigation
    await Promise.all([
      page.waitForNavigation(),
      saveButton.click()
    ]);

    // Check localStorage
    const storedKey = await page.evaluate(() => window.localStorage.getItem('cutctxAdminKey'));
    expect(storedKey).toBe('testkey');

    // After reload, with the key sent in headers, the mocked route returns 200, so overlay should be gone
    await expect(page.getByTestId('authentication-surface')).toBeHidden();
  });

  test('does not display Auth Overlay when authenticated (200 OK)', async ({ page }) => {
    await mockAuxiliaryDashboardRequests(page);

    // Mock successful response
    await page.route(statsEndpoint, async route => {
      await route.fulfill({
        status: 200,
        contentType: 'application/json',
        body: JSON.stringify({
          summary: { total_requests: 0, failed: 0, cached: 0 },
          savings: { total_tokens: 0, usd: { total: 0 } },
          route_counts: {}
        }),
      });
    });

    await page.goto('/dashboard');
    await page.evaluate(() => window.localStorage.clear());
    await page.reload();

    await expect(page.getByTestId('authentication-surface')).toBeHidden();

    // The Dashboard title should be visible
    const dashboardTitle = page.locator('.topbar-title-row h2');
    await expect(dashboardTitle).toBeVisible();
  });
});
