import { expect, test } from '@playwright/test';

test.describe('Quiet command center semantics', () => {
  test.beforeEach(async ({ page }) => {
    await page.addInitScript(() => {
      window.localStorage.setItem('cutctxAdminKey', 'testkey');
    });

    await page.route('**/health', async (route) => {
      await route.fulfill({
        status: 200,
        contentType: 'application/json',
        body: JSON.stringify({ status: 'healthy', ready: true }),
      });
    });
  });

  test('marks the memory enterprise gate as a semantic status surface', async ({ page }) => {
    await page.route('**/stats?*', async (route) => {
      await route.fulfill({
        status: 200,
        contentType: 'application/json',
        body: JSON.stringify({
          config: { memory: false },
        }),
      });
    });

    await page.route('**/v1/memory/query?limit=20', async (route) => {
      await route.fulfill({
        status: 200,
        contentType: 'application/json',
        body: JSON.stringify([]),
      });
    });

    await page.goto('/dashboard/memory');

    await expect(page.locator('.topbar-title-row h2')).toHaveText('Memory');
    await expect(page.getByTestId('memory-enterprise-state')).toHaveAttribute('role', 'status');
    await expect(page.getByTestId('memory-enterprise-state')).toContainText('Cross-agent memory');
  });
});
