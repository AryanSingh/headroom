import assert from 'node:assert/strict';
import { readFileSync } from 'node:fs';
import { resolve } from 'node:path';
import test from 'node:test';

const dashboardRoot = resolve(import.meta.dirname, '..');
const pageHeader = readFileSync(resolve(dashboardRoot, 'src/components/PageHeader.jsx'), 'utf8');
const statePanel = readFileSync(resolve(dashboardRoot, 'src/components/StatePanel.jsx'), 'utf8');
const styles = readFileSync(resolve(dashboardRoot, 'src/index.css'), 'utf8');

test('PageHeader marks the title for display typography', () => {
  assert.match(pageHeader, /className=["']page-header-title["']/);
  assert.match(styles, /\.page-header-title\s*\{[\s\S]*font-family:\s*var\(--font-display\)/);
});

test('StatePanel exposes empty and error tone contracts', () => {
  assert.match(statePanel, /state-panel-\$\{tone\}/);
  assert.match(statePanel, /tone === 'error' \? 'alert'/);
  assert.match(styles, /\.state-panel-empty\b/);
  assert.match(styles, /\.state-panel-error\b/);
});

test('metric panels prefer border elevation over glow', () => {
  assert.match(styles, /\.metric-card,\s*\.metric-panel\b|\.metric-panel\b/);
  assert.doesNotMatch(styles, /\.metric-card:hover\s*\{[^}]*box-shadow:\s*var\(--shadow-glow\)/);
});
