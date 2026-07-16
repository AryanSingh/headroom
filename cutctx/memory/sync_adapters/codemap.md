# cutctx/memory/sync_adapters/

## Responsibility
Imports conversation and agent state from Claude Code and Codex into memory.

## Design
Adapters encapsulate transcript discovery, incremental checkpoints, parsing, and event normalization.

## Flow
Sync scans new history, parses turns, writes normalized records, and advances its checkpoint.

## Integration
Driven by `memory.sync` and CLI; reads local provider state and writes configured backends.
