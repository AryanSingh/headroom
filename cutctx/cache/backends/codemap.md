# cutctx/cache/backends/

## Responsibility
Provides persistence strategies for exact and semantic cache records.

## Design
A backend protocol abstracts lookup, write, deletion, expiry, and statistics; memory and SQLite implementations trade ephemeral speed for durability.

## Flow
Cache layers serialize entries, call the selected backend, and receive live records after TTL checks; expired records are removed during access or cleanup.

## Integration
Used by cache registries and compression/semantic caches; SQLite uses local durable storage and memory is process-local.
