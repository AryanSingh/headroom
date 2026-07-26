import assert from 'node:assert/strict';
import { readFileSync } from 'node:fs';
import { resolve } from 'node:path';
import test from 'node:test';

const dashboardRoot = resolve(import.meta.dirname, '..');
const styles = readFileSync(resolve(dashboardRoot, 'src/index.css'), 'utf8');
const html = readFileSync(resolve(dashboardRoot, 'index.html'), 'utf8');

function cssVarBlock(selector) {
  const match = styles.match(new RegExp(`${selector.replace(/[.*+?^${}()|[\]\\]/g, '\\$&')}\\s*\\{([\\s\\S]*?)\\n\\}`));
  assert.ok(match, `expected CSS block for ${selector}`);
  return match[1];
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
