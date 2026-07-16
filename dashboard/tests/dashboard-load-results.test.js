import assert from 'node:assert/strict';
import test from 'node:test';

import { resolveDashboardLoadResults } from '../src/lib/dashboard-load-results.js';

const fulfilled = (value) => ({ status: 'fulfilled', value });
const rejected = (reason) => ({ status: 'rejected', reason });

test('prioritizes an authentication failure over another request failure', () => {
  const unauthorized = Object.assign(new Error('/stats returned 401'), { status: 401 });
  const unavailable = Object.assign(new Error('/health returned 502'), { status: 502 });

  assert.throws(
    () => resolveDashboardLoadResults(rejected(unauthorized), rejected(unavailable)),
    error => error === unauthorized,
  );
});

test('prioritizes a health authentication failure over a statistics failure', () => {
  const statsFailure = Object.assign(new Error('/stats returned 500'), { status: 500 });
  const unauthorized = Object.assign(new Error('/health returned 401'), { status: 401 });

  assert.throws(
    () => resolveDashboardLoadResults(rejected(statsFailure), rejected(unauthorized)),
    error => error === unauthorized,
  );
});

test('preserves statistics-first error selection without an authentication failure', () => {
  const statsFailure = Object.assign(new Error('/stats returned 500'), { status: 500 });
  const healthFailure = Object.assign(new Error('/health returned 502'), { status: 502 });

  assert.throws(
    () => resolveDashboardLoadResults(rejected(statsFailure), rejected(healthFailure)),
    error => error === statsFailure,
  );
});

test('returns both payloads when the requests succeed', () => {
  const statsData = { summary: { total_requests: 1 } };
  const healthData = { status: 'ok', ready: true };

  assert.deepEqual(
    resolveDashboardLoadResults(fulfilled(statsData), fulfilled(healthData)),
    { statsData, healthData },
  );
});
