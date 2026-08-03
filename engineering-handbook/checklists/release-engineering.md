---
id: CL-RELENG-01
kind: checklist
title: Release engineering production checklist
chapter: CH-12
controls:
  - id: ENG-RELENG-001
    requirement: A production release must promote an immutable, attributable artifact whose source, dependencies, tests, approvals, and target environment are recorded.
    applicability: required for production services, client applications, infrastructure, data changes, policies, and AI configuration releases
    procedure: Verify the release record binds the approved source revision, dependency evidence, artifact digest, test run IDs, configuration revision, approvals, and deployment target.
    expected_result: The deployed digest matches the tested candidate and every release decision can be traced to one approved evidence package.
    evidence: release record, source revision, artifact digest, dependency record, test evidence, approval, and deployment audit event
    automation: provenance and promotion-integrity gate
    owner: Release owner
    frequency: every production promotion and any pipeline, signing, or deployment-policy change
    failure_action: stop promotion, invalidate the candidate, rebuild and retest from declared inputs, and open a supply-chain finding if provenance cannot be established
    standards: [NIST-SSDF-1.1, OWASP-ASVS-5.0.0]
  - id: ENG-RELENG-002
    requirement: Each release must have observable stop criteria and a tested rollback that restores a safe service state across all affected components.
    applicability: required for customer-impacting deployments, schema changes, asynchronous workers, feature flags, and policy releases
    procedure: Run staged rollout fixtures, validate telemetry against declared thresholds, inject an adverse condition, and execute component-complete rollback in an isolated environment.
    expected_result: Rollout halts at the threshold, rollback restores the approved prior state, and no accepted business outcome is duplicated or lost.
    evidence: rollout plan, telemetry query, fault fixture, traffic decision, rollback log, outcome-integrity result, and owner approval
    automation: canary threshold and rollback rehearsal suite
    owner: SRE owner
    frequency: each release class change, quarterly rehearsal, and every high-risk promotion
    failure_action: block promotion, reduce traffic or roll back, preserve evidence, repair the plan, and rerun the rehearsal
    standards: [NIST-SSDF-1.1, OTEL-SEMCONV-1.43.0]
---

# Release engineering production checklist

- [ ] Bind the approved source, dependencies, artifact digest, configuration revision, tests, and target to one release record.
- [ ] Promote one immutable artifact through staged environments; do not rebuild at promotion.
- [ ] Confirm secrets are referenced through approved mechanisms and absent from logs and evidence.
- [ ] Observe canary outcomes against declared stop criteria and record the traffic decision.
- [ ] Prove component-complete rollback, post-deployment correctness, communications, and follow-up ownership.
