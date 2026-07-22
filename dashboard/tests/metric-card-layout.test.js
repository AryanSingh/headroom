import assert from 'node:assert/strict';
import { readFileSync } from 'node:fs';
import { resolve } from 'node:path';
import test from 'node:test';

const dashboardRoot = resolve(import.meta.dirname, '..');
const overviewSource = readFileSync(resolve(dashboardRoot, 'src/pages/Overview.jsx'), 'utf8');
const styles = readFileSync(resolve(dashboardRoot, 'src/index.css'), 'utf8');
const desktopStyles = styles.slice(0, styles.indexOf('@media (max-width: 640px)'));
const wideDesktopStyles = styles.slice(0, styles.indexOf('@media (max-width: 1200px)'));

test('overview uses independent adaptive column stacks without grid-row gaps', () => {
  assert.match(overviewSource, /className="metric-primary"/);
  assert.match(overviewSource, /className="metric-supporting"/);
  assert.match(desktopStyles, /\.metric-primary,\s*\.metric-supporting\s*\{\s*display: grid;/);
  assert.match(wideDesktopStyles, /\.metric-grid-four\s*\{\s*grid-template-columns: repeat\(2, minmax\(0, 1fr\)\);/);
  assert.match(overviewSource, /className="overview-secondary-stack"/);
  assert.match(overviewSource, /className="overview-side-stack"/);
  assert.match(styles, /\.overview-secondary-stack,\s*\.overview-side-stack\s*\{\s*display: grid;/);
  assert.match(styles, /\.overview-bottom-grid\s*\{[\s\S]*grid-template-columns: repeat\(auto-fit, minmax\(min\(100%, 360px\), 1fr\)\);/);
  assert.match(styles, /@media \(max-width: 640px\)[\s\S]*\.metric-card\s*\{[\s\S]*grid-template-columns:/);
});
