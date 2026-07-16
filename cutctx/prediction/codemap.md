# cutctx/prediction/

## Responsibility
Extracts stable request features for learned routing and compression decisions.

## Design
Feature extraction is deterministic and model-agnostic, normalizing request shape, content, tools, and history.

## Flow
A request is inspected before routing and downstream predictors/training pipelines consume the feature record.

## Integration
Used by proxy routing, ML models, and training label generation.
