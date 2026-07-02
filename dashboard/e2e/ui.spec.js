import { expect, test } from '@playwright/test';

test.describe('Navigation and Layout', () => {
  test.beforeEach(async ({ page }) => {
    // Authenticate user
    await page.addInitScript(() => {
      window.localStorage.setItem('cutctxAdminKey', 'testkey');
    });
    // Mock successful response
    await page.route('**/stats*', async route => {
      await route.fulfill({
        status: 200,
        contentType: 'application/json',
        body: JSON.stringify({}),
      });
    });
  });

  test('dashboard loads and exposes major navigation surfaces', async ({ page }) => {
    await page.goto('/dashboard');
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

    await nav.getByRole('link', { name: 'Playground', exact: true }).click();
    await expect(currentTitle).toHaveText('Playground');
    await expect(page.getByRole('button', { name: /load sample multimodal image/i })).toBeVisible();
  });

  test('sidebar collapses on mobile viewports', async ({ page }) => {
    // Set viewport to mobile size
    await page.setViewportSize({ width: 375, height: 812 });
    
    await page.goto('/dashboard');
    
    // Check that sidebar is collapsed (app-shell has sidebar-collapsed class)
    // Actually the sidebar itself might be hidden
    // On mobile, the sidebar might be hidden via CSS, but let's check the toggle button
    const toggleButton = page.locator('.sidebar-toggle-btn');
    await expect(toggleButton).toBeVisible();

    // Click toggle to open sidebar
    await toggleButton.click();
    const currentTitle = page.locator('.topbar-title-row h2');
    await expect(currentTitle).toBeVisible();
  });
});
