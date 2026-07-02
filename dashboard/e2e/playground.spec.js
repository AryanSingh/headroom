import { test, expect } from '@playwright/test';

test.describe('Playground Live Compression', () => {
  test.beforeEach(async ({ page }) => {
    await page.addInitScript(() => {
      window.localStorage.setItem('cutctxAdminKey', 'testkey');
    });

    await page.route('**/stats*', async route => {
      await route.fulfill({
        status: 200,
        contentType: 'application/json',
        body: JSON.stringify({}),
      });
    });
  });

  test('submits a prompt, runs compression, and renders the result', async ({ page }) => {
    let compressRequest = null;
    await page.route('**/v1/compress*', async route => {
      compressRequest = route.request();
      await route.fulfill({
        status: 200,
        contentType: 'application/json',
        body: JSON.stringify({
          tokens_before: 1234,
          tokens_after: 512,
          tokens_saved: 722,
          compression_ratio: 0.415,
          transforms_applied: ['deduplicate', 'strip_log_noise'],
          messages: [
            { role: 'user', content: [{ type: 'text', text: 'Summarized prompt payload.' }] },
          ],
        }),
      });
    });

    await page.goto('/playground');

    await expect(page.locator('.topbar-title-row h2')).toHaveText('Playground');

    const promptTextarea = page.getByPlaceholder(
      'Paste a long tool output, code, transcript, or ask a multimodal question.',
    );
    await expect(promptTextarea).toBeVisible();
    await promptTextarea.fill('Summarize the dashboard data');

    const modelSelect = page.locator('select');
    await modelSelect.selectOption('claude-sonnet-4-6');

    const runButton = page.getByRole('button', { name: /run live compression/i });
    await expect(runButton).toBeVisible();
    await runButton.click();

    await expect.poll(() => compressRequest).not.toBeNull();
    const payload = JSON.parse(compressRequest.postData() || '{}');
    expect(payload.model).toBe('claude-sonnet-4-6');
    expect(payload.messages[0].content[0].text).toBe('Summarize the dashboard data');
    expect(payload.compress_user_messages).toBe(true);

    const tokensBefore = page.locator('.metric-card').filter({ hasText: 'Tokens before' });
    const tokensAfter = page.locator('.metric-card').filter({ hasText: 'Tokens after' });
    const tokensSaved = page.locator('.metric-card').filter({ hasText: 'Tokens saved' });

    await expect(tokensBefore.locator('.metric-value')).toHaveText('1,234');
    await expect(tokensAfter.locator('.metric-value')).toHaveText('512');
    await expect(tokensSaved.locator('.metric-value')).toHaveText('722');

    await expect(page.getByText('deduplicate')).toBeVisible();
    await expect(page.getByText('strip_log_noise')).toBeVisible();

    await page.screenshot({ path: 'screenshots/playground-run-result.png', fullPage: true });
  });

  test('shows an error when the run button is clicked with an empty prompt', async ({ page }) => {
    await page.route('**/v1/compress*', async route => {
      await route.fulfill({
        status: 200,
        contentType: 'application/json',
        body: JSON.stringify({}),
      });
    });

    await page.goto('/playground');

    const runButton = page.getByRole('button', { name: /run live compression/i });
    await runButton.click();

    await expect(
      page.getByText('Enter a prompt before running the playground.'),
    ).toBeVisible();
  });

  test('surfaces an error when the compress endpoint returns non-2xx', async ({ page }) => {
    await page.route('**/v1/compress*', async route => {
      await route.fulfill({
        status: 500,
        contentType: 'application/json',
        body: JSON.stringify({ detail: 'Internal Server Error' }),
      });
    });

    await page.goto('/playground');

    const promptTextarea = page.getByPlaceholder(
      'Paste a long tool output, code, transcript, or ask a multimodal question.',
    );
    await promptTextarea.fill('Trigger a server failure');

    const runButton = page.getByRole('button', { name: /run live compression/i });
    await runButton.click();

    await expect(
      page.getByText(/Compression request failed with 500/),
    ).toBeVisible();
  });
});
