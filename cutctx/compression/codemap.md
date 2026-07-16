# cutctx/compression/

## Responsibility
Provides high-level content detection and universal/task-aware compression above the lower-level transform library.

## Design
Detectors classify payloads, masks protect invariant spans, task-aware policy selects a strategy, and handler strategies specialize code/JSON while universal compression supplies fallback behavior.

## Flow
Input is classified and masked, a handler or universal policy compacts it to the target, protected spans are restored, and compression metadata accompanies output.

## Integration
Called by SDK and proxy pipelines; delegates specialized work to `compression/handlers`, tokenizers, relevance scoring, and `cutctx.transforms`.
