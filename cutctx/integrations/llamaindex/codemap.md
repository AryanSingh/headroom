# cutctx/integrations/llamaindex/

## Responsibility
Provides a LlamaIndex node postprocessor that compresses retrieved context before synthesis.

## Design
The adapter follows the postprocessor contract and translates nodes while preserving identity and metadata.

## Flow
Retrieved nodes arrive with a query, content is budgeted/compacted, and updated nodes return to synthesis.

## Integration
Depends on optional LlamaIndex interfaces and core compression transforms.
