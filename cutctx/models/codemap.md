# cutctx/models/

## Responsibility
Manages optional local ML model metadata, artifacts, configuration, and loading.

## Design
A registry maps capabilities to artifacts and runtime requirements; typed configuration controls activation and paths.

## Flow
Callers resolve a capability, ensure its artifact exists, load it through the supported runtime, and invoke prediction.

## Integration
Used by learned/image routing and relevance features; integrates with optional ONNX/ML dependencies.
