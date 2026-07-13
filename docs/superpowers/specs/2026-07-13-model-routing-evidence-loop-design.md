# Model Routing Evidence Loop Design

## Objective

Make Cutctx model routing simultaneously safe, economically useful, and operable. The first implementation slice turns existing routing calibration capabilities into a production feedback loop without changing the deterministic safety classifier or allowing learned evidence to bypass transport, capability, account, or high-risk gates.

## Industry assessment

Cutctx already has stronger safety and audit foundations than gateway routers centered on load balancing, provider fallback, or static cheapest/fastest selection. Existing strengths include conservative task classification, confidence abstention, transport-safe targets, sanitized shadow evidence, segmented calibration, and unified decision traces.

The material product gaps are:

1. Sampled shadow replay is awaited on non-streaming request paths and therefore adds baseline latency to the visible response.
2. Quality/cost calibration exists as offline Python and CLI functionality but is not exposed as an authenticated operator-readable product surface.
3. The dashboard emphasizes modes and estimated savings without showing whether sufficient evidence exists, whether quality guardrails pass, or which threshold is recommended.

## Approved architecture

The long-term product is an evidence-first routing workbench bounded by deterministic policy:

1. A safety kernel verifies task risk, capabilities, account, provider, transport, and policy constraints. It fails closed by retaining the requested model.
2. A candidate planner considers only compatible model deployments.
3. An evidence policy applies confidence thresholds, quality floors, unsafe-rate limits, and savings objectives. It may assign a safe candidate or abstain, but cannot override the safety kernel.
4. Primary execution is independent of sampled baseline evaluation.
5. Sanitized evidence feeds a versioned decision ledger, simulation, staged promotion, drift detection, and rollback.

## First implementation slice

### Non-blocking shadow evaluation

The visible non-streaming response must not await model-routing baseline replay. A small background-task scheduler will retain task references until completion and consume task exceptions. Existing shadow sampling, judging, sanitization, and failure isolation remain unchanged. Direct unit calls to transport-specific shadow helpers remain awaitable for deterministic testing.

### Evidence report API

Add an authenticated read-only endpoint at `GET /v1/orchestration/routing/evidence`. It reads the sanitized JSONL evidence store and returns schema version 1 with:

- shadow mode enabled state and configured sample rate;
- sample count and minimum sample requirement;
- readiness status: `no_evidence`, `collecting`, `quality_blocked`, or `ready`;
- explicit quality and unsafe-rate constraints;
- the recommended global confidence policy only when minimum evidence is met;
- the quality/cost frontier and segmented recommendations;
- no prompt text, response text, raw workspace path, raw repository name, credential, or evidence-file path.

Default readiness constraints are 20 samples, mean quality at least 0.90, unsafe rate at most 0.01, and an unsafe quality floor of 0.80. Query parameters may tighten or relax these values within validated ranges for read-only simulation; they do not mutate runtime routing.

### Evidence-first dashboard

The Orchestrator page will fetch the evidence endpoint and show one compact decision card near routing mode control:

- readiness state and sample progress;
- recommended confidence threshold when ready;
- measured mean quality, unsafe rate, routing rate, and verified savings from the recommended frontier point;
- clear empty, collecting, blocked, ready, loading, and unavailable states;
- copy that distinguishes measured shadow evidence from estimated live savings.

The existing Providers, Models, Roles, Routing, Activity, routing-mode controls, and user credential-removal changes remain intact.

## Error handling

- A missing evidence file is a successful `no_evidence` response.
- Malformed JSONL rows remain ignored by the existing store.
- Background evaluation failures never affect the primary response and never create unhandled task-exception warnings.
- An unavailable evidence endpoint does not block the rest of the Orchestrator page.
- Invalid evidence query constraints return FastAPI validation errors.

## Testing strategy

All behavior changes follow red-green-refactor:

1. Unit tests prove scheduled background evaluation returns before a blocked coroutine completes, retains the task, and consumes failures.
2. API tests prove authentication, readiness transitions, privacy, constraint reporting, and recommended metrics.
3. Browser tests prove collecting and ready evidence states render while all existing Orchestrator controls remain available.
4. Targeted routing, API, dashboard lint/build, and relevant Playwright tests run before the broader regression suite.

## Deferred work

This slice does not automatically promote a learned scorer, mutate routing thresholds, run shadow streams, replay tool-bearing requests, or add a new classifier. Those require a separate staged-rollout design after the evidence surface is operating in production.
