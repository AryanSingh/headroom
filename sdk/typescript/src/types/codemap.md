# sdk/typescript/src/types/

## Responsibility
Defines compile-time configuration and data-model contracts for the Cutctx TypeScript SDK.

## Design
`config.ts` mirrors proxy compression modes, profiles, relevance, rolling-window, anchors, smart-crusher, cache, CCR, and lifecycle options. `models.ts` describes simulation artifacts, request/session metrics, health/stats, memory/retrieval, telemetry, TOIN, and query shapes.

## Flow
SDK callers construct typed config/query objects -> client serializes them to proxy wire fields -> responses are converted into the corresponding typed models for downstream code.

## Integration
- Re-exported by `src/index.ts` and used throughout client, simulation, hooks, and adapters.
- Complements core message/result interfaces in `src/types.ts`.
