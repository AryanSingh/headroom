# Dashboard Authentication Error Priority Design

## Problem

The dashboard loads `/stats?cached=1` and `/health` concurrently with `Promise.all`. When both requests fail, the first network rejection becomes the displayed error. A fast `/health` 502 can therefore hide a `/stats` 401 and prevent the authentication surface from appearing.

GitHub Product Release Evidence reproduced this condition: the statistics request returned 401, the health request returned 502 first, and both authentication E2E cases failed because the dashboard rendered its generic unavailable state.

## Chosen Design

Keep both initial requests concurrent, but collect both outcomes with `Promise.allSettled`. Resolve the pair with these priorities:

1. If either request failed with status 401, throw that authentication failure.
2. Otherwise, preserve the existing required-data ordering by throwing the statistics failure before the health failure.
3. If neither failed, publish the statistics and health payloads exactly as before.

The authentication E2E suite will control every request involved in initial dashboard loading. Its regression case will make `/health` fail immediately with 502 and delay the `/stats` 401, proving that authentication wins independently of response timing. The key-save and authenticated cases will mock healthy `/health` and `/stats-history` responses so they never depend on a local proxy.

## Boundaries

- Do not change dashboard layout, copy, routing, polling intervals, or authentication storage.
- Do not serialize the initial requests or add user-visible latency.
- Do not start, stop, probe, or otherwise touch port 8787.
- Do not weaken non-authentication errors: when no 401 exists, the current statistics-first error preference remains.

## Verification

- Observe the new delayed-401/fast-502 Playwright regression fail before implementation.
- Run the focused authentication Playwright suite after implementation.
- Run all Chromium dashboard journeys, dashboard Node tests, lint, and production build.
- Run repository diff checks and the relevant Python dashboard contract tests.
- Commit and push the fix, then monitor every workflow triggered for the new `main` SHA through completion.
