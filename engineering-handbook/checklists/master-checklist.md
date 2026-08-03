---
id: CL-DISCOVERY-01
kind: checklist
title: Master capability-discovery checklist
chapter: CH-02
controls:
  - id: GOV-MAP-001
    requirement: Each high-priority capability is mapped from an observable outcome to entry points, owner, dependencies, data, runtime signal, and verification evidence.
    applicability: required for material product, release, security, and integration reviews
    procedure: Review the capability matrix and sample one source link plus one runtime or test artifact per high-priority row.
    expected_result: Every high-priority row has no blank owner, entry point, or verification-status field.
    evidence: Versioned capability matrix, source links, test report or runtime observation.
    automation: inventory extractor plus manual evidence sampling
    owner: Discovery lead
    frequency: before material review and at material change
    failure_action: record a discovery gap and block dependent approval until risk is accepted or evidence is added
    standards: [NIST-SSDF-1.1, OWASP-SAMM-2.1]
  - id: GOV-MAP-002
    requirement: Configured external providers and feature-flagged paths are classified by observed reachability rather than configuration alone.
    applicability: required where the product uses providers, queues, feature flags, or optional runtime routes
    procedure: Compare deployment/configuration records with a safe runtime observation, test fixture, or explicitly documented limitation.
    expected_result: Each relevant dependency is tagged observed, configured-only, unreachable, disabled, or unknown.
    evidence: Configuration snapshot, telemetry/query output, test output, or limitation record.
    automation: read-only configuration and telemetry inventory
    owner: Service owner
    frequency: release and provider/flag change
    failure_action: create a verification task for high-risk unknown or unreachable paths
    standards: [NIST-SSDF-1.1]
---

# Master capability-discovery checklist

## Intake

- [ ] Name the decision, accountable owner, time boundary, and source revision.
- [ ] Define outcomes, not packages, as the top-level capability rows.
- [ ] Mark privacy-sensitive, financial, safety-critical, and externally exposed paths.

## Map and verify

- [ ] Record route, command, job, webhook, SDK, and operator entry points.
- [ ] Link authorization, mutation, persistence, provider, queue, and recovery paths.
- [ ] Attach at least one source or configuration artifact and one test/runtime artifact per high-priority row.
- [ ] Tag feature-flag and provider state as observed, configured-only, unreachable, disabled, or unknown.

## Decide and refresh

- [ ] Create a finding or verification task for every critical unknown.
- [ ] Confirm capability and service owners reviewed their rows.
- [ ] Version the map and declare its next refresh trigger.

Product Atlas uses this checklist before a subscription release: the billing
retry worker is listed even though it has no dashboard route, because it can
create a customer-impacting duplicate-charge outcome.
