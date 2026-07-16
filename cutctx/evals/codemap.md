# cutctx/evals/

## Responsibility
Runs offline and model-backed benchmarks for compression quality, cost, memory impact, canaries, and release evidence.

## Design
Datasets, metrics, cost tracking, suite orchestration, reports, and runner strategies are separated. Release bundle/manifest modules convert measured evidence into reproducible release artifacts; child memory/runners packages specialize execution.

## Flow
CLI or automation loads a dataset/suite, executes configured baseline and transformed cases, scores fidelity/downstream outcomes/cost, aggregates metrics, and emits benchmark or release artifacts.

## Integration
Consumes backends, compression, memory, telemetry, and pricing; `memory` and `runners` provide specialized strategies, while `reports` stores generated outputs.
