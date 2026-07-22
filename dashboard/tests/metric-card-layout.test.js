import assert from 'node:assert/strict';
import { readFileSync } from 'node:fs';
import { resolve } from 'node:path';
import test from 'node:test';

const dashboardRoot = resolve(import.meta.dirname, '..');
const overviewSource = readFileSync(resolve(dashboardRoot, 'src/pages/Overview.jsx'), 'utf8');
const styles = readFileSync(resolve(dashboardRoot, 'src/index.css'), 'utf8');

test('MetricCard groups primary and supporting content for narrow layouts', () => {
  assert.match(overviewSource, /className="metric-primary"/);
  assert.match(overviewSource, /className="metric-supporting"/);
  assert.match(styles, /\.metric-primary,\s*\.metric-supporting\s*\{\s*display: contents;/);
  assert.match(styles, /@media \(max-width: 640px\)[\s\S]*\.metric-card\s*\{[\s\S]*grid-template-columns:/);
});
