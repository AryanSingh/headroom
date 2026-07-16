# crates/cutctx-core/src/transforms/smart_crusher/

## Responsibility
Compresses structured JSON/tool output by analyzing schemas, selecting anchors/outliers, applying field-aware crusher strategies, and formatting a deterministic compact representation.

## Design
Typed analyzer/planner/executor stages separate observation from mutation. Traits abstract classification, anchors, crushers, observers, and hashing; builders/config assemble an orchestrator. Statistical and error-keyword modules protect anomalous or important values. `compaction/` supplies recursive schema/table IR for nested heterogeneous data.

## Flow
Parse and classify fields -> compute statistics/errors/outliers -> build a constraint-aware plan with protected anchors -> execute per-field crushers or recursive compaction -> observe decisions -> format and token-check output, declining unsafe or unhelpful candidates.

## Integration
- Used by JSON offload and live-zone tool-result compression.
- Integrates with tokenizers, CCR hashing/markers, content detection, and pipeline statistics.
