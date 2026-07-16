# cutctx_ee/audit/

## Responsibility
Provides tenant-aware enterprise audit event ingestion and querying.

## Design
Typed immutable audit models, an append/query store, and FastAPI router separate transport from persistence.

## Flow
Authenticated requests validate audit events, append them with tenant/user context, and query paginated/filterable records.

## Integration
Mounted by proxy enterprise routes; consumed by policy, security, billing, and administrative operations.
