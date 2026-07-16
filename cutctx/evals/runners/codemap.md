# cutctx/evals/runners/

## Responsibility
Provides reusable execution strategies for compression and memory-impact experiments.

## Design
Separate runners cover compression-only, before/after downstream comparison, and memory-impact scenarios.

## Flow
A runner receives data/configuration, executes baseline and transformed cases, records outputs/costs, and aggregates measurements.

## Integration
Orchestrated by the eval suite and CLI; invokes compression, model backends, and memory systems.
