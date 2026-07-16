# crates/cutctx-core/

## Responsibility
Provides provider-neutral, transport-free context analysis and compression algorithms, token counting, retrieval storage, relevance/signals, cache policy, licensing primitives, and code navigation.

## Design
The crate exposes small typed modules behind stable re-exports. Strategy traits select tokenizer, relevance, transform, and CCR implementations; deterministic algorithms preserve Python parity. `config/pipeline.toml` embeds default transform ordering and gates.

## Flow
Callers classify auth/content, count tokens, select transforms or pipelines, optionally persist originals in CCR, and receive transformed content plus manifests/statistics. No network server lifecycle lives here.

## Integration
- Primary consumer: `cutctx-proxy`; also used by `cutctx-py` and `cutctx-parity`.
- Depends on serde, native tokenizers, Magika/unidiff, tree-sitter stack graphs, concurrent/SQLite/optional Redis storage, and media codecs.
- `src/` contains runtime code; `benches/` measures hot-path primitives.
