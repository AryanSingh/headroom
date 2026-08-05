---
id: EX-CH12-RELEASE
kind: worked-example
chapter: CH-12
standards: [NIST-SSDF-1.1, OWASP-ASVS-5.0.0, OTEL-SEMCONV-1.43.0]
preconditions: [isolated Atlas staging and production-like tenants, immutable export-service artifact, canary traffic fixture, tested rollback artifact]
placement: engineering-handbook/examples/release-engineering
dependencies: [CI evidence store, artifact registry fixture, deployment controller simulator, telemetry collector]
invocation: Promote the approved export-service digest to staging, execute the 5 percent canary, inject a schema-incompatible worker, and execute the declared rollback.
expected_output: The candidate is traceable to one source revision, the canary detects the worker compatibility breach, rollout stops, and rollback restores the prior artifact without duplicating completed exports.
failure_output: The system rebuilds at promotion, expands traffic after a breach, rolls back only the API while incompatible workers continue, or cannot associate telemetry with the artifact digest.
interpretation: Release evidence passes only when a decision can be reconstructed from immutable inputs and observed production-like outcomes.
remediation: Pin build inputs and digests, add worker compatibility gates, use staged traffic limits, link telemetry to release identity, and rehearse component-complete rollback.
cleanup: Restore sandbox traffic to zero, remove the candidate deployment and fixtures, reset the controller, and retain only sanitized release evidence.
---

# Product Atlas release engineering evidence

Atlas releases export service artifact `sha256:atlas-export-2026-09-18`, built from source `8f1a2c7`, to a production-like environment. The approved canary is 5 percent of export requests for 15 minutes; the rollback threshold is any schema-compatibility error or a client-error rate above 1 percent.

| Stage | Observation | Decision evidence |
| --- | --- | --- |
| Candidate | Digest and source revision match the signed release record | build ID, digest, test run IDs |
| Canary | A legacy worker rejects the new event schema | trace ID, worker version, 1.4% client-error rate |
| Stop | Controller holds rollout at 5 percent | traffic-control audit event |
| Rollback | Prior digest restored; completed exports remain exactly once | deployment event, outcome query |

**Product Atlas result.** Release `rel-atlas-2026-09-18` stopped at 5 percent, restored `sha256:atlas-export-2026-09-04`, and produced no duplicate export. The team added a worker-schema gate and reissued a new candidate rather than promoting a rebuilt artifact.
