# crates/

## Responsibility
Houses the native Rust implementation: compression primitives, the Axum reverse proxy, Python extension bindings, and a Rust/Python parity runner.

## Design
A Cargo workspace separates pure reusable algorithms (`cutctx-core`) from transport/runtime concerns (`cutctx-proxy`), FFI exposure (`cutctx-py`), and fixture comparison (`cutctx-parity`). The proxy depends inward on core; bindings re-export core capabilities rather than duplicating algorithms.

## Flow
Requests enter `cutctx-proxy`, are classified and transformed with `cutctx-core`, then forwarded/streamed upstream. Python calls reach the same core through `cutctx-py`. `cutctx-parity` serializes representative operations for cross-language comparison.

## Integration
- Consumed by the CLI/proxy distribution and Python package build.
- Core integrations include tokenizers, tree-sitter/stack graphs, storage backends, Axum/Tokio, provider auth SDKs, Prometheus/OpenTelemetry, and PyO3.
