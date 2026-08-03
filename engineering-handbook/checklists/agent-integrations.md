---
id: CL-INT-01
kind: checklist
title: Agent and integration release checklist
chapter: CH-07
controls:
  - id: ENG-INT-001
    requirement: Every inbound callback verifies the original signed bytes, provider environment, tenant binding, and replay key before any state change.
    applicability: required for signed webhooks and provider callbacks
    procedure: Submit valid, altered, stale, duplicate, cross-environment, and cross-tenant fixture callbacks.
    expected_result: Only a valid current callback mutates state once in its intended tenant/environment.
    evidence: Signature test report, event-deduplication record, correlation ID, and source revision.
    automation: local callback contract suite
    owner: Integration owner
    frequency: every callback or provider change
    failure_action: block enablement and rotate/disable affected integration when exposure exists
    standards: [OWASP-ASVS-5.0.0, OWASP-API-TOP10-2023]
  - id: ENG-INT-002
    requirement: High-impact agent tool actions require explicit user-owned approval at the execution boundary.
    applicability: required for external delivery, financial, destructive, or privileged tool actions
    procedure: Attempt execution with absent, expired, cross-tenant, and valid approval records.
    expected_result: Only a current matching approval permits execution; preview remains non-mutating.
    evidence: Tool test output, approval audit record, and policy version.
    automation: tool-authority contract suite
    owner: Product owner
    frequency: tool or policy change
    failure_action: block publication and revoke affected tool scope
    standards: [NIST-SSDF-1.1]
---

# Agent and integration release checklist

- [ ] Map every scope, action, data class, owner, disable switch, and approval rule.
- [ ] Exercise callback signature, replay, consent revocation, rate limit, and outage paths.
- [ ] Prove tools cannot convert untrusted retrieved text into execution authority.
