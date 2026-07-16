# crates/cutctx-core/src/transforms/pipeline/offloads/

## Responsibility
Implements specialized high-reduction passes for diff, JSON, log, and search-result payloads, including diff-noise filtering.

## Design
Each strategy implements `OffloadTransform`, independently estimates bloat/benefit, and returns an `OffloadOutput` with transformed text and accounting. Domain compressors delegate to core diff/log/search/smart-crusher algorithms rather than sharing one heuristic.

## Flow
After reformats, the pipeline evaluates offloads in parallel -> qualifying strategies run in configured order -> outputs replace or annotate bulky regions -> token accounting and failures return to the orchestrator.

## Integration
- Registered by `CompressionPipeline` and driven by pipeline TOML thresholds.
- Uses domain transforms, tokenization, and optional CCR-compatible markers.
