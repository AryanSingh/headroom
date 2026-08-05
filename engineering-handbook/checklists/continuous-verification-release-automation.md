---
id: CL-CONTINUOUS-VERIFICATION-01
kind: checklist
title: Continuous verification and release automation checklist
chapter: CH-20
standards: [NIST-SSDF-1.1, NIST-IR-800-61R3, OWASP-ASVS-5.0.0]
controls:
  - id: ENG-CV-001
    requirement: Every production promotion must evaluate versioned required checks against the exact source and artifact candidate, block on failures, and retain resolvable evidence for each decision.
    applicability: required for services, clients, infrastructure, data changes, configuration, and release automation that can affect production
    procedure: Declare required checks, owners, policy version, candidate identifiers, evidence references, stop conditions, waiver authority, and decision output; exercise a failed check and a passing rerun in isolation.
    expected_result: No candidate is promoted with a failed, skipped, unverifiable, or wrongly scoped required check unless a time-bounded approved exception is attached.
    evidence: build provenance, policy version, check outputs, immutable candidate identifiers, waiver record, release decision, and fixture report
    automation: deterministic policy fixture plus CI policy evaluation and artifact-attestation verification
    owner: Release engineering owner
    frequency: every promotion and any pipeline, policy, dependency, or environment change
    failure_action: block promotion, preserve evidence, repair the check or policy, obtain a time-bounded exception when authorized, and rerun qualification
    standards: [NIST-SSDF-1.1, OWASP-ASVS-5.0.0]
  - id: ENG-CV-002
    requirement: Release automation must provide controlled rollout, observable verification, rollback or containment triggers, and accountable post-release evidence.
    applicability: required for customer-impacting deployments, feature flags, infrastructure changes, data changes, and emergency releases
    procedure: Define rollout cohorts, health and business thresholds, observation window, rollback owner, reversible action, incident escalation, and evidence locations; rehearse a threshold breach and record containment.
    expected_result: An accountable operator can halt or reverse an unsafe rollout using the declared evidence before avoidable customer impact expands.
    evidence: rollout plan, threshold configuration, deployment record, telemetry links, rollback rehearsal, incident or release decision, and post-release verification record
    automation: staged rollout gate, threshold monitor, rollback rehearsal, and post-release evidence collector
    owner: Service owner
    frequency: every production release, quarterly recovery rehearsal, and after automation changes
    failure_action: halt rollout, contain exposure, invoke incident response when thresholds or integrity boundaries breach, repair automation, and repeat the rehearsal
    standards: [NIST-IR-800-61R3, NIST-SSDF-1.1]
---

# Continuous verification and release automation checklist

- [ ] Bind every required check to the exact source revision, build artifact, configuration, and target environment.
- [ ] Define a named owner, pass threshold, failure action, evidence reference, waiver authority, and expiry for every release gate.
- [ ] Prove a failed required check blocks promotion and a corrected rerun supplies immutable evidence before approval.
- [ ] Define staged rollout cohorts, observation windows, health and customer-outcome thresholds, stop authority, and rollback action.
- [ ] Retain the release decision, artifacts, checks, approvals, waivers, rollout telemetry, and post-release verification record.
