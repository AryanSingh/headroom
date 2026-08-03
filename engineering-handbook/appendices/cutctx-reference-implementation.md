---
id: APP-CUTCTX-REFERENCE-001
kind: reference
title: Cutctx Reference Implementation Map
purpose: Show how handbook procedures can be grounded in a real multi-surface engineering product without making the manual product-specific.
audience: [engineering teams, audit leads, Cutctx maintainers]
standards: [NIST-SSDF-1.1, OWASP-ASVS-5.0.0, OTEL-SEMCONV-1.43.0]
---

# Cutctx Reference Implementation Map

## How to use this appendix

The manual is product-agnostic. Cutctx is a reference implementation for locating evidence and applying the procedures to a system with a CLI, proxy, SDKs, dashboard, native components, enterprise services, and integrations. Paths can change; confirm them in the repository codemap before relying on them in an audit.

This is an evidence map, not a security certification or an assurance claim about a particular release.

## System surfaces and audit questions

| Surface | Typical entry point | Audit question | Evidence to collect |
| --- | --- | --- | --- |
| CLI | `cutctx/cli.py`, `cutctx/cli/` | Are non-interactive output, exit codes, config precedence, and interruption behavior contractual? | Deterministic CLI fixture, JSON output, stderr, exit code. |
| Proxy | `cutctx/proxy/server.py` | Are authentication, tenant context, provider routing, and egress boundaries enforced? | Route tests, policy configuration, trace and decision records. |
| SDK | `cutctx/client.py`, `sdk/` | Are compatibility, retries, idempotency, and error envelopes documented and tested? | Contract suite, version matrix, deprecation record. |
| Dashboard | `dashboard/src/main.jsx` | Do user journeys show loading, empty, error, and access-denied states accessibly? | Playwright results, screenshots, accessibility findings. |
| Native core | `crates/cutctx-proxy/`, `crates/cutctx-py/` | Are performance-sensitive transformations bounded and observable? | Benchmarks, parity tests, release provenance. |
| Enterprise services | `cutctx_ee/` | Are identity, billing, retention, and audit controls tenant-scoped? | Authorization tests, retention job records, audit-log samples. |
| Integrations | `plugins/`, `extensions/` | Are installation, tool authority, callbacks, and fallback behavior explicit? | Installation test, permission map, callback replay fixture. |

## Evidence-led audit sequence

1. Start with the root `codemap.md` and the relevant surface map. Record the commit, environment, and enabled components.
2. Trace one representative customer outcome across the CLI or SDK, proxy, provider adapter, telemetry, and dashboard. Note each identity and authorization transition.
3. Execute the smallest deterministic fixture for that surface before using shared or production-like environments.
4. For each conclusion, attach a durable path, command, timestamp, and expected result to the evidence register.
5. Convert a gap into a stable control, finding, exception, or release decision; do not leave it as an informal chat observation.

## Worked example: provider-routing evidence

**Scenario:** An Atlas tenant sends a request through a Cutctx-compatible proxy with a route policy that allows a preferred provider and a bounded fallback.

**Review steps:**

1. Capture the policy version and the tenant-scoped route decision.
2. Run a deterministic request fixture for the preferred path and a controlled failure fixture for fallback.
3. Verify the response and telemetry share a correlation identifier and do not include token-like secrets.
4. Verify the fallback did not widen the tenant, tool, or data authority.
5. Record latency, cost, result class, and failure reason in the routing evidence record.

**Pass condition:** the reviewer can explain which policy selected the route, why fallback occurred, which tenant context applied, and how the request outcome was observed. A successful response without that chain is incomplete evidence.

## Procedure-to-surface crosswalk

| Handbook procedure | Cutctx reference surface | Minimum verification |
| --- | --- | --- |
| API/backend audit | Proxy, provider adapters, EE policy services | Contract, authorization, idempotency, and tenant-isolation tests. |
| Routing/orchestration | Router, policy, memory services | Preferred/fallback replay with recorded decision reasons. |
| Memory governance | Memory service and enterprise retention paths | Create, retrieve, delete, and retention-expiry evidence for one tenant. |
| Playwright testing | Dashboard and local fixture | Loopback-only browser test for recovery, accessibility, and sensitive-detail absence. |
| Observability | Proxy telemetry and dashboard | Trace-to-log-to-metric correlation for a known request. |
| Release engineering | Python/Rust/SDK build and CI paths | Provenance, qualification, rollback, and decision record. |

## Common mistakes

- Treating a repository path as proof that a control is enabled in a deployed environment.
- Reading a dashboard state as proof of a backend authorization decision without collecting the decision evidence.
- Using production credentials for a handbook fixture when a deterministic local fixture can establish the contract.
- Measuring compression savings without checking the relevant engine is reachable and actually applied.
- Conflating a provider’s response with proof that routing policy, tenant scope, and fallback rules behaved as intended.

## Handoff record

For a Cutctx-specific audit, attach the repository commit, deployment identifier, enabled feature flags, route-policy version, test commands, results, redacted evidence locations, findings, and decision owner. Re-run the map after a material architecture change or before claiming control coverage for a new deployment.
