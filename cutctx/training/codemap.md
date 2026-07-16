# cutctx/training/

## Responsibility
Builds supervised examples for learned compression and routing decisions.

## Design
Typed schemas define feature/label records; a builder joins request features with observed outcomes.

## Flow
Observations are normalized, features/targets derived, invalid samples filtered, and training records emitted.

## Integration
Consumes proxy traces, prediction features, and outcomes; feeds routing training/evaluation.
