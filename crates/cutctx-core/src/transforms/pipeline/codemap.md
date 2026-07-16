# crates/cutctx-core/src/transforms/pipeline/

## Responsibility
Orchestrates configurable two-phase structural reformatting and high-volume content offloading.

## Design
`ReformatTransform` and `OffloadTransform` define independent strategies over a `CompressionContext`. `CompressionPipeline`/builder register ordered passes; TOML-backed config controls enablement and thresholds. Reformat and offload bloat estimates can run in parallel before ordered execution.

## Flow
Build context -> evaluate/apply enabled reformats -> estimate offload benefit -> run qualifying offloads -> aggregate transformed content, token deltas, applied strategy names, and recoverable errors into `PipelineResult`.

## Integration
- Re-exported through `transforms` and used by higher-level compression dispatch.
- Child strategies live in `reformats/` and `offloads/`; concurrency uses Rayon.
