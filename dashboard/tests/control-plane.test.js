import assert from 'node:assert/strict';
import { readFileSync } from 'node:fs';
import { resolve } from 'node:path';
import test from 'node:test';

const dashboardRoot = resolve(import.meta.dirname, '..');
const orchestrator = readFileSync(resolve(dashboardRoot, 'src/pages/Orchestrator.jsx'), 'utf8');
const governance = readFileSync(resolve(dashboardRoot, 'src/pages/Governance.jsx'), 'utf8');
const firewall = readFileSync(resolve(dashboardRoot, 'src/pages/Firewall.jsx'), 'utf8');
const styles = readFileSync(resolve(dashboardRoot, 'src/index.css'), 'utf8');

test('Orchestrator surfaces an explicit live control-plane status', () => {
  assert.match(orchestrator, /control-plane-status/);
  assert.match(orchestrator, /Live|Applied live|applied_live/);
  assert.match(styles, /\.control-plane-status\s*\{/);
});

test('Governance and Security share page-stack + PageHeader shell', () => {
  assert.match(governance, /className=["']page-stack["']/);
  assert.match(governance, /<PageHeader/);
  assert.match(firewall, /className=["']page-stack["']/);
  assert.match(firewall, /<PageHeader/);
});
