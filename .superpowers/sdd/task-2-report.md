# Task 2 report: newest-request-wins dashboard refresh

## Scope

Changed only the assigned dashboard files:

- `dashboard/src/lib/dashboard-context.jsx`
- `dashboard/src/pages/Orchestrator.jsx`
- `dashboard/e2e/orchestrator.spec.js`

This report is the requested delivery artifact.

## Implementation

- Current stats/health loading uses a monotonically increasing generation. Only the newest generation can publish `stats`, `health`, `error`, `refreshError`, `lastUpdated`, and optional config-flag state.
- `loading` remains initial-only. A committed polling snapshot can also release the initial loading shell when it supersedes a delayed initial request.
- Explicit refreshes expose `refreshing`; a newer current-data completion clears it when it supersedes the outstanding explicit generation, preventing it from being stranded.
- `refresh()` returns a structured `{ ok, committed, stale, error, generation, stats, health }` result and starts history loading without awaiting it.
- History and optional config-flag work no longer delay mode confirmation.
- Mode POSTs require `applied_live.orchestrator_mode.mode` to exactly equal the requested value. Missing or mismatched acknowledgement is a mutation error. After valid acknowledgement, optimistic mode remains active until the newest committed stats exactly match; failed or stale refreshes display a non-destructive pending-confirmation warning.
- Refreshing existing data no longer sets `loading`, so Orchestrator stays mounted during a delayed mode refresh.

## RED evidence

Command:

```sh
rtk proxy env CI=true PAGER=cat npx playwright test e2e/orchestrator.spec.js --project=chromium --grep 'keeps the established page|requires an exact acknowledgement'
```

Result: 2 failed. The delayed-refresh case failed because `.page-stack` disappeared, and the acknowledgement case failed because no acknowledgement error was rendered.

Command:

```sh
rtk proxy env CI=true PAGER=cat npx playwright test e2e/orchestrator.spec.js --project=chromium --workers=1 --grep 'publishes a polling snapshot'
```

Result: 1 failed. The delayed-initial/polling test timed out waiting for the `Off` control because the old initial-only `finally` left `loading` true after polling superseded it.

## GREEN evidence

Command:

```sh
rtk proxy env CI=true PAGER=cat npx playwright test e2e/orchestrator.spec.js --project=chromium --workers=1 --grep 'publishes a polling snapshot|keeps the established page|requires an exact acknowledgement' && rtk proxy env CI=true PAGER=cat npm run lint && rtk proxy env CI=true PAGER=cat npm run build
```

Result:

- Playwright: 3 passed (13.5s).
- ESLint: exit 0 with `--max-warnings=0`.
- Vite production build: exit 0.

An earlier focused mocked run also passed the baseline POST coverage together with the two mode regressions: 3 passed (8.9s).

## Review and concerns

Spec-quality review against `task-2-brief.md` and the controller follow-up found and resolved the two important lifecycle gaps: a superseded initial request could strand `loading`, and an explicit refresh superseded by polling could strand `refreshing`.

The suite is mocked browser coverage; no live proxy was required or started persistently. Dev-mode test output still includes the intentional console error for the missing-acknowledgement case; it is asserted behavior, not a test failure.

## Review follow-up fixes

- Added `committedGeneration` to the provider. Optimistic mode is now scoped to the committed generation that existed when the request started. A later committed snapshot—whether it confirms the requested mode or reports a different authoritative backend mode—wins over stale optimism.
- Added deterministic mismatched-acknowledgement coverage.
- Added deterministic valid-acknowledgement coverage for a stale successful stats response, a newer exact confirmation, and a later conflicting authoritative snapshot.
- Added deterministic initial + polling + explicit-refresh coverage. Stats and health completions for initial and explicit generations are held until after the newer polling generation publishes; releasing them as failures does not change the published timestamp, refresh error, mode, or refreshing flag.

### Follow-up RED/GREEN evidence

RED command:

```sh
rtk proxy env CI=true PAGER=cat npx playwright test e2e/orchestrator.spec.js --project=chromium --workers=1 --grep 'rejects a mismatched|newest committed stats replace'
```

The stale-optimism regression failed before the committed-generation change: after a newer backend snapshot changed to `aggressive`, the page continued to present `Routing balanced`.

GREEN bounded command:

```sh
rtk proxy env CI=true PAGER=cat timeout 30 npx playwright test e2e/orchestrator.spec.js --project=chromium --workers=1 --timeout=12000 --grep 'only the newest initial'
```

Result: 1 passed (13.1s); the outer process bound completed without leaving a test server or browser process.
