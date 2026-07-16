# cutctx/billing/

## Responsibility
Provides a stable billing namespace for checkout, entitlements, seats, trials, and usage.

## Design
The package is a facade over root commercial modules, preserving a compact public import surface.

## Flow
Consumers import billing operations here; calls delegate to underlying clients and return typed billing state.

## Integration
Connects CLI and proxy administration to `cutctx.checkout`, entitlements, seats, and trials.
