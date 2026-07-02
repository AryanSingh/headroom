// Comprehensive UI audit script for the headroom/cutctx dashboard.
// Run: node audit/audit-screenshots.mjs
import { chromium } from 'playwright';
import { mkdir } from 'node:fs/promises';
import { existsSync, writeFileSync, appendFileSync } from 'node:fs';
import { resolve, dirname } from 'node:path';
import { fileURLToPath } from 'node:url';

const __dirname = dirname(fileURLToPath(import.meta.url));
const SCREENSHOT_DIR = resolve(__dirname, 'screenshots');
const REPORT_PATH = resolve(__dirname, 'screenshot-report.json');
const CONSOLE_LOG_PATH = resolve(__dirname, 'console-log.txt');
const ISSUES_PATH = resolve(__dirname, 'visual-issues.md');

if (!existsSync(SCREENSHOT_DIR)) {
  await mkdir(SCREENSHOT_DIR, { recursive: true });
}

const BASE_URL = 'http://localhost:5173';

const ROUTES = [
  { path: '/', name: 'overview' },
  { path: '/orchestrator', name: 'orchestrator' },
  { path: '/capabilities', name: 'capabilities' },
  { path: '/governance', name: 'governance' },
  { path: '/firewall', name: 'firewall' },
  { path: '/memory', name: 'memory' },
  { path: '/playground', name: 'playground' },
  { path: '/docs', name: 'docs' },
];

const VIEWPORTS = [
  { width: 1440, height: 900, name: 'desktop-1440x900' },
  { width: 1280, height: 800, name: 'desktop-1280x800' },
  { width: 768, height: 1024, name: 'tablet-768x1024' },
  { width: 390, height: 844, name: 'mobile-390x844' },
];

const consoleEntries = [];
const issues = [];
const capturedScreenshots = [];
const interactions = [];

function log(msg) {
  console.log(`[audit] ${msg}`);
}

function recordConsole(route, viewport, type, text, location) {
  consoleEntries.push({ route, viewport, type, text, location });
  appendFileSync(CONSOLE_LOG_PATH, `[${route} @ ${viewport}] [${type}] ${text}\n`);
}

function recordIssue({ route, viewport, severity, description, location, screenshotPath }) {
  issues.push({ route, viewport, severity, description, location, screenshotPath });
}

async function attachConsoleLogging(page, route, viewport) {
  page.on('console', (msg) => {
    const type = msg.type();
    if (type === 'warning' || type === 'error' || type === 'log') {
      recordConsole(route, viewport, type, msg.text(), msg.location());
    }
  });
  page.on('pageerror', (err) => {
    recordConsole(route, viewport, 'pageerror', err.message + (err.stack ? '\n' + err.stack : ''), null);
  });
  page.on('requestfailed', (req) => {
    recordConsole(route, viewport, 'requestfailed', `${req.method()} ${req.url()} - ${req.failure()?.errorText}`, null);
  });
}

async function waitForDataLoad(page) {
  // Give time for the React app to fetch /health, /stats etc via the proxy.
  try {
    await page.waitForLoadState('networkidle', { timeout: 8000 });
  } catch {}
  await page.waitForTimeout(800);
}

async function captureRoute(page, route, viewport, suffix = '') {
  const file = resolve(SCREENSHOT_DIR, `${route.name}-${viewport.name}${suffix}.png`);
  log(`Capturing ${route.path} @ ${viewport.name}${suffix}`);
  await page.screenshot({ path: file, fullPage: true });
  capturedScreenshots.push({
    route: route.path,
    routeName: route.name,
    viewport: viewport.name,
    suffix,
    file: file,
  });
  return file;
}

async function inspectLayout(page, route, viewport, screenshotPath) {
  // Inspect elements for obvious issues
  const inspection = await page.evaluate(() => {
    const out = {
      docTitle: document.title,
      bodyOverflowsX: document.documentElement.scrollWidth > window.innerWidth + 2,
      bodyScrollWidth: document.documentElement.scrollWidth,
      bodyClientWidth: document.documentElement.clientWidth,
      bodyScrollHeight: document.documentElement.scrollHeight,
      hasHorizontalScroll: window.scrollX > 0,
      rootEl: document.getElementById('root')?.scrollWidth,
      fixedElements: [],
      overflowingElements: [],
      clippedElements: [],
      imageLoadFailures: [],
    };
    const all = document.querySelectorAll('*');
    for (const el of all) {
      const r = el.getBoundingClientRect();
      if (r.right > window.innerWidth + 2 && r.width < window.innerWidth) {
        out.overflowingElements.push({
          tag: el.tagName.toLowerCase(),
          cls: el.className?.toString().slice(0, 80),
          text: (el.innerText || '').slice(0, 40),
          right: r.right,
          width: r.width,
        });
      }
      if (r.width < 20 && r.width > 0 && (el.innerText || '').length > 0) {
        out.clippedElements.push({
          tag: el.tagName.toLowerCase(),
          cls: el.className?.toString().slice(0, 80),
          text: (el.innerText || '').slice(0, 40),
        });
      }
      const style = window.getComputedStyle(el);
      if (style.position === 'fixed' || style.position === 'sticky') {
        out.fixedElements.push({
          tag: el.tagName.toLowerCase(),
          cls: el.className?.toString().slice(0, 60),
        });
      }
    }
    out.overflowingElements = out.overflowingElements.slice(0, 8);
    out.clippedElements = out.clippedElements.slice(0, 8);
    out.fixedElements = out.fixedElements.slice(0, 5);
    out.imagesBroken = Array.from(document.images).filter((img) => !img.complete || img.naturalWidth === 0).length;
    out.imageCount = document.images.length;
    return out;
  });
  // Record common issues
  if (inspection.bodyOverflowsX) {
    recordIssue({
      route: route.path,
      viewport,
      severity: 'High',
      description: `Horizontal overflow: scrollWidth=${inspection.bodyScrollWidth}, clientWidth=${inspection.bodyClientWidth}, rootEl=${inspection.rootEl}`,
      location: 'document/body',
      screenshotPath,
    });
  }
  if (inspection.imagesBroken > 0) {
    recordIssue({
      route: route.path,
      viewport,
      severity: 'Medium',
      description: `${inspection.imagesBroken}/${inspection.imageCount} broken images`,
      location: 'img',
      screenshotPath,
    });
  }
  if (inspection.overflowingElements.length > 0) {
    recordIssue({
      route: route.path,
      viewport,
      severity: 'High',
      description: `Elements overflowing viewport: ${inspection.overflowingElements.map((e) => e.tag + (e.cls ? '.' + e.cls.split(' ')[0] : '') + '(' + e.text + ')').join(', ')}`,
      location: inspection.overflowingElements[0]?.cls || 'body',
      screenshotPath,
    });
  }
  if (inspection.clippedElements.length > 0) {
    recordIssue({
      route: route.path,
      viewport,
      severity: 'Medium',
      description: `Tiny clipped elements with text: ${inspection.clippedElements.map((e) => e.tag + ':' + e.text).join(', ')}`,
      location: inspection.clippedElements[0]?.cls || 'body',
      screenshotPath,
    });
  }
  return inspection;
}

async function tryClickNav(page, targetRoute) {
  try {
    const sel = `a[href*="${targetRoute}"], a[href$="${targetRoute}"], a[href$="/"], a[href="/"]`;
    const link = await page.$(`a[href="${targetRoute}"]`);
    if (link) {
      await link.click();
      await page.waitForTimeout(700);
      return true;
    }
    return false;
  } catch (e) {
    return false;
  }
}

async function run() {
  log('Launching Chromium');
  const browser = await chromium.launch({
    headless: true,
    executablePath: '/Users/aryansingh/Library/Caches/ms-playwright/chromium_headless_shell-1223/chrome-headless-shell-mac-arm64/chrome-headless-shell',
  });
  const results = {};

  // Capture each route at desktop-1440x900 first (this is the main set)
  const desktopVp = VIEWPORTS[0];
  const context = await browser.newContext({
    viewport: { width: desktopVp.width, height: desktopVp.height },
    deviceScaleFactor: 1,
  });
  const page = await context.newPage();
  await attachConsoleLogging(page, 'init', desktopVp.name);

  // First navigate to root to set up the SPA
  log(`Initial load: ${BASE_URL}/`);
  await page.goto(BASE_URL + '/', { waitUntil: 'domcontentloaded' });
  // Pre-seed localStorage with the admin key to bypass the auth screen.
  await page.evaluate(() => {
    try { localStorage.setItem('cutctxAdminKey', 'test-admin-key'); } catch {}
  });
  await page.reload({ waitUntil: 'domcontentloaded' });
  await waitForDataLoad(page);
  // Check for auth screen
  const authVisible = await page.evaluate(() => {
    return document.body.innerText.includes('Authentication Required');
  });
  if (authVisible) {
    log('Auth screen still showing — injecting via input');
    await page.fill('input[type="password"]', 'test-admin-key');
    await page.click('button:has-text("Save & Reload")');
    await page.waitForLoadState('domcontentloaded');
    await waitForDataLoad(page);
  }

  // Capture all routes at desktop
  for (const route of ROUTES) {
    log(`Navigating to ${route.path}`);
    try {
      await page.goto(BASE_URL + route.path, { waitUntil: 'domcontentloaded' });
      await waitForDataLoad(page);
      const file = await captureRoute(page, route, desktopVp);
      results[route.name] = results[route.name] || {};
      results[route.name][desktopVp.name] = await inspectLayout(page, route, desktopVp, file);
    } catch (e) {
      log(`Error on ${route.path}: ${e.message}`);
      recordIssue({ route: route.path, viewport: desktopVp, severity: 'Critical', description: `Failed to capture: ${e.message}`, location: 'navigate', screenshotPath: null });
    }
  }

  // Theme toggle test on the overview page
  log('Testing theme toggle');
  try {
    await page.goto(BASE_URL + '/', { waitUntil: 'domcontentloaded' });
    await waitForDataLoad(page);
    const initialTheme = await page.evaluate(() => document.documentElement.classList.contains('dark') ? 'dark' : 'light');
    log(`Initial theme: ${initialTheme}`);
    const themeBtn = await page.$('button.theme-toggle, button[aria-label*="mode"]');
    if (themeBtn) {
      await themeBtn.click();
      await page.waitForTimeout(600);
      const newTheme = await page.evaluate(() => document.documentElement.classList.contains('dark') ? 'dark' : 'light');
      log(`After click theme: ${newTheme}`);
      await captureRoute(page, ROUTES[0], desktopVp, '-after-theme-toggle');
      interactions.push({ name: 'theme-toggle', from: initialTheme, to: newTheme, ok: initialTheme !== newTheme });
      if (initialTheme === newTheme) {
        recordIssue({ route: '/', viewport: desktopVp, severity: 'Medium', description: 'Theme toggle did not change theme', location: 'header.theme-toggle', screenshotPath: null });
      }
    } else {
      interactions.push({ name: 'theme-toggle', ok: false, reason: 'no theme button found' });
    }
  } catch (e) {
    interactions.push({ name: 'theme-toggle', ok: false, error: e.message });
  }

  // Capabilities toggle test
  log('Testing capabilities toggles');
  try {
    await page.goto(BASE_URL + '/capabilities', { waitUntil: 'domcontentloaded' });
    await waitForDataLoad(page);
    const toggleInfo = await page.evaluate(() => {
      // Custom toggle-switch class was used in the build
      const switches = Array.from(document.querySelectorAll('.toggle-switch, button[role="switch"]'));
      const labels = Array.from(document.querySelectorAll('label.toggle-switch'));
      return {
        count: switches.length,
        labelCount: labels.length,
        first: switches[0] ? {
          tag: switches[0].tagName,
          cls: switches[0].className?.toString(),
          html: switches[0].outerHTML.slice(0, 200),
        } : null,
      };
    });
    log(`Found ${toggleInfo.count} toggle-switch elements on /capabilities`);
    if (toggleInfo.count === 0) {
      // Fallback: find any element with role=switch or input checkbox
      const anySwitch = await page.$('input[type="checkbox"]');
      if (anySwitch) {
        const before = await anySwitch.isChecked();
        await anySwitch.click();
        await page.waitForTimeout(500);
        const after = await anySwitch.isChecked();
        await captureRoute(page, ROUTES[2], desktopVp, '-after-toggle');
        interactions.push({ name: 'capability-toggle-checkbox', before, after, ok: before !== after });
      } else {
        interactions.push({ name: 'capability-toggle', ok: false, reason: 'no toggle-switch or checkbox found', info: toggleInfo });
      }
    } else {
      // The toggle-switch is a label that wraps a hidden input checkbox
      const firstSwitchInput = await page.$('.toggle-switch input[type="checkbox"]');
      if (firstSwitchInput) {
        const before = await firstSwitchInput.isChecked();
        await firstSwitchInput.click({ force: true });
        await page.waitForTimeout(600);
        const after = await firstSwitchInput.isChecked();
        log(`First switch: ${before} → ${after}`);
        await captureRoute(page, ROUTES[2], desktopVp, '-after-toggle');
        interactions.push({ name: 'capability-toggle', before, after, ok: before !== after });
      }
    }
  } catch (e) {
    interactions.push({ name: 'capability-toggle', ok: false, error: e.message });
  }

  // Governance flag toggles
  log('Testing governance flag toggles');
  try {
    await page.goto(BASE_URL + '/governance', { waitUntil: 'domcontentloaded' });
    await waitForDataLoad(page);
    const switchCount = await page.evaluate(() => document.querySelectorAll('.toggle-switch, input[type="checkbox"]').length);
    log(`Found ${switchCount} toggles on /governance`);
    const firstSwitch = await page.$('.toggle-switch input[type="checkbox"], input[type="checkbox"]');
    if (firstSwitch) {
      const before = await firstSwitch.isChecked();
      await firstSwitch.click({ force: true });
      await page.waitForTimeout(800);
      const after = await firstSwitch.isChecked();
      log(`First governance switch: ${before} → ${after}`);
      await captureRoute(page, ROUTES[3], desktopVp, '-after-flag-click');
      interactions.push({ name: 'governance-flag', before, after, ok: before !== after });
    } else {
      interactions.push({ name: 'governance-flag', ok: false, reason: 'no flag switches found' });
    }
  } catch (e) {
    interactions.push({ name: 'governance-flag', ok: false, error: e.message });
  }

  // Firewall scan
  log('Testing firewall scan');
  try {
    await page.goto(BASE_URL + '/firewall', { waitUntil: 'domcontentloaded' });
    await waitForDataLoad(page);
    // List all buttons on the page so we know what's available
    const buttons = await page.evaluate(() => Array.from(document.querySelectorAll('button')).map((b) => ({
      text: (b.innerText || '').slice(0, 60),
      disabled: b.disabled,
    })).slice(0, 20));
    log(`Firewall buttons: ${JSON.stringify(buttons)}`);
    // Try various selectors
    const candidates = ['button:has-text("Scan")', 'button:has-text("Run scan")', 'button:has-text("Test")', 'button:has-text("Run")', 'button:has-text("Submit")', 'button:has-text("Send")', 'button:has-text("Check")'];
    let scanBtn = null;
    for (const sel of candidates) {
      const btn = await page.$(sel);
      if (btn) { scanBtn = btn; log(`Found scan button via: ${sel}`); break; }
    }
    if (scanBtn) {
      const beforeDisabled = await scanBtn.isDisabled();
      if (beforeDisabled) {
        log('Scan button disabled');
        interactions.push({ name: 'firewall-scan', ok: false, reason: 'scan button disabled' });
      } else {
        await scanBtn.click();
        await page.waitForTimeout(2000);
        await captureRoute(page, ROUTES[4], desktopVp, '-after-scan');
        interactions.push({ name: 'firewall-scan', ok: true });
      }
    } else {
      interactions.push({ name: 'firewall-scan', ok: false, reason: 'no scan button found', buttons });
    }
  } catch (e) {
    interactions.push({ name: 'firewall-scan', ok: false, error: e.message });
  }

  // Playground compression
  log('Testing playground compression');
  try {
    await page.goto(BASE_URL + '/playground', { waitUntil: 'domcontentloaded' });
    await waitForDataLoad(page);
    const tas = await page.evaluate(() => document.querySelectorAll('textarea').length);
    log(`Found ${tas} textareas on /playground`);
    const ta = await page.$('textarea');
    if (ta) {
      await ta.fill('Please summarize this article about the cutctx LLM proxy: It is a Rust-powered Python service that compresses prompts to reduce token spend, with a React dashboard for observability. The compression preserves semantic content while reducing redundant boilerplate.');
    }
    const buttons = await page.evaluate(() => Array.from(document.querySelectorAll('button')).map((b) => ({
      text: (b.innerText || '').slice(0, 60),
      disabled: b.disabled,
    })).slice(0, 20));
    log(`Playground buttons: ${JSON.stringify(buttons)}`);
    const candidates = ['button:has-text("Compress")', 'button:has-text("Run")', 'button:has-text("Submit")', 'button:has-text("Send")'];
    let runBtn = null;
    for (const sel of candidates) {
      const btn = await page.$(sel);
      if (btn) { runBtn = btn; break; }
    }
    if (runBtn) {
      const beforeDisabled = await runBtn.isDisabled();
      if (beforeDisabled) {
        interactions.push({ name: 'playground-compress', ok: false, reason: 'run button disabled' });
      } else {
        await runBtn.click();
        await page.waitForTimeout(3000);
        await captureRoute(page, ROUTES[6], desktopVp, '-after-compress');
        interactions.push({ name: 'playground-compress', ok: true });
      }
    } else {
      interactions.push({ name: 'playground-compress', ok: false, reason: 'no run button found', buttons });
    }
  } catch (e) {
    interactions.push({ name: 'playground-compress', ok: false, error: e.message });
  }

  // Test sidebar nav click from a non-root page
  log('Testing sidebar nav');
  try {
    await page.goto(BASE_URL + '/orchestrator', { waitUntil: 'domcontentloaded' });
    await waitForDataLoad(page);
    // Click "Capabilities" link
    const link = await page.$('a.nav-card[href="/capabilities"]');
    if (link) {
      await link.click();
      await page.waitForTimeout(800);
      const url = page.url();
      const onCap = url.includes('/capabilities');
      await captureRoute(page, ROUTES[2], desktopVp, '-after-nav-click');
      interactions.push({ name: 'nav-click', from: '/orchestrator', to: url, ok: onCap });
    } else {
      interactions.push({ name: 'nav-click', ok: false, reason: 'no nav link' });
    }
  } catch (e) {
    interactions.push({ name: 'nav-click', ok: false, error: e.message });
  }

  await context.close();

  // Capture additional viewports for the layout-sensitive pages
  for (const vp of VIEWPORTS.slice(1)) {
    log(`\n=== Viewport ${vp.name} ===`);
    const ctx = await browser.newContext({ viewport: { width: vp.width, height: vp.height } });
    const p = await ctx.newPage();
    await attachConsoleLogging(p, 'multi', vp.name);
    // Pre-seed localStorage with the admin key so we bypass the auth screen
    await p.addInitScript(() => {
      try { localStorage.setItem('cutctxAdminKey', 'test-admin-key'); } catch {}
    });
    for (const route of ROUTES) {
      try {
        await p.goto(BASE_URL + route.path, { waitUntil: 'domcontentloaded' });
        await waitForDataLoad(p);
        const file = await captureRoute(p, route, vp);
        results[route.name] = results[route.name] || {};
        results[route.name][vp.name] = await inspectLayout(p, route, vp, file);
      } catch (e) {
        log(`Error on ${route.path} @ ${vp.name}: ${e.message}`);
        recordIssue({ route: route.path, viewport: vp, severity: 'Critical', description: `Failed to capture: ${e.message}`, location: 'navigate', screenshotPath: null });
      }
    }
    await ctx.close();
  }

  await browser.close();
  log('Browser closed');

  // Save report
  writeFileSync(REPORT_PATH, JSON.stringify({
    screenshots: capturedScreenshots,
    issues,
    consoleEntries: consoleEntries.slice(0, 200),
    interactions,
  }, null, 2));
  log(`Report saved to ${REPORT_PATH}`);
  log(`Screenshots: ${capturedScreenshots.length}`);
  log(`Issues: ${issues.length}`);
  log(`Console entries: ${consoleEntries.length}`);
  log(`Interactions: ${interactions.length}`);
}

run().catch((e) => {
  console.error('Audit script crashed:', e);
  process.exit(1);
});
