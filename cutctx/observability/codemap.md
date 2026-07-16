# cutctx/observability/

## Responsibility
Provides tracing and metrics for compression, memory impact, latency, and savings.

## Design
Framework-neutral metric records and spans isolate instrumentation from exporters; memory helpers calculate retrieval contribution.

## Flow
Runtime paths open spans and record counters/timings, then exporters consume observations.

## Integration
Used across proxy, compression, and memory services; interoperates with optional tracing backends.
