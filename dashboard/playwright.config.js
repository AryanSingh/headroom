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
      testIgnore: [auditSpec, /orchestrator-live\.spec\.js/],
      // The orchestration suite contains deliberate pending-request and
      // timeout cases. Running many copies against one Vite process makes
      // lifecycle assertions CPU-contention dependent, so keep this project
      // deterministic while the isolated live-proxy project remains separate.
      workers: 1,
      use: { ...devices['Desktop Chrome'] },
    },
    {
      name: 'live-proxy',
      testMatch: /orchestrator-live\.spec\.js/,
      workers: 1,
      use: { ...devices['Desktop Chrome'] },
    },
    ...auditViewports.map(({ name, width, height }) => ({
      name,
      testMatch: auditSpec,
      use: { ...devices['Desktop Chrome'], viewport: { width, height } },
    })),
  ],
  webServer: [
    {
      command: 'uv run python ../tests/fixtures/orchestration_e2e_server.py --port 48787',
      url: 'http://127.0.0.1:48787/health',
      // Reusing a stray/stale server hides startup failures and can point
      // tests at the wrong fixture. Only reuse locally; CI always starts fresh.
      reuseExistingServer: !process.env.CI,
      stdout: 'pipe',
      stderr: 'pipe',
      timeout: 120_000,
    },
    {
      command: 'CUTCTX_PROXY_PORT=48787 CUTCTX_ADMIN_API_KEY=test-admin-key-for-live-e2e npm run dev -- --port 4123',
      url: 'http://localhost:4123/dashboard',
      reuseExistingServer: !process.env.CI,
      stdout: 'pipe',
      stderr: 'pipe',
      timeout: 30_000,
    },
  ],
});
