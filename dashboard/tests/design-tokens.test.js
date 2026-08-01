import assert from 'node:assert/strict';
import { readFileSync } from 'node:fs';
import { resolve } from 'node:path';
import test from 'node:test';

const dashboardRoot = resolve(import.meta.dirname, '..');
const styles = readFileSync(resolve(dashboardRoot, 'src/index.css'), 'utf8');
const html = readFileSync(resolve(dashboardRoot, 'index.html'), 'utf8');
const visualIdentityE2e = readFileSync(resolve(dashboardRoot, 'e2e/visual-identity.spec.js'), 'utf8');

function cssVarBlock(selector) {
  const match = styles.match(new RegExp(`${selector.replace(/[.*+?^${}()|[\]\\]/g, '\\$&')}\\s*\\{([\\s\\S]*?)\\n\\}`));
  assert.ok(match, `expected CSS block for ${selector}`);
  return match[1];
}

function relativeLuminance(hex) {
  const channels = hex.match(/[0-9a-f]{2}/gi).map((value) => Number.parseInt(value, 16) / 255);
  const linear = channels.map((value) => (
    value <= 0.04045 ? value / 12.92 : ((value + 0.055) / 1.055) ** 2.4
  ));
  return (0.2126 * linear[0]) + (0.7152 * linear[1]) + (0.0722 * linear[2]);
}

function contrastRatio(foreground, background) {
  const [lighter, darker] = [relativeLuminance(foreground), relativeLuminance(background)]
    .sort((a, b) => b - a);
  return (lighter + 0.05) / (darker + 0.05);
}

test('index.html loads Sora and IBM Plex font families', () => {
  assert.match(html, /fonts\.googleapis\.com/);
  assert.match(html, /Sora/);
  assert.match(html, /IBM\+Plex\+Sans|IBM Plex Sans/);
  assert.match(html, /IBM\+Plex\+Mono|IBM Plex Mono/);
});

test('design tokens use Context Command Center identity', () => {
  const root = cssVarBlock(':root');
  assert.match(root, /--font-display:\s*['"]?Sora/);
  assert.match(root, /--font-body:\s*['"]?['"]?IBM Plex Sans/);
  assert.match(root, /--font-mono:\s*['"]?['"]?IBM Plex Mono/);
  assert.doesNotMatch(root, /--font-body:[^;]*Inter/);

  const dark = cssVarBlock('.dark');
  assert.match(dark, /--surface-0:\s*#090A0E/i);
  assert.match(dark, /--accent:\s*#1FCBAA/i);

  const light = cssVarBlock('.light');
  assert.match(light, /--accent:\s*#0F766E/i);
});

test('motion respects prefers-reduced-motion', () => {
  assert.match(styles, /@media\s*\(prefers-reduced-motion:\s*reduce\)/);
});

test('visual identity E2E keeps documentation screenshots read-only', () => {
  assert.doesNotMatch(visualIdentityE2e, /docs\/screenshots/);
});

test('dark tertiary text clears WCAG AA on panel surfaces', () => {
  const dark = cssVarBlock('.dark');
  const tertiary = dark.match(/--text-tertiary:\s*(#[0-9a-f]{6})/i)?.[1];
  const panel = dark.match(/--surface-1:\s*(#[0-9a-f]{6})/i)?.[1];

  assert.ok(tertiary);
  assert.ok(panel);
  assert.ok(
    contrastRatio(tertiary, panel) >= 4.5,
    `${tertiary} on ${panel} must have at least 4.5:1 contrast`,
  );
});
