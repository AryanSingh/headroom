# crates/cutctx-proxy/src/observability/

## Responsibility
Records proxy request, provider, cache, compression, latency, cost, and stream behavior for Prometheus, OpenTelemetry, logs, and an optional spend ledger.

## Design
Central metric names bound label vocabularies to control cardinality. Lazy registered counters/gauges/histograms cover proxy and provider paths; specialized modules track cache hit rate and compression ratios. OTel setup is non-fatal, and `SpendEmitter` asynchronously exports ledger events.

## Flow
Request/stream/compression paths record bounded observations -> registry exposes text metrics and OTel spans/metrics -> cache/compression calculators derive ratios -> spend events queue for asynchronous delivery without blocking responses.

## Integration
- Called across proxy, compression, cache stabilization, Bedrock, Vertex, and SSE code.
- Exposes the metrics handler and integrates Prometheus, tracing/OpenTelemetry, and configured ledger HTTP delivery.
