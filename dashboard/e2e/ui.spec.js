import { expect, test } from '@playwright/test';

test('dashboard loads and exposes major navigation surfaces', async ({ page }) => {
  await page.goto('/dashboard');
  const nav = page.locator('.nav-stack');
  const currentTitle = page.locator('.topbar-title-row h2');
  await expect(currentTitle).toHaveText('Dashboard');

  await nav.getByRole('link', { name: 'Capabilities', exact: true }).click();
  await expect(currentTitle).toHaveText('Capabilities');

  await nav.getByRole('link', { name: 'Governance', exact: true }).click();
  await expect(currentTitle).toHaveText('Governance');

  await nav.getByRole('link', { name: 'Security', exact: true }).click();
  await expect(currentTitle).toHaveText('Security');

  await nav.getByRole('link', { name: 'Memory', exact: true }).click();
  await expect(currentTitle).toHaveText('Memory');

  await nav.getByRole('link', { name: 'Playground', exact: true }).click();
  await expect(currentTitle).toHaveText('Playground');
  await expect(page.getByRole('button', { name: /load sample multimodal image/i })).toBeVisible();
});
