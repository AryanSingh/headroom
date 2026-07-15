import { expect, test } from '@playwright/test';

test.describe('Navigation and Layout', () => {
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
        body: JSON.stringify({}),
      });
    });
  });

  test('dashboard loads exposes major navigation surfaces', async ({ page }) => {
    await page.goto('/dashboard');
    await expect(page.getByRole('navigation', { name: 'Main Navigation' })).toBeVisible();
    const nav = page.locator('.nav-stack');
    const currentTitle = page.locator('.topbar-title-row h2');
    await expect(currentTitle).toHaveText('Dashboard');

    await nav.getByRole('link', { name: 'Capabilities', exact: true }).click();
    await expect(currentTitle).toHaveText('Capabilities');

    await nav.getByRole('link', { name: 'Governance', exact: true }).click();
    await expect(currentTitle).toHaveText('Governance');
    await expect(page.getByRole('heading', { name: 'Enable optional features' })).toBeVisible();

    await nav.getByRole('link', { name: 'Security', exact: true }).click();
    await expect(currentTitle).toHaveText('Security');
    await expect(page.getByText('Firewall event tape')).toBeVisible();

    await nav.getByRole('link', { name: 'Memory', exact: true }).click();
    await expect(currentTitle).toHaveText('Memory');

    await nav.getByRole('link', { name: 'Replay', exact: true }).click();
    await expect(currentTitle).toHaveText('Replay');
    await expect(page.getByRole('heading', { name: 'Inspect policy decisions for a session' })).toBeVisible();

    await nav.getByRole('link', { name: 'Playground', exact: true }).click();
    await expect(currentTitle).toHaveText('Playground');
    await expect(page.getByRole('button', { name: /load sample multimodal image/i })).toBeVisible();
  });

  test('unknown routes redirect to dashboard', async ({ page }) => {
    await page.goto('/dashboard/does-not-exist');
    await expect(page.locator('.topbar-title-row h2')).toHaveText('Dashboard');
  });

  test('sidebar opens and closes with Escape on mobile viewports', async ({ page }) => {
    await page.setViewportSize({ width: 375, height: 812 });
    await page.goto('/dashboard');

    const toggleButton = page.locator('.sidebar-toggle-btn');
    await expect(toggleButton).toBeVisible();

    await toggleButton.click();
    await expect(page.locator('.sidebar-shell')).toHaveClass(/open/);

    await page.keyboard.press('Escape');
    await expect(page.locator('.sidebar-shell')).not.toHaveClass(/open/);
    await expect(toggleButton).toBeFocused();
  });
});
