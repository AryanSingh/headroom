# cutctx/storage/

## Responsibility
Defines generic durable event/record storage for non-memory subsystems.

## Design
A storage interface abstracts append/query lifecycle; JSONL and SQLite implementations offer portable/indexed persistence.

## Flow
Services serialize records through the interface and filtered queries reconstruct them for reporting/control.

## Integration
Used by savings, telemetry, and operational state; depends on filesystem and SQLite.
