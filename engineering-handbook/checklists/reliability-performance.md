---
id: CL-REL-01
kind: checklist
title: Reliability, performance, and scale release checklist
chapter: CH-10
controls:
  - id: ENG-RELPERF-001
    requirement: Each critical service outcome must have an owned objective and production-representative load, degradation, and correctness evidence before release.
    applicability: required for customer-facing APIs, asynchronous workflows, persistent services, and critical internal platforms
    procedure: Run baseline, burst, dependency-latency, worker-loss, queue-backlog, and restart fixtures; measure outcome success and latency at the client boundary.
    expected_result: Observed outcomes meet the approved objective or produce bounded, explainable degradation without duplicate or lost accepted work.
    evidence: objective revision, traffic model, fixture report, percentile distributions, traces, queue metrics, and release decision
    automation: reliability contract and load-fixture suite
    owner: Service owner
    frequency: release and any capacity, timeout, dependency, or topology change
    failure_action: block release, reduce traffic or disable affected path, and open an incident when customer outcomes are at risk
    standards: [NIST-SSDF-1.1, OTEL-SEMCONV-1.43.0]
  - id: ENG-RELPERF-002
    requirement: Recovery procedures must restore the approved recovery point and verify integrity, authorization scope, and safe replay before the service is declared recovered.
    applicability: required for services with durable state, queues, indexes, or externally visible business outcomes
    procedure: Restore a representative isolated fixture, compare recovery point and time to objectives, validate data relationships and tenant access, and replay only idempotent bounded events.
    expected_result: Restored data passes integrity and scope checks; replay does not duplicate outcomes; evidence records the recovery point, time, and residual gaps.
    evidence: restore logs, backup identity, integrity query, access fixture results, replay report, and owner approval
    automation: restore-integrity and bounded-replay verification suite
    owner: Data owner
    frequency: quarterly, before major persistence change, and release for recovery-sensitive changes
    failure_action: stop promotion, preserve the failed evidence, repair the runbook or backup design, and repeat the exercise
    standards: [NIST-SSDF-1.1, OWASP-ASVS-5.0.0]
---

# Reliability, performance, and scale release checklist

- [ ] Publish the critical outcome, indicator, objective, window, owner, and error-budget decision.
- [ ] Exercise realistic baseline, burst, degradation, restart, queue, and cancellation fixtures.
- [ ] Verify timeouts, retries, idempotency, backpressure, and shedding protect correctness as well as latency.
- [ ] Capture correlated, redacted telemetry at the client and dependency boundaries.
- [ ] Perform and evidence a restore with integrity, tenant-scope, freshness, and safe-replay checks.
- [ ] Confirm rollback, traffic-reduction, and escalation actions are owned and immediately usable.
