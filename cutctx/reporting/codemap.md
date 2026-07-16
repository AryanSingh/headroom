# cutctx/reporting/

## Responsibility
Generates user-facing savings reports and portable memory exports.

## Design
Generators separate aggregation from rendering; memory export normalizes backend records.

## Flow
Callers supply usage or memory records, metrics/sections are aggregated, and serialized/text output is returned.

## Integration
Consumed by report and memory CLI; reads savings, telemetry, and memory backends.
