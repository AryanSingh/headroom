# cutctx/savings/

## Responsibility
Calculates, parses, and orchestrates savings measurements across agent tools.

## Design
Typed events, provider parsers, eligibility policy, integrations, and an orchestrator separate concerns.

## Flow
Tool output/telemetry becomes token-cost observations, policy validates comparison, and aggregate savings are emitted.

## Integration
Used by agent-savings CLI, proxy metadata, and reports; consumes histories, pricing, and telemetry.
