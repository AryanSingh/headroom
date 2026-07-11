import { test, expect } from '@playwright/test';

test.describe('Orchestrator Toggles', () => {
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
          config: { orchestrator: false }
        }),
      });
    });
  });

  test('toggling orchestrator fires POST to config flags', async ({ page }) => {
    const postUrls = [];
    await page.route('**/config/flags*', async route => {
      if (route.request().method() === 'POST') {
        postUrls.push(new URL(route.request().url()).pathname);
        await route.fulfill({ status: 200, contentType: 'application/json', body: JSON.stringify({}) });
        return;
      }
      await route.fulfill({ status: 200, contentType: 'application/json', body: JSON.stringify({}) });
    });

    await page.goto('/orchestrator');
    
    await expect(page.locator('h2').filter({ hasText: 'Orchestrator Insights' })).toBeVisible();
    
    const toggle = page.locator('.toggle-switch input[type="checkbox"]');
    await expect(page.locator('.toggle-switch')).toBeVisible();
    
    // Check initial state
    await expect(toggle).not.toBeChecked();
    
    // Click parent label to toggle
    await page.locator('.toggle-switch').click();
    
    await expect.poll(() => postUrls.length).toBe(1);
    await expect(postUrls).toEqual(['/config/flags']);
  });
});
