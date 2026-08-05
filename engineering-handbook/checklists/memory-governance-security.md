---
id: CL-MEM-01
kind: checklist
title: Memory governance and security release checklist
chapter: CH-09
controls:
  - id: ENG-MEM-001
    requirement: Memory ingestion and retrieval must enforce purpose, classification, tenant scope, and authorization before ranking or exposing any derivative.
    applicability: required for memory stores, retrieval indexes, profiles, caches, and agent state
    procedure: Test same-tenant, cross-tenant, role-denied, expired, and revoked-access fixtures across every retrieval path.
    expected_result: Only authorized current records are returned; cross-tenant, expired, and revoked records are absent.
    evidence: scoped query traces, authorization verdicts, policy version, and sanitized fixture results
    automation: memory access contract suite
    owner: Memory owner
    frequency: release and schema or retrieval change
    failure_action: block release, disable affected retrieval path, and escalate suspected exposure to security owner
    standards: [OWASP-ASVS-5.0.0, NIST-SSDF-1.1, NIST-AI-RMF-1.0]
  - id: ENG-MEM-002
    requirement: A deletion or retention event must remove or tombstone memory from primary storage, indexes, caches, exports, and future retrieval within the documented service objective.
    applicability: required where memory can contain subject, tenant, or regulated data
    procedure: Submit a fixture deletion and verify per-layer completion, retrieval absence, backlog status, and failure alerting.
    expected_result: No layer returns the deleted record after the service objective; delayed work is visible and retrieval remains blocked by tombstone.
    evidence: deletion job IDs, per-layer acknowledgements, retrieval tests, backlog dashboard, and alert record
    automation: all-layer deletion verification suite
    owner: Privacy owner
    frequency: release and storage or retention change
    failure_action: stop affected ingestion, apply retrieval tombstone, and open incident assessment when exposure is possible
    standards: [NIST-SSDF-1.1, NIST-AI-RMF-1.0, OWASP-ASVS-5.0.0]
---

# Memory governance and security release checklist

- [ ] Inventory memory purpose, classification, owner, retention, access policy, and all derivative layers.
- [ ] Test tenant/role isolation, expiry, revocation, provenance, and safe evaluation behavior.
- [ ] Verify deletion across storage, index, cache, export, and future retrieval paths.
