# cutctx/proxy/routes/

## Responsibility
Defines FastAPI control-plane routes for administration and enterprise operations.

## Design
Route modules isolate APIs for admin, airgap, audit, DSR, failover, licensing, memory, MFA, orchestration, policy, rate limits, RBAC, residency, secrets, spend, SSO, and related services. Factories bind routes to runtime dependencies, including live telemetry, TOIN, CCR, memory, and orchestration services.

## Flow
`create_app` constructs services and dependencies, includes routers, validates request/auth models, invokes service/store methods, and serializes operational responses.

## Integration
Mounted by proxy server alongside provider data-plane endpoints; integrates core services and optional `cutctx_ee` implementations.
