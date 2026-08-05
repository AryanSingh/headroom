---
id: CL-CHAOS-01
kind: checklist
title: Chaos engineering experiment checklist
chapter: CH-15
controls:
  - id: ENG-CHAOS-001
    requirement: Each chaos experiment must have an approved falsifiable hypothesis, bounded blast radius, named abort authority, and reversible containment action.
    applicability: required for experiments that degrade services, dependencies, queues, identity, persistence, or production-like environments
    procedure: Record the outcome boundary, fault, environment, tenant or traffic scope, duration, stop thresholds, owner, communications route, and rollback before injection.
    expected_result: The fault remains within approved bounds and can be stopped immediately by the designated authority.
    evidence: experiment plan, approval, injection record, scope metrics, abort or rollback record, and communications log
    automation: deterministic fault-plan lint and isolated fixture suite
    owner: SRE owner
    frequency: before every experiment and after material topology change
    failure_action: do not inject; correct scope, rollback, or authority gaps and obtain renewed approval
    standards: [NIST-SSDF-1.1, NIST-IR-800-61R3]
  - id: ENG-CHAOS-002
    requirement: A chaos result must reconcile client-visible and business outcomes before it is used as resilience or release evidence.
    applicability: required for all experiments involving accepted work, durable state, retries, queues, or tenant-scoped actions
    procedure: Compare baseline and experiment results across client outcomes, idempotency records, queue state, traces, logs, and the business ledger; repeat after remediation.
    expected_result: Accepted work is neither lost nor duplicated, tenant scope remains intact, and recovery time is evidenced.
    evidence: fixture version, result report, correlation queries, ledger reconciliation, recovery record, finding, and owner sign-off
    automation: outcome-reconciliation fixture
    owner: Service owner
    frequency: each experiment and remediation retest
    failure_action: block resilience claim, contain affected path, open a finding, and repeat the exercise after repair
    standards: [NIST-SSDF-1.1, OTEL-SEMCONV-1.43.0]
---

# Chaos engineering experiment checklist

- [ ] State one critical outcome, steady state, fault hypothesis, and correctness boundary.
- [ ] Bound environment, tenant, traffic, duration, dependencies, and irreversible actions.
- [ ] Name the experiment owner, abort authority, communications channel, and rollback action.
- [ ] Capture a baseline and correlate client, queue, trace, log, and business-ledger evidence.
- [ ] Abort on threshold breach; preserve evidence before retrying or expanding scope.
- [ ] Reconcile accepted work, tenant scope, recovery time, and remediation retest before release use.
