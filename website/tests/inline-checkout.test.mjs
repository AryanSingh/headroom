import assert from 'node:assert/strict';
import { readFileSync } from 'node:fs';
import test from 'node:test';

const pricing = readFileSync(new URL('../pricing/index.html', import.meta.url), 'utf8');

test('CutCtx pricing renders a database-backed inline checkout instead of a PitchToShip billing link', () => {
  assert.match(pricing, /data-plan-price="starter"/);
  assert.match(pricing, /data-plan-select="starter"/);
  assert.match(pricing, /id="cutctx-checkout"/);
  assert.doesNotMatch(pricing, /pitchtoship\.com\/billing/);
  assert.match(pricing, /\/assets\/pricing\.js/);
});

test('CutCtx checkout loads catalog data and verifies payment without a cross-site handoff', () => {
  const checkout = readFileSync(new URL('../assets/pricing.js', import.meta.url), 'utf8');
  assert.match(checkout, /functions\/v1\/\$\{path\}/);
  assert.match(checkout, /request\('list-plans'/);
  assert.match(checkout, /request\('create-order'/);
  assert.match(checkout, /request\('verify-payment'/);
  assert.match(checkout, /checkout\.razorpay\.com\/v1\/checkout\.js/);
  assert.match(checkout, /window\.location\.assign\(licensePortalUrl\(\)\)/);
});
