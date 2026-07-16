# crates/cutctx-core/src/ccr/backends/

## Responsibility
Implements configurable CCR storage strategies for process-local, durable single-instance, and shared multi-worker deployments.

## Design
`InMemoryCcrStore` uses a bounded concurrent map with TTL; `SqliteCcrStore` provides durable WAL-backed storage; feature-gated `RedisCcrStore` shares entries across workers. `CcrBackendConfig` and `from_config` form an abstract factory returning `Box<dyn CcrStore>`.

## Flow
Startup converts configuration into a concrete backend -> callers issue store/get/stat operations through the trait -> each backend enforces expiration and its own concurrency/persistence semantics.

## Integration
- Implements `ccr::CcrStore` and is selected by `cutctx-proxy` startup.
- Uses DashMap, rusqlite, and optional Redis clients.
