# cutctx_ee/ledger/

## Responsibility
Records enterprise usage/cost ledger entries and serves aggregate spend queries.

## Design
Typed usage models, normalized pricing, durable store, query service, and API router separate ingestion from reporting.

## Flow
Provider usage is priced and appended under org/project identity; queries filter and aggregate entries into spend/usage views.

## Integration
Mounted by spend/ledger control-plane routes; consumes proxy usage metadata and pricing and feeds billing/reporting.
