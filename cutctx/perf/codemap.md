# cutctx/perf/

## Responsibility
Analyzes runtime observations for latency and throughput regressions.

## Design
The analyzer converts timing samples into aggregate statistics, stage breakdowns, and findings.

## Flow
CLI/evaluation code supplies observations; the analyzer groups and compares them and emits summaries.

## Integration
Consumes proxy timing/evaluation data and feeds performance CLI and release evidence.
