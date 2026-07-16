# crates/cutctx-core/src/relevance/

## Responsibility
Ranks context items against a query using lexical, embedding, or hybrid semantic relevance.

## Design
`RelevanceScorer` is the strategy contract and returns typed `RelevanceScore` values with confidence/detail. `BM25Scorer`, `EmbeddingScorer`, and `HybridScorer` implement alternative tiers; `create_scorer` is the named factory and `default_batch_score` supplies shared batching behavior.

## Flow
Callers select a tier -> scorer tokenizes or embeds query/documents -> produces normalized scores -> hybrid mode combines lexical and embedding evidence -> compression planners retain or prioritize higher-relevance items.

## Integration
- Consumed by compression and retrieval ranking paths.
- Embedding mode uses the native fastembed/ONNX model; BM25 remains deterministic and local.
