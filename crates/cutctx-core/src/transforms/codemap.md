# crates/cutctx-core/src/transforms/

## Responsibility
Implements safe, content-aware context reduction for code, JSON, diffs, logs, search output, text, image/audio payloads, and provider message live zones.

## Design
Content detection routes inputs to specialized compressors. Shared modules protect tags/tool pairs, select anchors, compute adaptive sizes, and reject unsafe or token-larger rewrites. `pipeline/` composes reformat/offload passes; `smart_crusher/` handles structured arrays; `live_zone.rs` maps provider schemas into block actions and manifests.

## Flow
Detect content and protected regions -> select compressor/config -> transform candidates while retaining salient anchors/errors -> recount tokens and validate structure -> accept only safe reductions -> emit result, statistics, exclusion reasons, and optional CCR markers.

## Integration
- Called by proxy compression adapters for Anthropic, OpenAI Chat, and OpenAI Responses payloads.
- Uses tokenizer, signals, relevance, CCR, media codecs, Magika, unidiff, and embedded pipeline configuration.
