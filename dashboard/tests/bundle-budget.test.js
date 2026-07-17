import assert from 'node:assert/strict';
import { readdirSync, statSync } from 'node:fs';
import { resolve } from 'node:path';
import { spawnSync } from 'node:child_process';
import test from 'node:test';

const dashboardRoot = resolve(import.meta.dirname, '..');
// Match Vite's 500 kB warning threshold rather than silently accepting it as
// 500 KiB.
const maxJavaScriptChunkBytes = 500_000;

test('production JavaScript chunks stay within the 500 kB bundle budget', () => {
  const build = spawnSync('npm', ['run', 'build'], {
    cwd: dashboardRoot,
    encoding: 'utf8',
  });
  assert.equal(build.status, 0, build.stderr || build.stdout);

  const assetsDir = resolve(dashboardRoot, 'dist/assets');
  const oversizedChunks = readdirSync(assetsDir)
    .filter((file) => file.endsWith('.js'))
    .map((file) => ({ file, bytes: statSync(resolve(assetsDir, file)).size }))
    .filter(({ bytes }) => bytes > maxJavaScriptChunkBytes);

  assert.deepEqual(oversizedChunks, []);
});
