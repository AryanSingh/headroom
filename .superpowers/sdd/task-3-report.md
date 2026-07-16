# Task 3 Report — Fetch timeout composition and Routing Studio lifecycle

## Scope

Implemented only the Task 3 dashboard files plus this required report. Existing unrelated workspace changes were preserved.

## RED evidence

1. Initial Node RED command:

   ```sh
   CI=true rtk npm run test
   ```

   Result: failed because the test script initially targeted the `tests` directory directly, which Node interpreted as a module. The script was narrowed to the explicit test file before rerunning.

2. Required Node RED command:

   ```sh
   CI=true rtk npm run test
   ```

   Result: failed with `ERR_MODULE_NOT_FOUND` for `dashboard/src/lib/fetch-with-timeout.js`. This established the missing reusable timeout helper before any production implementation.

3. Focused browser RED command:

   ```sh
   CI=true rtk npx playwright test e2e/orchestrator.spec.js --grep "times out contract loading|keeps the newest contract-load|upserts a saved starter" --project=chromium
   ```

   Result: `PASS (2) FAIL (1)`. The timeout/Retry case failed after 12 seconds because no alert containing `Request timed out after 10000ms` existed in the pre-change UI.

## Implementation

- Added `fetchWithTimeout()` and `TimeoutError`.
  - Already-aborted caller signals reject without initiating fetch or a timer.
  - Caller cancellation preserves the caller's abort reason.
  - Only the helper's own timer becomes `TimeoutError`.
  - Timer and caller abort listener are cleaned up after success, HTTP response, caller cancellation, and timeout.
- Routed `listContracts({ signal })` through the helper with a 10,000 ms deadline and retained `cache: "no-store"`.
- Added monotonic load tokens and abort controllers in Routing Studio.
  - A new load aborts the preceding load.
  - Success, failure, and finalization update state only when their token is current.
  - Expected request aborts are silent.
  - Load errors are distinct from action errors and show a Retry control.
- Save reconciliation now replaces an existing contract matching `(id, version)` or appends only when no such entry exists. Failed saves, including revision conflicts, leave list, draft, and revision untouched.

## GREEN evidence

Final bounded validation command:

```sh
CI=true rtk npm run test && CI=true rtk npm run lint && CI=true rtk npm run build && CI=true rtk npx playwright test e2e/orchestrator.spec.js --grep "times out contract loading|keeps the newest contract-load|upserts a saved starter" --project=chromium
```

Result:

- Node unit tests: `7` passed, `0` failed.
- ESLint: exited successfully with zero warnings/errors.
- Vite production build: exited successfully.
- Focused Playwright: `PASS (3) FAIL (0)` in 14.7 seconds.

The Vite build emitted its existing chunk-size advisory for a 500.19 kB JavaScript bundle; it is not caused by this Task 3 change and did not fail the build.

## Spec-quality review

Reviewed the implementation against the Task 3 brief after the initial GREEN run. One Important finding was corrected: the timed `listContracts` route had omitted the prior `cache: "no-store"` request option. It was restored, and the complete bounded GREEN command above was rerun successfully. No unresolved Critical or Important findings remain.

## Changed files

- `dashboard/src/lib/fetch-with-timeout.js`
- `dashboard/tests/fetch-with-timeout.test.js`
- `dashboard/package.json`
- `dashboard/src/components/routing-studio/api.js`
- `dashboard/src/components/routing-studio/RoutingStudio.jsx`
- `dashboard/e2e/orchestrator.spec.js`
- `.superpowers/sdd/task-3-report.md`

## Concerns

- The browser lifecycle tests are focused rather than the entire dashboard Playwright suite, per the bounded validation scope.
- The production build chunk-size advisory remains a pre-existing optimization consideration.
