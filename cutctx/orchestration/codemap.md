# cutctx/orchestration/

## Responsibility
Provides deterministic policy-driven routing and workflow orchestration across model providers.

## Design
Contracts/configuration compile into signed or stored policy bundles; registry/provider abstractions expose targets; a deterministic routing engine evaluates candidates; schedulers/workflows coordinate execution; simulation/evaluation/audit/telemetry support governance.

## Flow
A request is validated against a contract, compiled policy and credentials resolve eligible providers, the engine scores/selects a route, scheduler executes it, and outcomes/audit telemetry update contract and evaluation state.

## Integration
Exposed through orchestration service and proxy routes/CLI; integrates with provider adapters, credential stores, policy bundles, telemetry, and enterprise governance.
