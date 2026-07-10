import { expect, ROUTE_INVENTORY, test } from './fixtures/dashboard-audit.js';

const expectedHrefs = ROUTE_INVENTORY.map(({ path }) => `/dashboard${path === '/' ? '' : path}`);

test.describe('Dashboard audit matrix', () => {
  test.describe.configure({ mode: 'parallel' });

  test('exposes the complete route inventory', async ({ page, audit }) => {
    await page.goto('/dashboard', { waitUntil: 'domcontentloaded' });
    await expect(page.locator('.topbar-title-row h2')).toHaveText('Dashboard');

    const links = await page.locator('nav[aria-label="Main Navigation"] a').evaluateAll(
      (elements) => elements.map((element) => ({ href: element.getAttribute('href'), label: element.textContent?.trim() })),
    );
    expect(links).toEqual(ROUTE_INVENTORY.map(({ path, label }) => ({
      href: `/dashboard${path === '/' ? '' : path}`,
      label,
    })));
    expect(new Set(links.map(({ href }) => href)).size).toBe(10);
    await audit.assertLayoutAndAccessibility();
    await audit.assertClean();
  });

  for (const route of ROUTE_INVENTORY) {
    test(`renders ${route.path} without audit defects`, async ({ page, audit }) => {
      await page.goto(`/dashboard${route.path === '/' ? '' : route.path}`, { waitUntil: 'domcontentloaded' });
      await expect(page.locator('.topbar-title-row h2')).toHaveText(route.label);

      const links = await page.locator('nav[aria-label="Main Navigation"] a').evaluateAll(
        (elements) => elements.map((element) => element.getAttribute('href')),
      );
      expect(links).toEqual(expectedHrefs);
      await audit.assertLayoutAndAccessibility();

      if (route.path === '/governance') {
        const search = page.locator('input[aria-label="Search"]');
        await page.keyboard.press('/');
        await expect(search).toBeFocused();
      }

      if (audit.isMobile) {
        const toggle = page.getByRole('button', { name: 'Toggle sidebar' });
        await toggle.click();
        await expect(page.locator('.sidebar-shell')).toHaveClass(/open/);
        await page.keyboard.press('Escape');
        await expect(page.locator('.sidebar-shell')).not.toHaveClass(/open/);
        await expect(toggle).toBeFocused();
      }

      await audit.assertClean();
    });
  }
});
