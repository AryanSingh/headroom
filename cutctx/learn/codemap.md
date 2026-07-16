# cutctx/learn/

## Responsibility
Learns compression and configuration recommendations from local agent histories.

## Design
A plugin registry selects provider adapters; scanners/watchers discover new transcripts, analyzers normalize observations, aggregators derive recommendations, and writers persist managed output. Typed models/base contracts keep the pipeline provider-independent.

## Flow
A scan or watch event loads provider history, converts it into observations, analyzes and aggregates patterns, then writes recommended policy/configuration with incremental state.

## Integration
Invoked by learn CLI; child plugins support Claude, Codex, and Gemini histories and connect results to configuration/policy modules.
