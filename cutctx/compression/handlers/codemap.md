# cutctx/compression/handlers/

## Responsibility
Defines content-specific compression handlers for code and JSON.

## Design
A base handler contract enables Strategy selection; implementations preserve syntax and structure while compacting.

## Flow
The router selects a handler by detected content, invokes it with a budget, and receives compacted text and metadata.

## Integration
Used by universal compression and the content-routing transform pipeline.
