# cutctx/image/

## Responsibility
Optimizes image inputs before multimodal provider calls.

## Design
Compression and tiling are separate strategies; ONNX/trained routers choose policy from image features and constraints.

## Flow
An image is inspected, routed to optimization parameters, transformed, and accompanied by size/quality metadata.

## Integration
Called by proxy image-compression decisions; optionally uses local ONNX inference.
