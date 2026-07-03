import { test, expect } from '@playwright/test';

test.describe('Session Replay', () => {
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
          summary: { saved: 0, input: 0, savings_percent: 0 },
          tokens: { saved: 0, input: 0 },
          requests: { total: 0 },
          recent_requests: [],
          persistent_savings: { lifetime: {}, display_session: {} },
        }),
      });
    });
  });

  test('loads replay timeline for a session', async ({ page }) => {
    await page.route('**/v1/sessions/sess-1/replay', async route => {
      expect(route.request().headers()['x-cutctx-admin-key']).toBe('testkey');
      await route.fulfill({
        status: 200,
        contentType: 'application/json',
        body: JSON.stringify({
          session_id: 'sess-1',
          events: [
            {
              timestamp: Date.now() / 1000,
              session_id: 'sess-1',
              event_type: 'policy_blocked',
              surface: 'openai.chat.completions',
              request_id: 'req-1',
              detail: {
                matched_rules: ['secret'],
                message: 'Blocked by context policy.',
              },
            },
          ],
        }),
      });
    });

    await page.goto('/dashboard/replay');
    await page.getByLabel('Session ID').fill('sess-1');
    await page.getByRole('button', { name: 'Load replay' }).click();

    await expect(page.getByRole('heading', { name: 'sess-1' })).toBeVisible();
    await expect(page.getByText('Context policy blocked request')).toBeVisible();
    await expect(page.getByText('Rules: secret')).toBeVisible();
  });

  test('shows a useful empty/error state when replay is unavailable', async ({ page }) => {
    await page.route('**/v1/sessions/missing/replay', async route => {
      await route.fulfill({
        status: 404,
        contentType: 'application/json',
        body: JSON.stringify({ error: 'replay_not_found' }),
      });
    });

    await page.goto('/dashboard/replay');
    await expect(page.getByText('Enter a session id to inspect replay events.')).toBeVisible();

    await page.getByLabel('Session ID').fill('missing');
    await page.getByRole('button', { name: 'Load replay' }).click();

    await expect(
      page.getByText('No replay events found for that session, or replay is disabled on the proxy.'),
    ).toBeVisible();
  });
});
