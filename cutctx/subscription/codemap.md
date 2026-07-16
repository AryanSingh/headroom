# cutctx/subscription/

## Responsibility
Tracks third-party subscription capacity, quotas, and per-session consumption.

## Design
A provider contract has Codex rate-limit and Copilot quota adapters; common models normalize limits.

## Flow
Clients fetch/infer quota, session tracking records consumption, and tracker returns remaining capacity/reset data.

## Integration
Used by routing and CLI status; integrates with Codex/Copilot APIs or local auth state.
