# Chapter 6 -- API & Backend Verification Playbook

## Objective

Verify that backend services, APIs, background processing, and
persistence layers are correct, secure, reliable, and consistent with
the product's documented and observed behavior.

## Scope

Audit:

-   REST / GraphQL / RPC APIs
-   Authentication & authorization
-   Service-to-service communication
-   Background workers
-   Scheduled jobs
-   Message queues
-   Databases
-   Caches
-   Webhooks
-   Import/export pipelines
-   Observability (logs, metrics, traces)

## API Inventory

Create an inventory before testing.

  Endpoint   Method   Auth   Module   Priority   Tested   Evidence
  ---------- -------- ------ -------- ---------- -------- ----------

Include public, private, admin, enterprise-only, and internal endpoints.

## Contract Verification

For every endpoint verify:

-   Request schema
-   Response schema
-   Required fields
-   Optional fields
-   Validation rules
-   HTTP status codes
-   Error payloads
-   Backward compatibility
-   Documentation accuracy

## Authentication & Authorization

Verify:

-   Anonymous access
-   Authenticated access
-   Role-based permissions
-   Enterprise entitlements
-   Expired tokens
-   Revoked credentials
-   Invalid signatures
-   Session expiry
-   Cross-tenant isolation

## Input Validation

Test:

-   Missing fields
-   Invalid types
-   Boundary values
-   Large payloads
-   Unicode
-   Duplicate identifiers
-   Unknown fields
-   Malformed JSON
-   File uploads (where supported)

Confirm validation occurs server-side.

## Persistence & Data Integrity

Verify:

-   Create
-   Read
-   Update
-   Delete
-   Transactions
-   Rollback on failure
-   Idempotency
-   Referential integrity
-   Data migrations
-   Soft delete / hard delete behavior

## Background Processing

Audit:

-   Job creation
-   Retry policy
-   Scheduling
-   Dead-letter handling
-   Duplicate prevention
-   Cancellation
-   Recovery after restart

## Queues & Events

Verify:

-   Publish
-   Consume
-   Ordering guarantees
-   At-least-once / exactly-once expectations
-   Failure recovery
-   Poison message handling

## Cache Verification

Confirm:

-   Cache population
-   Expiration
-   Invalidation
-   Stale data handling
-   Fallback to source
-   Consistency after writes

## Webhooks & Integrations

Verify:

-   Signature validation
-   Retry policy
-   Duplicate event handling
-   Timeout handling
-   Error responses
-   Replay protection

## Error Handling

For every service verify:

-   Structured errors
-   User-safe messages
-   Logging
-   Correlation IDs
-   Retry guidance
-   No sensitive information leakage

## Observability

Review:

-   Logs
-   Metrics
-   Traces
-   Health checks
-   Readiness probes
-   Alerting hooks

Confirm that failures can be diagnosed without exposing secrets.

## Performance

Measure where appropriate:

-   Latency
-   Throughput
-   Database query efficiency
-   Queue depth
-   Worker utilization
-   Cache hit rate
-   Startup and recovery times

## Regression Strategy

After every confirmed fix:

1.  Reproduce the defect.
2.  Verify the fix.
3.  Execute related API tests.
4.  Verify downstream consumers.
5.  Update evidence.

## Evidence

Capture:

-   Request payload
-   Response payload
-   Status code
-   Logs
-   Database verification (where safe)
-   Queue state (where relevant)
-   Reproduction steps

## Deliverables

1.  API inventory
2.  Contract verification report
3.  Authentication report
4.  Authorization report
5.  Persistence report
6.  Queue & worker report
7.  Webhook verification report
8.  Performance observations
9.  Backend defect register
10. Evidence index

## Exit Criteria

Backend audit is complete only when:

-   Every discovered endpoint has been verified or explicitly documented
    as blocked.
-   Authentication and authorization are validated.
-   Persistence and background processing have been exercised.
-   Critical workflows succeed end-to-end.
-   Critical and High findings include reproducible evidence.
