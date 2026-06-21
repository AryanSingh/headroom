import { test, expect } from '@playwright/test';

test('dashboard loads and navigates', async ({ page }) => {
  await page.goto('/');
  await expect(page.locator('h2').first()).toHaveText('Dashboard Overview');

  // Navigate to Firewall
  await page.click('text=Firewall');
  await expect(page.locator('h2').first()).toHaveText('Firewall & Security');

  // Navigate to Memory
  await page.click('text=Memory & Learn');
  await expect(page.locator('h2').first()).toHaveText('Memory & Learn');

  // Navigate to Playground
  await page.click('text=Prompt Simulator');
  await expect(page.locator('h2').first()).toHaveText('Prompt Simulator');

  // Test empty state
  await page.click('button:has-text("Simulate")');
  await expect(page.locator('text=Please enter a prompt to simulate.')).toBeVisible();

  // Test simulate
  await page.fill('textarea', 'simulate this text');
  await page.click('button:has-text("Simulate")');
  await expect(page.locator('h3:has-text("Original Prompt")')).toBeVisible();
});
