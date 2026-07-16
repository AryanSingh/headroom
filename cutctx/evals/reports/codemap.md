# cutctx/evals/reports/

## Responsibility
Serves as the output location for generated evaluation artifacts rather than executable code.

## Design
Evaluation runners own serialization; this directory intentionally defines no runtime abstractions.

## Flow
Evaluation modules compute metrics and write machine- or human-readable summaries here.

## Integration
Produced by benchmark/release-evidence workflows and consumed by release tooling or reviewers.
