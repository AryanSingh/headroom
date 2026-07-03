import { test, expect } from '@playwright/test';

test.describe('Capabilities Toggles', () => {
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

    const flagsState = {
      rate_limiter: false,
      cache: false,
      ccr: false,
      memory: false,
      firewall: false,
    };

    await page.route('**/stats?*', async route => {
      await route.fulfill({
        status: 200,
        contentType: 'application/json',
        body: JSON.stringify({
          config: {
            rate_limiter: flagsState.rate_limiter,
            cache: flagsState.cache,
            ccr: flagsState.ccr,
            memory: flagsState.memory,
            firewall: flagsState.firewall,
          },
          rate_limiter: { active_keys: 0, tokens_per_minute: 0 },
          cache: { total_hits: 0, entries: 0, max_entries: 0 },
          compression: { ccr_entries: 0, ccr_retrievals: 0 },
          memory: { active_sessions: 0 },
          firewall: { scans: 0 },
        }),
      });
    });

    const configEndpoints = ['**/config/flags*', '**/admin/config/flags*'];
    for (const endpoint of configEndpoints) {
      await page.route(endpoint, async route => {
        if (route.request().method() === 'POST') {
          const payload = JSON.parse(route.request().postData() || '{}');
          Object.assign(flagsState, payload);
          await route.fulfill({
            status: 200,
            contentType: 'application/json',
            body: JSON.stringify({
              config: { ...flagsState },
              live_toggleable: Object.fromEntries(
                Object.entries(flagsState).map(([key, enabled]) => [key, { enabled, source: 'runtime' }]),
              ),
            }),
          });
          return;
        }

        await route.fulfill({
          status: 200,
          contentType: 'application/json',
          body: JSON.stringify({
            config: { ...flagsState },
            live_toggleable: Object.fromEntries(
              Object.entries(flagsState).map(([key, enabled]) => [key, { enabled, source: 'runtime' }]),
            ),
          }),
        });
      });
    }
  });

  test('toggling a live surface fires a POST to the config flags endpoint', async ({ page }) => {
    const configPosts = [];

    for (const endpoint of ['**/config/flags*', '**/admin/config/flags*']) {
      await page.route(endpoint, async route => {
        if (route.request().method() === 'POST') {
          configPosts.push({
            url: route.request().url(),
            body: route.request().postData(),
          });
        }
        await route.fallback();
      });
    }

    await page.goto('/capabilities');

    await expect(page.locator('.topbar-title-row h2')).toHaveText('Capabilities');
    await expect(page.getByText('Live evidence')).toBeVisible();

    const liveEvidencePanel = page
      .locator('.panel')
      .filter({ has: page.getByText('Live evidence') });
    await expect(liveEvidencePanel).toBeVisible();

    const rateLimiterCard = liveEvidencePanel.locator('.metric-card').filter({ hasText: 'Rate limiter' });
    await expect(rateLimiterCard.locator('.status-inactive')).toHaveText('Idle');
    const firstToggle = rateLimiterCard.locator('.toggle-switch input[type="checkbox"]');
    await expect(firstToggle).toHaveCount(1);
    const initialChecked = await firstToggle.isChecked();
    await rateLimiterCard.locator('.toggle-switch').click();

    await expect.poll(() => configPosts.length, { timeout: 5000 }).toBeGreaterThan(0);

    const lastPost = configPosts[configPosts.length - 1];
    const body = JSON.parse(lastPost.body || '{}');
    const bodyKeys = Object.keys(body);
    expect(bodyKeys.length).toBeGreaterThan(0);
    expect(typeof body[bodyKeys[0]]).toBe('boolean');

    const stateAfter = await firstToggle.isChecked();
    expect(stateAfter).not.toBe(initialChecked);
    await expect(rateLimiterCard.locator('.status-active')).toHaveText('Active');

    await page.screenshot({ path: 'screenshots/capabilities-toggle.png', fullPage: true });
  });

  test('falls back to stats-backed states when config flags endpoint is missing', async ({ page }) => {
    await page.route('**/config/flags*', async route => {
      await route.fulfill({ status: 404, body: 'Not Found' });
    });
    await page.route('**/admin/config/flags*', async route => {
      await route.fulfill({ status: 404, body: 'Not Found' });
    });

    await page.goto('/capabilities');

    const liveEvidencePanel = page
      .locator('.panel')
      .filter({ has: page.getByText('Live evidence') });

    await expect(liveEvidencePanel).toBeVisible();
    await expect(page.getByText(/Runtime config API unavailable/)).toHaveCount(0);

    const rateLimiterCard = liveEvidencePanel.locator('.metric-card').filter({ hasText: 'Rate limiter' });
    await expect(rateLimiterCard.locator('.status-inactive')).toHaveText('Idle');
  });
});
