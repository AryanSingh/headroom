# crates/cutctx-core/src/ccr/

## Responsibility
Defines Compress-Cache-Retrieve persistence contracts and deterministic markers for recovering original content replaced during compression.

## Design
`CcrStore` is the storage strategy interface. BLAKE3-derived 24-character keys and `<<ccr:HASH>>` markers form the cross-runtime wire contract; `backends/` supplies in-memory, SQLite, and optional Redis implementations plus a configuration factory.

## Flow
A compressor computes a key from original bytes -> stores content with metadata/TTL through `CcrStore` -> emits a marker -> retrieval code resolves the hash through the same store; expired or evicted values become misses.

## Integration
- Used by live-zone transforms and proxy retrieval endpoints/tool integrations.
- Re-exported from `cutctx-core`; constructed by proxy startup from CCR configuration.
