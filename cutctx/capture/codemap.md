# cutctx/capture/

## Responsibility
Captures and compares network traffic to quantify transformation savings.

## Design
Snapshot and diff records separate measurement from presentation, with helpers for request/response byte accounting.

## Flow
A capture brackets an operation, records traffic, computes before/after deltas, and returns comparison data.

## Integration
Invoked by capture CLI and benchmark workflows; observes traffic without mutating requests.
