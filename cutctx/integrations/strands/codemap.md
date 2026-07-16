# cutctx/integrations/strands/

## Responsibility
Adapts CutCtx to Strands agents through wrappers, hooks, and bundles.

## Design
Provider adapters normalize models; hooks intercept lifecycle events; bundles package activation.

## Flow
Requests pass through hooks, eligible context is compacted, the provider runs, and outcomes are recorded.

## Integration
Depends on optional Strands APIs and core compression/savings services.
