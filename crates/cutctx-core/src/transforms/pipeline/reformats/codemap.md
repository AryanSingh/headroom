# crates/cutctx-core/src/transforms/pipeline/reformats/

## Responsibility
Provides loss-minimizing structural rewrite passes for verbose JSON and repetitive logs.

## Design
`JsonMinifier` removes representation overhead while preserving values; `LogTemplate` identifies repeated line shapes and emits compact templates/instances. Both implement the pipeline's `ReformatTransform` strategy contract.

## Flow
Pipeline supplies content/context -> each enabled pass checks applicability -> produces a candidate and metadata -> orchestrator accepts only beneficial safe output before offload evaluation.

## Integration
- Registered by `CompressionPipeline`.
- Feeds smaller structured input into downstream offload transforms.
