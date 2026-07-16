# cutctx/proxy/

## Responsibility
Runs the FastAPI data/control-plane proxy that assembles compression, routing, caching, memory, governance, and observability.

## Design
`CutctxProxy` composes provider-handler mixins; `create_app` builds middleware, routes, stores, and optional enterprise services. A staged intelligence pipeline, model router, budgets, rate/circuit controls, interceptors, and child routing/handler packages implement policy as composable strategies.

## Flow
Requests enter provider-compatible endpoints, pass auth/security/rate checks, project/tool/memory/cache and compression decisions, model/provider routing, then upstream forwarding. Streaming or JSON results are normalized while costs, savings, outcomes, traces, webhooks, and session state are recorded.

## Integration
Launched by CLI/server entrypoints; depends on providers, transforms, cache, memory, pricing, telemetry/security/orchestration, child handlers/interceptors/routes/routing, and optional `cutctx_ee` services.
