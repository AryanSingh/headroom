import { chromium } from '@playwright/test';
import { mkdirSync } from 'node:fs';
import { resolve } from 'node:path';

const out = resolve(import.meta.dirname, '../../audit/screenshots');
mkdirSync(out, { recursive: true });

const browser = await chromium.launch();
const context = await browser.newContext({ viewport: { width: 1440, height: 900 } });
const page = await context.newPage();

await page.addInitScript(() => {
  localStorage.setItem('cutctxAdminKey', 'testkey');
  localStorage.setItem('cutctxTheme', 'dark');
});

const json = (body) => ({
  status: 200,
  contentType: 'application/json',
  body: JSON.stringify(body),
});

await page.route('**/health', (route) => route.fulfill(json({ status: 'healthy', ready: true, version: '0.32.0' })));
await page.route('**/stats**', (route) => route.fulfill(json({
  cost: { savings_usd: 12.34, compression_savings_usd: 8.1 },
  tokens: { total_before_compression: 100000, total_after_compression: 62000, active_savings_percent: 38 },
  summary: { requests: 128 },
})));
await page.route('**/stats-history**', (route) => route.fulfill(json([])));
await page.route('**/config**', (route) => route.fulfill(json({})));
await page.route('**/entitlements**', (route) => route.fulfill(json({ tier: 'business' })));
await page.route('**/policy**', (route) => route.fulfill(json({})));
await page.route('**/firewall/**', (route) => route.fulfill(json({ enabled: true, patterns_loaded: 12, config: {} })));
await page.route('**/audit/**', (route) => route.fulfill(json([])));
await page.route('**/rbac/**', (route) => route.fulfill(json([])));
await page.route('**/safe-savings**', (route) => route.fulfill(json({})));
await page.route('**/routing**', (route) => route.fulfill(json({})));

const base = process.env.BASE_URL || 'http://localhost:4123';

async function shot(path, file, viewport) {
  if (viewport) {
    await page.setViewportSize(viewport);
  }
  await page.goto(`${base}/dashboard${path}`, { waitUntil: 'domcontentloaded', timeout: 15000 });
  await page.waitForTimeout(600);
  await page.screenshot({ path: resolve(out, file), fullPage: true });
  console.log('wrote', file);
}

await shot('', 'overview-desktop-dark.png', { width: 1440, height: 900 });
await shot('/savings', 'savings-desktop-dark.png');
await shot('/orchestrator', 'orchestrator-desktop-dark.png');
await shot('/governance', 'governance-desktop-dark.png');
await shot('/firewall', 'security-desktop-dark.png');
await shot('', 'overview-mobile-dark.png', { width: 390, height: 844 });

await page.setViewportSize({ width: 1440, height: 900 });
await page.goto(`${base}/dashboard`, { waitUntil: 'domcontentloaded' });
await page.getByRole('button', { name: /switch to light mode/i }).click();
await page.waitForTimeout(400);
await page.screenshot({ path: resolve(out, 'overview-desktop-light.png'), fullPage: true });
console.log('wrote overview-desktop-light.png');

await browser.close();
