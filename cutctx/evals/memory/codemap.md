# cutctx/evals/memory/

## Responsibility
Evaluates memory retrieval and answer quality against conversational benchmarks including LoCoMo.

## Design
Dataset loaders, judge adapters, and versioned runners separate preparation, execution, scoring, and experiment evolution.

## Flow
A runner loads conversations/questions, exercises a memory system, judges answers/evidence, and aggregates quality and latency metrics.

## Integration
Consumes `cutctx.memory`; results feed benchmark and release-evidence reporting.
