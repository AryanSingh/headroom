import assert from 'node:assert/strict';
import { readFileSync } from 'node:fs';
import { resolve } from 'node:path';
import test from 'node:test';

const dashboardRoot = resolve(import.meta.dirname, '..');
const overview = readFileSync(resolve(dashboardRoot, 'src/pages/Overview.jsx'), 'utf8');
const savings = readFileSync(resolve(dashboardRoot, 'src/pages/Savings.jsx'), 'utf8');
const styles = readFileSync(resolve(dashboardRoot, 'src/index.css'), 'utf8');

test('Overview leads with a savings hero metric', () => {
  assert.match(overview, /className=["'][^"']*savings-hero/);
  assert.match(overview, /metric-panel/);
  assert.match(styles, /\.savings-hero\s*\{/);
  // Money saved appears before Tokens saved in the hero reading order.
  const moneyIdx = overview.indexOf('label="Money saved"');
  const tokensIdx = overview.indexOf('label="Tokens saved"');
  assert.ok(moneyIdx > 0 && tokensIdx > 0, 'expected money and tokens metric labels');
  assert.ok(moneyIdx < tokensIdx, 'Money saved should lead Tokens saved');
});

test('Savings page uses command-center page stack and panel language', () => {
  assert.match(savings, /className=["']page-stack["']/);
  assert.match(savings, /PageHeader|page-header|eyebrow/);
  assert.match(styles, /\.savings-hero\s*\{[\s\S]*grid-column/);
});
