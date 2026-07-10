import { defineConfig, devices } from '@playwright/test';

const auditSpec = /dashboard-audit\.spec\.js/;
const auditViewports = [
  { name: 'dashboard-audit-375', width: 375, height: 812 },
  { name: 'dashboard-audit-768', width: 768, height: 1024 },
  { name: 'dashboard-audit-1280', width: 1280, height: 900 },
  { name: 'dashboard-audit-1720', width: 1720, height: 1400 },
];

export default defineConfig({
  testDir: './e2e',
  fullyParallel: true,
  reporter: 'list',
  outputDir: process.env.CUTCTX_DASHBOARD_AUDIT_OUTPUT_DIR || 'screenshots/dashboard-audit/playwright',
  use: {
    baseURL: 'http://localhost:4123',
    trace: 'on-first-retry',
  },
  projects: [
    {
      name: 'chromium',
      testIgnore: auditSpec,
      use: { ...devices['Desktop Chrome'] },
    },
    ...auditViewports.map(({ name, width, height }) => ({
      name,
      testMatch: auditSpec,
      use: { ...devices['Desktop Chrome'], viewport: { width, height } },
    })),
  ],
  webServer: {
    command: 'npm run dev -- --port 4123',
    url: 'http://localhost:4123',
    reuseExistingServer: true,
  },
});
