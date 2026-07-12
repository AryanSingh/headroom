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

    await page.getByRole('button', { name: 'Balanced' }).click();

    await expect.poll(() => postUrls.length).toBe(1);
    await expect(postUrls).toEqual(['/config/flags']);
    await expect(postedBodies[0]).toMatchObject({ orchestrator_mode: 'balanced' });
  });
});
