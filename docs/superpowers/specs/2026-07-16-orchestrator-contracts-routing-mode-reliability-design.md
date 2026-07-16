# Orchestrator Contracts and Routing Mode Reliability

## Objective

Make the authenticated Orchestrator dashboard behave as a responsive control plane:

- an empty installation exposes one editable Implementation starter contract;
- contract loading cannot remain indefinite and can be retried;
- switching Off, Balanced, or Aggressive remains visible while backend data refreshes;
- confirmed backend state replaces optimistic state without remounting the feature;
- API, persistence, UI, error, cleanup, and concurrent refresh behavior are covered by repeatable tests.

## Confirmed failure modes

The routing-mode write is not failing. Live Chrome reproduction changed Aggressive to Balanced, and the backend reported `balanced`, preset `codex-gpt54mini-high`, with 10 configured routes. The apparent failure happens afterward: `DashboardDataProvider.refresh()` sets global `loading=true`, and `Orchestrator` replaces the entire feature with a loading panel. During reproduction, `/stats?cached=1` took about 11.8 seconds and `/health` took about 13.4 seconds.

The contracts endpoint is also healthy. Once Routing Studio mounted, `GET /v1/orchestration/contracts` returned HTTP 200 in about 649 ms. It returned an empty collection because the durable store, legacy roles, and bindings are all empty. Routing Studio is mounted only after the unrelated global stats/health gate completes, and its request has no timeout or Retry action.

## Architecture

### Initial load versus background refresh

`DashboardDataProvider` will retain `loading` as an initial-load signal only. A new `refreshing` signal will describe later polling or explicit refresh work. Background refreshes will preserve the last successful `stats`, `health`, and feature components instead of replacing the page.

The existing `refresh()` interface will continue to return a promise. It will refresh current dashboard data without setting initial `loading` back to true. History refresh remains independently represented by `historyLoading`.

Fatal load errors will block the Orchestrator only when no usable stats snapshot exists. A refresh failure after successful initial data will keep the feature mounted and expose a non-destructive warning.

### Routing mode state flow

The mode selector remains optimistic:

1. set the selected mode locally;
2. POST `{"orchestrator_mode":"<mode>"}` to `/config/flags`;
3. verify the response acknowledges that mode;
4. refresh dashboard data in the background;
5. clear optimistic state after the refreshed backend mode is available.

The selector remains visible throughout. It is disabled only while its own mutation is active. A failed POST restores the last confirmed backend mode and displays the existing actionable error.

### First-run starter contract

The backend will own the starter contract so all API consumers see the same state.

When the durable contract store has revision `0`, contains no contracts, and legacy role conversion produces no contracts, `OrchestrationService.list_contracts()` will return one synthesized starter:

- id: `implementation`
- name: `Implementation`
- version: `1`
- state: `draft`
- template: `implementation`
- task type and role aliases for implementation work
- canonical baseline model `openai:gpt-5.4-mini`
- bounded quality, cost, latency, retry, fallback, and evidence defaults matching the current Routing Studio contract schema

The synthesized contract does not increment the store revision and is not written to disk. Saving it through the existing draft endpoint with expected revision `0` creates the first durable version and increments revision to `1`. Once any durable contract exists, only durable contracts are returned.

### Contract loading and recovery

`routingStudioApi()` will support a bounded `timeoutMs` option and caller cancellation. It will compose caller cancellation with an internal timeout, clean up listeners and timers, and normalize timeout errors into a user-facing message.

Routing Studio will move initial contract loading into a reusable function. It will:

- cancel an earlier in-flight load before retrying;
- ignore stale completions;
- clear loading in all terminal paths;
- show a dedicated error panel with Retry;
- preserve the rest of the Orchestrator;
- abort work on unmount.

The normal empty-state component remains as a defensive fallback, although the first-run backend starter means a healthy empty installation will usually show the starter editor.

## Error and concurrency behavior

- A timed-out contracts request never leaves a permanent spinner.
- Retrying aborts the prior request and only the newest response may update state.
- Unmounting aborts outstanding contract work.
- Repeated mode clicks are prevented while a mode mutation is active.
- Periodic dashboard polling and explicit mode refresh may overlap without resetting initial loading or unmounting child studios.
- A background stats/health error does not discard the last successful mode or contract UI.
- Contract save revision checks remain authoritative; the synthesized starter uses revision `0` and existing conflict responses remain unchanged.

## Verification strategy

### Backend

- Service test: an empty store and empty legacy config returns exactly one synthesized draft without changing revision.
- Service test: legacy contracts still take precedence over the starter.
- Service test: durable contracts replace the synthesized starter.
- API test: first GET exposes the starter; first PUT with revision `0` persists it; later GET returns the durable contract at revision `1`.
- Existing rollout, simulation, conflict, and evidence tests continue to pass.

### Frontend

- Playwright test with delayed post-mutation stats/health: Balanced remains pressed and the full Orchestrator remains mounted.
- Playwright test: refreshed backend mode becomes authoritative after the delay.
- Playwright test: a timed-out contracts request shows an error and Retry.
- Playwright test: Retry loads the starter and removes the error.
- Playwright test: stale/aborted responses cannot overwrite the latest contract state.
- Existing keyboard, responsive, rollout, evidence, routing, and API-auth coverage remains green.

### Runtime

- Build and lint the dashboard.
- Sync production dashboard assets into `cutctx/dashboard`.
- Run focused backend and frontend suites, then the broader orchestration suite.
- Exercise the packaged authenticated dashboard in Chrome against port 8787:
  - starter contract visible;
  - Balanced, Aggressive, and Off each persist;
  - no full-page loading reset after mode clicks;
  - refresh preserves the selected mode;
  - browser console has no new errors.

## Non-goals

- Redesigning the Orchestrator visual system.
- Changing model-routing preset definitions.
- Persisting the starter contract before explicit user action.
- Refactoring unrelated dashboard pages or proxy handlers.
