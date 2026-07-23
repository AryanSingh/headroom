import assert from 'node:assert/strict';
import { readFileSync } from 'node:fs';
import test from 'node:test';

test('license cards offer a safe local text download', () => {
  const portal = readFileSync(new URL('../assets/licenses.js', import.meta.url), 'utf8');
  const downloadFunction = portal.match(/function downloadLicense\(license\) \{[\s\S]*?\n\}/)?.[0] || '';

  assert.match(downloadFunction, /new Blob\(\[licenseText\], \{ type: 'text\/plain;charset=utf-8' \}\)/);
  assert.match(downloadFunction, /anchor\.download = `\$\{license\.tier\}-cutctx-license\.txt`/);
  assert.match(downloadFunction, /License key: \$\{license\.key\}/);
  assert.doesNotMatch(downloadFunction, /accessToken|refresh_token|payment_id|customer_id/);
});
