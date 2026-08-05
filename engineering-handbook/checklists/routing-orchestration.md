---
id: CL-ROUTE-01
kind: checklist
title: Routing and orchestration release checklist
chapter: CH-08
controls:
  - id: ENG-ROUTE-001
    requirement: Every production route decision must be derived from a versioned policy with tenant, data-classification, safety, and residency predicates preserved through fallback.
    applicability: required for provider, model, workflow, region, or tool routing
    procedure: Run allowed, denied, timeout, budget, and cross-tenant fixtures while recording selected and rejected candidates.
    expected_result: Every result names a policy revision and reason code; no fallback crosses a declared boundary.
    evidence: policy artifact, fixture report, decision records, and correlation IDs
    automation: deterministic routing contract suite
    owner: Routing owner
    frequency: every policy or provider change
    failure_action: block release, disable unsafe fallback, and notify security owner if data left an approved boundary
    standards: [NIST-SSDF-1.1, NIST-AI-RMF-1.0, OWASP-ASVS-5.0.0]
  - id: ENG-ROUTE-002
    requirement: Orchestrated retries, queueing, cancellation, and dead-letter handling must not duplicate high-impact work or silently change approval semantics.
    applicability: required for asynchronous or retrying workflows
    procedure: Simulate acknowledgement loss, timeout, cancellation, budget exhaustion, and retry exhaustion for a privileged fixture.
    expected_result: One action occurs at most once; queue and failure records preserve tenant, correlation ID, and approval state.
    evidence: worker trace, deduplication record, dead-letter record, and replay result
    automation: orchestration failure-path suite
    owner: SRE owner
    frequency: release and worker-policy change
    failure_action: block release and drain or disable affected queue
    standards: [NIST-SSDF-1.1, NIST-AI-RMF-1.0]
---

# Routing and orchestration release checklist

- [ ] Reconcile workload inventory to versioned policy and provider allowlists.
- [ ] Test denied, timeout, budget, queue, cancellation, and retry-exhaustion paths.
- [ ] Verify every fallback preserves tenant, residency, data, safety, and approval boundaries.
