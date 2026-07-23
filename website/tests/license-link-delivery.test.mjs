import assert from 'node:assert/strict';
import { readFileSync } from 'node:fs';
import test from 'node:test';

test('CutCtx licenses request branded email delivery through the secure backend', () => {
  const portal = readFileSync(new URL('../assets/licenses.js', import.meta.url), 'utf8');

  assert.match(portal, /functions\/v1\/request-license-link/);
  assert.doesNotMatch(portal, /auth\/v1\/otp/);
  assert.doesNotMatch(portal, /create_user/);
});
