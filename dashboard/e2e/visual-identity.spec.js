import { expect, test } from '@playwright/test';

async function mockDashboardApis(page) {
  await page.addInitScript(() => {
    window.localStorage.setItem('cutctxAdminKey', 'testkey');
    window.localStorage.setItem('cutctxTheme', 'dark');
  });

  await page.route('**/health', async route => {
    await route.fulfill({
      status: 200,
      contentType: 'application/json',
      body: JSON.stringify({ status: 'healthy', ready: true, version: '0.32.0' }),
    });
  });

  await page.route('**/stats**', async route => {
    await route.fulfill({
      status: 200,
      contentType: 'application/json',
      body: JSON.stringify({}),
    });
  });
}

test.describe('Context Command Center visual identity', () => {
  test.beforeEach(async ({ page }) => {
    await mockDashboardApis(page);
  });

  test('applies Sora display and IBM Plex Sans body fonts', async ({ page }) => {
    await page.goto('/dashboard');
    await expect(page.locator('.topbar-title-row h2')).toHaveText('Dashboard');

    const fonts = await page.evaluate(() => {
      const title = document.querySelector('.topbar-title-row h2');
      const body = document.body;
      return {
        title: getComputedStyle(title).fontFamily,
        body: getComputedStyle(body).fontFamily,
      };
    });

    expect(fonts.title.toLowerCase()).toContain('sora');
    expect(fonts.body.toLowerCase()).toContain('ibm plex sans');
    expect(fonts.body.toLowerCase()).not.toContain('inter');
  });

  test('theme toggle switches between dark and light identity', async ({ page }) => {
    await page.goto('/dashboard');
    const html = page.locator('html');
    await expect(html).toHaveClass(/dark/);

    await page.getByRole('button', { name: /switch to light mode|switch to dark mode|theme/i }).click();
    await expect(html).toHaveClass(/light/);

    await page.getByRole('button', { name: /switch to light mode|switch to dark mode|theme/i }).click();
    await expect(html).toHaveClass(/dark/);
  });

  test('dark overview shell matches the approved visual baseline', async ({ page }) => {
    await page.setViewportSize({ width: 1280, height: 900 });
    await page.goto('/dashboard');
    await expect(page.locator('.topbar-title-row h2')).toHaveText('Dashboard');
    await expect(page.getByText('Loading module…')).toBeHidden({ timeout: 15_000 });

    await expect(page).toHaveScreenshot('overview-shell-dark.png', {
      animations: 'disabled',
      fullPage: true,
      maxDiffPixelRatio: 0.005,
    });
  });

  test('mobile sidebar drawer closes with Escape', async ({ page }) => {
    await page.setViewportSize({ width: 375, height: 812 });
    await page.goto('/dashboard');

    const toggle = page.locator('.sidebar-toggle-btn');
    await expect(toggle).toBeVisible();
    await toggle.click();
    await expect(page.locator('.sidebar-shell')).toHaveClass(/open/);

    await page.keyboard.press('Escape');
    await expect(page.locator('.sidebar-shell')).not.toHaveClass(/open/);
    await expect(toggle).toBeFocused();
  });

  test('Orchestrator exposes live control-plane status badge', async ({ page }) => {
    await page.route('**/policy**', async route => {
      await route.fulfill({ status: 200, contentType: 'application/json', body: JSON.stringify({}) });
    });
    await page.route('**/safe-savings**', async route => {
      await route.fulfill({ status: 200, contentType: 'application/json', body: JSON.stringify({}) });
    });
    await page.goto('/dashboard/orchestrator');
    await expect(page.getByTestId('control-plane-status')).toBeVisible({ timeout: 15000 });
    await expect(page.getByTestId('control-plane-status')).toHaveText(/Live|Degraded/);
  });
});
