# cutctx/telemetry/

## Responsibility
Collects privacy-aware operational episodes, outcomes, context, and savings signals.

## Design
Typed telemetry models flow through context/episode collectors, differential-privacy processing, TOIN/outcome aggregation, reporting, and pluggable child backends. Beacon logic controls delivery.

## Flow
Runtime events are normalized into envelopes, sensitive fields are minimized/noised, episodes and outcomes are aggregated, and the reporter persists or transmits them.

## Integration
Used by proxy, savings, training, evals, and orchestration; child backends provide filesystem/HTTPS delivery.
