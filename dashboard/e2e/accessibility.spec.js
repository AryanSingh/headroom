import AxeBuilder from '@axe-core/playwright';
import { expect, test } from '@playwright/test';

const SERIOUS_IMPACTS = new Set(['critical', 'serious']);

const STATS_BODY = {
  summary: { cost: { without_cutctx_usd: 1.5, with_cutctx_usd: 0.25, total_saved_usd: 1.25 } },
  tokens: { saved: 5000, savings_usd: 1.25, savings_percent: 12.5 },
  requests: { total: 125, failed: 2, cached: 15 },
  persistent_savings: {
    lifetime: { requests: 125, tokens_saved: 5000, total_input_tokens: 40000, total_savings_usd: 1.25 },
    display_session: { requests: 20, tokens_saved: 800, total_input_tokens: 6000, total_savings_usd: 0.2 },
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
};

test.describe('Dashboard accessibility', () => {
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
    await page.route('**/stats?*', async (route) => {
      await route.fulfill({
        status: 200,
        contentType: 'application/json',
        body: JSON.stringify(STATS_BODY),
      });
    });
    await page.route('**/stats-history*', async (route) => {
      await route.fulfill({
        status: 200,
        contentType: 'application/json',
        body: JSON.stringify({ series: { hourly: [] } }),
      });
    });
  });

  test('overview has no serious accessibility violations', async ({ page }) => {
    await page.goto('/dashboard');
    await expect(page.locator('.topbar-title-row h2')).toHaveText('Dashboard');

    const results = await new AxeBuilder({ page }).analyze();
    const serious = results.violations.filter((violation) => SERIOUS_IMPACTS.has(violation.impact ?? ''));
    expect(serious, JSON.stringify(serious, null, 2)).toEqual([]);
  });

  test('skip link moves focus to main content', async ({ page }) => {
    await page.goto('/dashboard');
    await expect(page.locator('.topbar-title-row h2')).toHaveText('Dashboard');

    await page.keyboard.press('Tab');
    const skipLink = page.locator('.skip-link');
    await expect(skipLink).toBeFocused();

    await page.keyboard.press('Enter');
    await expect(page.locator('#main-content')).toBeFocused();
  });

  test('primary navigation is reachable and operable via keyboard', async ({ page }) => {
    await page.goto('/dashboard');
    await expect(page.locator('.topbar-title-row h2')).toHaveText('Dashboard');

    const savingsLink = page.locator('nav[aria-label="Main Navigation"] a', { hasText: 'Savings' });
    await savingsLink.focus();
    await expect(savingsLink).toBeFocused();

    await page.keyboard.press('Enter');
    await expect(page.locator('.topbar-title-row h2')).toHaveText('Savings');

    await page.keyboard.press('Shift+Tab');
    const dashboardLink = page.locator('nav[aria-label="Main Navigation"] a', { hasText: 'Dashboard' });
    await expect(dashboardLink).toBeFocused();
  });

  test('mobile sidebar drawer closes on Escape and restores focus', async ({ page }) => {
    await page.setViewportSize({ width: 375, height: 812 });
    await page.goto('/dashboard');
    await expect(page.locator('.topbar-title-row h2')).toHaveText('Dashboard');

    const toggle = page.getByRole('button', { name: 'Toggle sidebar' });
    await toggle.click();
    await expect(page.locator('.sidebar-shell')).toHaveClass(/open/);

    await page.keyboard.press('Escape');
    await expect(page.locator('.sidebar-shell')).not.toHaveClass(/open/);
    await expect(toggle).toBeFocused();
  });
});
