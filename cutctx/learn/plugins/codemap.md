# cutctx/learn/plugins/

## Responsibility
Defines Claude, Codex, and Gemini adapters for learning policy from local histories.

## Design
Each plugin implements common scanning/writing behavior while owning provider paths and transcript formats.

## Flow
The registry selects a plugin, scans history into observations, and writes learned recommendations in provider syntax.

## Integration
Consumed by `cutctx.learn`; reads local agent histories and configuration.
