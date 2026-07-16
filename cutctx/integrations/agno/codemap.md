# cutctx/integrations/agno/

## Responsibility
Adapts compression and savings tracking to Agno agents and models.

## Design
Model wrappers and lifecycle hooks intercept Agno calls; provider helpers normalize configurations.

## Flow
Hooks observe a request, compact eligible context, forward through the wrapped model, and attach outcome metadata.

## Integration
Depends on optional Agno APIs and core transforms; exported through `cutctx.integrations`.
