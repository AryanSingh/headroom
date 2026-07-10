import { expect, test as base } from '@playwright/test';

export const ROUTE_INVENTORY = Object.freeze([
  { path: '/', label: 'Dashboard' },
  { path: '/savings', label: 'Savings' },
  { path: '/orchestrator', label: 'Orchestrator' },
  { path: '/capabilities', label: 'Capabilities' },
  { path: '/governance', label: 'Governance' },
  { path: '/firewall', label: 'Security' },
  { path: '/memory', label: 'Memory' },
  { path: '/replay', label: 'Replay' },
  { path: '/playground', label: 'Playground' },
  { path: '/docs', label: 'Docs' },
]);

const JSON_HEADERS = { 'content-type': 'application/json' };

const STATS = {
  summary: { saved: 0, input: 0, savings_percent: 0 },
  tokens: { saved: 0, input: 0, total_before_compression: 0, savings_percent: 0 },
  requests: { total: 0, failed: 0, cached: 0 },
  config: {
    firewall: false,
    memory: false,
    orchestrator: false,
    rate_limiter: false,
  },
  cost: { budget: { enabled: false } },
  recent_requests: [],
  persistent_savings: { lifetime: {}, display_session: {} },
};

const FLAG_STATE = {
  live_toggleable: {
    task_aware_enabled: { enabled: false },
    dedup_enabled: { enabled: false },
    context_budget_enabled: { enabled: false },
    profiles_enabled: { enabled: false },
    shared_context_enabled: { enabled: false },
    cost_forecast_enabled: { enabled: false },
    autopilot_enabled: { enabled: false },
    episodic_memory_enabled: { enabled: false },
    audit_enabled: { enabled: false },
    orchestrator: { enabled: false },
  },
  restart_required: {
    rate_limit_enabled: { enabled: false },
  },
};

const ENTITLEMENTS = {
  current_tier: 'builder',
  features: {
    episodic_memory: { available: false, required_tier: 'business' },
    cross_agent_memory: { available: false, required_tier: 'business' },
    audit_logs: { available: false, required_tier: 'enterprise' },
    rbac: { available: false, required_tier: 'enterprise' },
  },
};

function responseBody(pathname, method) {
  if (pathname === '/health') {
    return { status: 'healthy', ready: true, version: '0.30.0', checks: {} };
  }
  if (pathname === '/stats' || pathname === '/stats-history') {
    return pathname === '/stats'
      ? STATS
      : { history: [], series: { hourly: [], daily: [], weekly: [], monthly: [] }, lifetime: {} };
  }
  if (pathname === '/config/flags' || pathname === '/admin/config/flags') {
    return method === 'POST' ? { ...FLAG_STATE, applied_live: {} } : FLAG_STATE;
  }
  if (pathname === '/entitlements') {
    return ENTITLEMENTS;
  }
  if (pathname === '/audit/events' || pathname === '/rbac/roles') {
    return pathname.endsWith('events') ? { events: [] } : { assignments: [], roles: [] };
  }
  if (pathname === '/firewall/status') {
    return { enabled: false, events: [] };
  }
  if (pathname === '/policy/status') {
    return { enabled: false, mode: 'observe', rules: [] };
  }
  if (pathname === '/v1/providers') {
    return { providers: [] };
  }
  if (pathname === '/v1/memory/query') {
    return [];
  }
  if (pathname.startsWith('/v1/sessions/')) {
    return { session_id: pathname.split('/')[3] || '', events: [] };
  }
  return {};
}

function isMockedApi(pathname) {
  return [
    '/health',
    '/stats',
    '/v1/',
    '/config/',
    '/admin/config/',
    '/audit/',
    '/rbac/',
    '/entitlements',
    '/firewall/',
    '/policy/',
  ].some((prefix) => pathname === prefix || pathname.startsWith(prefix));
}

async function installDeterministicApi(page) {
  await page.addInitScript(() => {
    window.localStorage.setItem('cutctxAdminKey', 'dashboard-audit-key');
  });

  await page.route('**/*', async (route) => {
    const url = new URL(route.request().url());
    if (!isMockedApi(url.pathname)) {
      await route.continue();
      return;
    }

    await route.fulfill({
      status: 200,
      headers: JSON_HEADERS,
      body: JSON.stringify(responseBody(url.pathname, route.request().method())),
    });
  });
}

export const test = base.extend({
  audit: async ({ page }, use, testInfo) => {
    const consoleErrors = [];
    const pageErrors = [];
    const failedRequests = [];
    const brokenAssets = [];

    await installDeterministicApi(page);
    page.on('console', (message) => {
      if (message.type() === 'error') {
        consoleErrors.push(message.text());
      }
    });
    page.on('pageerror', (error) => pageErrors.push(String(error)));
    page.on('requestfailed', (request) => {
      failedRequests.push({ url: request.url(), failure: request.failure()?.errorText || 'unknown' });
    });
    page.on('response', (response) => {
      const request = response.request();
      const assetTypes = new Set(['stylesheet', 'script', 'font', 'image']);
      if (assetTypes.has(request.resourceType()) && response.status() >= 400) {
        brokenAssets.push({ url: response.url(), status: response.status() });
      }
    });

    const viewportWidth = Number(testInfo.project.name.match(/-(\d+)$/)?.[1] || 1280);
    const audit = {
      viewportWidth,
      isMobile: viewportWidth <= 1024,
      async assertLayoutAndAccessibility() {
        await expect(page.locator('main')).toBeVisible();
        const metrics = await page.evaluate(() => ({
          viewportWidth: document.documentElement.clientWidth,
          documentWidth: Math.max(document.documentElement.scrollWidth, document.body.scrollWidth),
          activeElement: document.activeElement?.tagName || '',
          duplicateIds: [...document.querySelectorAll('[id]')]
            .map((element) => element.id)
            .filter((id, index, ids) => ids.indexOf(id) !== index),
        }));
        expect(metrics.documentWidth).toBeLessThanOrEqual(metrics.viewportWidth + 1);
        expect(metrics.duplicateIds).toEqual([]);

        const missingNames = await page.locator('button:visible, a:visible, input:visible, select:visible, textarea:visible').evaluateAll(
          (elements) => elements
            .filter((element) => !element.disabled && !element.closest('[aria-hidden="true"]'))
            .map((element) => ({
              tag: element.tagName,
              name: element.getAttribute('aria-label') || element.getAttribute('title') || element.getAttribute('placeholder') || element.labels?.[0]?.textContent?.trim() || element.textContent?.trim() || '',
            }))
            .filter(({ name }) => !name),
        );
        expect(missingNames).toEqual([]);
        await expect(page.locator('nav[aria-label="Main Navigation"]')).toBeVisible();
        await expect(page.getByRole('button', { name: 'Toggle sidebar' })).toBeVisible();
        await expect(page.getByRole('button', { name: /Switch to/ })).toBeVisible();
        await page.keyboard.press('Tab');
        expect(await page.evaluate(() => document.activeElement?.tagName)).not.toBe('BODY');
      },
      async assertClean() {
        expect(consoleErrors, 'console errors').toEqual([]);
        expect(pageErrors, 'page errors').toEqual([]);
        expect(failedRequests, 'failed requests').toEqual([]);
        expect(brokenAssets, 'broken assets').toEqual([]);
      },
    };

    await use(audit);

    const screenshotPath = testInfo.outputPath('dashboard-audit.png');
    if (!page.isClosed()) {
      await page.screenshot({ path: screenshotPath, fullPage: true });
      await testInfo.attach('dashboard-audit-screenshot', { path: screenshotPath, contentType: 'image/png' });
    }
    await testInfo.attach('dashboard-audit-events', {
      body: JSON.stringify({ consoleErrors, pageErrors, failedRequests, brokenAssets }, null, 2),
      contentType: 'application/json',
    });
  },
});

export { expect };
