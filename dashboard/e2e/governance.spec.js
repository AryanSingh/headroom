import { test, expect } from '@playwright/test';

test.describe('Governance Toggles', () => {
  test.beforeEach(async ({ page }) => {
    await page.addInitScript(() => {
      window.localStorage.setItem('cutctxAdminKey', 'testkey');
    });
    
    // Mock health
    await page.route('**/health', async route => {
      await route.fulfill({
        status: 200,
        contentType: 'application/json',
        body: JSON.stringify({ status: 'healthy', ready: true }),
      });
    });

    // Mock initial stats/flags state
    await page.route('**/stats?*', async route => {
      await route.fulfill({
        status: 200,
        contentType: 'application/json',
        body: JSON.stringify({
          config: {},
          rate_limiter: {},
        }),
      });
    });

    // Mock governance sub-routes
    await page.route('**/audit/events', async route => {
      await route.fulfill({ status: 200, body: JSON.stringify({ events: [] }) });
    });
    await page.route('**/rbac/roles', async route => {
      await route.fulfill({ status: 200, body: JSON.stringify({ assignments: [] }) });
    });
  });

  test('toggling a live surface in governance fires POST to config flags', async ({ page }) => {
    let postFired = false;
    await page.route('**/config/flags*', async route => {
      if (route.request().method() === 'POST') {
        postFired = true;
        const payload = JSON.parse(route.request().postData() || '{}');
        await route.fulfill({
          status: 200,
          contentType: 'application/json',
          body: JSON.stringify({
            applied_live: {
               [Object.keys(payload)[0]]: { enabled: Object.values(payload)[0] }
            }
          }),
        });
        return;
      }
      await route.fulfill({ status: 200, contentType: 'application/json', body: JSON.stringify({ live_toggleable: { task_aware_enabled: { enabled: false } } }) });
    });

    await page.goto('/governance');
    await expect(page.locator('.topbar-title-row h2')).toHaveText('Governance');
    
    // Find Task-aware compression feature toggle (which is live toggleable)
    const row = page.locator('.feature-config-row').filter({ hasText: 'Task-aware compression' });
    await expect(row).toBeVisible();
    
    const toggle = row.locator('.feature-toggle');
    await toggle.click();
    
    await expect.poll(() => postFired).toBe(true);
  });
});
