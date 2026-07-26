import assert from 'node:assert/strict';
import { readFileSync } from 'node:fs';
import { resolve } from 'node:path';
import test from 'node:test';

const dashboardRoot = resolve(import.meta.dirname, '..');
const pages = ['Memory', 'Replay', 'Playground', 'Docs', 'Capabilities'];

for (const name of pages) {
  test(`${name} uses shared page-stack and PageHeader`, () => {
    const source = readFileSync(resolve(dashboardRoot, `src/pages/${name}.jsx`), 'utf8');
    assert.match(source, /className=["'][^"']*\bpage-stack\b/);
    assert.match(source, /<PageHeader[\s>]/);
  });
}
