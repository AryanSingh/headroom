---
id: CH-09
kind: chapter
title: Memory, Governance, and Security Engineering Audit
purpose: Build and assess memory systems whose retention, retrieval, access, deletion, and AI-assisted use are controlled and auditable.
audience: [Platform engineers, security engineers, privacy engineers, AI engineers, SREs]
scope: Memory ingestion, classification, tenant isolation, retrieval, retention, deletion, provenance, evaluation, and incident handling.
applicability: Conversation memory, retrieval stores, vector indexes, caches, profiles, and agent state.
owners: [Memory owner, security owner, privacy owner]
inputs: [data inventory, retention schedule, access model, retrieval policy, deletion fixtures]
outputs: [memory evidence register, control findings, deletion gate, risk decision]
dependencies: [NIST-SSDF-1.1, NIST-AI-RMF-1.0, OWASP-ASVS-5.0.0]
standards: [NIST-SSDF-1.1, NIST-AI-RMF-1.0, OWASP-ASVS-5.0.0]
---

# Memory, Governance, and Security Engineering Audit

## Purpose, audience, scope, and applicability

Memory turns prior data into future influence. Audit what enters memory, who can retrieve it, how it is scoped, how it expires, and how a deletion or incident request propagates through indexes, caches, and derived artifacts.

## Concepts and engineering principles

Use explicit purpose, classification, tenant scope, provenance, and retention at ingestion. Retrieval must enforce authorization before ranking; a highly relevant record from another tenant is still forbidden. Treat generated summaries and embeddings as governed derivatives, and use evaluation sets to measure whether retrieval is useful without accepting unsafe recall.

## Roles and accountability

The memory owner owns schema, retrieval behavior, and deletion propagation. The privacy owner owns purpose and retention decisions. Security owns access control and incident containment. The AI owner owns evaluation and safety monitoring; the release owner accepts evidence.

## Prerequisites and required inputs

Collect memory types, sources, classifications, tenant/subject identifiers, access rules, retention schedule, index topology, cache topology, delete workflow, evaluation set, incident contacts, and sanitized fixtures.

## Standard operating procedure

1. Inventory each memory store, derivative, owner, purpose, classification, retention rule, and delete capability.
2. Test same-tenant retrieval, cross-tenant denial, role denial, expired-record exclusion, and source-provenance display.
3. Submit a deletion request and verify removal from primary storage, indexes, caches, exports, and future retrieval results.
4. Inspect ingestion for unapproved secrets, credentials, regulated data, and untrusted instructions.
5. Evaluate retrieval on a versioned safe set; record relevance, citation, leakage, and refusal outcomes separately.
6. Exercise degraded index, stale cache, revocation, and incident-containment paths.
7. Record evidence and set a time-bounded exception only through the governance process.

## Worked example

[Product Atlas memory governance evidence](../examples/memory-governance/README.md) shows a support-memory record that is retrievable only by its tenant, excluded after expiration, and absent from the index and cache after a verified deletion request.

## Automation examples

```python
assert retrieve(tenant="atlas-a", query="renewal") == ["mem-a-17"]
assert retrieve(tenant="atlas-b", query="renewal") == []
delete_subject("subject-a-9")
assert search_all_layers("subject-a-9") == []
```

## Audit prompts

Use [Opus](../prompts/opus/ch09-memory-risk-assessment.md), [Sonnet](../prompts/sonnet/ch09-deletion-evidence-review.md), and [Haiku](../prompts/haiku/ch09-memory-inventory.md) for governance-risk assessment, deletion-chain review, and compact inventory normalization.

## Workflow checklist

Run [CL-MEM-01](../checklists/memory-governance-security.md) before changing ingestion, retrieval, retention, access rules, index topology, or an AI evaluation set.

## Evidence requirements and retention guidance

Retain policy version, classification decision, source provenance, fixture identity, authorization verdict, deletion job IDs, per-layer deletion results, evaluation revision, and sanitized trace IDs. Do not retain the sensitive memory content merely to prove a control.

## Example findings with severity and remediation

**Critical — MEM-ATLAS-01.** A deleted tenant profile disappeared from the primary table but remained retrievable from a vector index for 24 hours. Remediation: make deletion fan out transactionally or asynchronously with a blocking retrieval tombstone, monitor backlog, and verify all layers before closure.

## KPIs and domain scorecard

The [memory KPI catalog](../scorecards/memory-kpis.md) tracks scope-enforcement coverage and verified deletion completion. One cross-tenant retrieval or unverified deletion is a release blocker.

## Common failure patterns and diagnostic guidance

- An embedding index is treated as non-sensitive because it is not the original text.
- A cache returns a record after the source authorization is revoked.
- An evaluator rewards relevance but does not score tenant leakage or unsupported citation.
- A retention job deletes the primary record while an export or backup workflow remains undocumented.

## Exit criteria

Exit when every memory type has accountable ownership, purpose, access and retention policy, tested scope enforcement, verified deletion propagation, evaluation evidence, and an incident disable path.

## Related runbooks, controls, examples, and templates

Use the memory checklist, evidence-register, threat-model, incident-review, and AI-evaluation-report templates. Coordinate confirmed exposure with the incident response runbook.
