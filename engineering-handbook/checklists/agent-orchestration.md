---
id: CL-AGENT-ORCH-01
kind: checklist
title: Agent orchestration control checklist
chapter: CH-13
controls:
  - id: ENG-AGENT-001
    requirement: Every agent delegation must use an explicit, time-bounded authority grant that limits tenant, tool, action, budget, and escalation path.
    applicability: required for workflows that invoke tools, services, external systems, or delegated agents
    procedure: Inspect the task envelope and broker decision; verify identity, correlation ID, allowed tools, tenant scope, expiry, budget, and owner before execution.
    expected_result: Each invocation is authorized by a matching non-ambient grant and scope mismatches are denied before side effect.
    evidence: task envelope, capability record, policy decision, trace event, denied-request record, and owner review
    automation: authority-chain verifier and cross-scope negative fixture
    owner: Agent platform owner
    frequency: every new workflow, capability change, and quarterly control review
    failure_action: disable the capability, stop queued work, rotate affected grants, investigate traces, and require reapproval before re-enablement
    standards: [NIST-AI-RMF-1.0, OWASP-LLM-TOP10-2025]
  - id: ENG-AGENT-002
    requirement: Sensitive or irreversible agent actions must require explicit approval and authoritative outcome reconciliation.
    applicability: required for writes, external communications, financial actions, destructive operations, and cross-system state changes
    procedure: Execute approval and adverse-result fixtures; verify the broker blocks unapproved action, records the approver, and reconciles the authoritative system result before completion.
    expected_result: The workflow cannot claim success from generated text alone and retains a complete approval-to-outcome chain.
    evidence: approval record, invocation request, authoritative response, reconciliation result, trace, and incident linkage where applicable
    automation: approval-gate integration test and outcome-reconciliation query
    owner: Workflow owner
    frequency: before release, after policy change, and for every high-impact action class
    failure_action: block the workflow, contain partial effects, notify the accountable owner, and create a remediation finding
    standards: [NIST-AI-600-1, NIST-SSDF-1.1]
---

# Agent orchestration control checklist

- [ ] Assign one correlation ID, owner, objective, and retention class to each workflow.
- [ ] Verify task scope and issued tool capability before every invocation.
- [ ] Deny cross-tenant, expired, excessive-budget, and unapproved actions before side effect.
- [ ] Record delegation, policy, approval, invocation, result, retry, and terminal state.
- [ ] Reconcile authoritative outcomes and test kill-switch recovery before release.
