# cutctx/memory/writers/

## Responsibility
Writes retrieved memory context into provider-specific instruction files.

## Design
A base writer has Claude, Codex, Cursor, and generic strategies owning paths, syntax, and safe updates.

## Flow
A wrapper selects a writer, renders selected records, merges managed content, and returns metadata.

## Integration
Consumed by memory wrapper tools/CLI; targets provider config while sourcing `cutctx.memory`.
