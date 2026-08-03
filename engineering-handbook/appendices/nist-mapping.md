---
id: APP-NIST-MAPPING
kind: appendix
title: NIST mapping and evidence guide
standards: [NIST-SSDF-1.1, NIST-IR-800-61R3, NIST-AI-RMF-1.0, NIST-AI-600-1]
---

# NIST mapping and evidence guide

This appendix turns the handbook’s registered NIST sources into evidence-led
work. It intentionally maps outcomes to existing controls rather than claiming
formal certification. The official publications remain authoritative; record
their pinned registry IDs in assessment and exception records.

## Source-to-workflow map

| Source ID | Operational purpose | Handbook procedures and controls | Evidence package |
| --- | --- | --- | --- |
| `NIST-SSDF-1.1` | Make secure development practices repeatable across planning, implementation, release, and response. | Audit execution; API, integration, migration, release, and continuous-verification checklists; `ENG-API-001/002`, `ENG-MIGRATION-001/002`, `ENG-RELENG-001/002`, `ENG-CVRA-001/002`. | source/artifact identity, review/test outputs, release gate, remediation and exception records. |
| `NIST-IR-800-61R3` | Integrate preparation, detection, containment, recovery, and lessons learned with risk management. | Reliability, chaos, observability, migration, release chapters; `ENG-RELPERF-002`, `ENG-CHAOS-002`, `ENG-MIGRATION-002`, `ENG-OBS-002`. | incident timeline, scope/impact, containment decision, recovery rehearsal, post-incident action owners. |
| `NIST-AI-RMF-1.0` | Govern, map, measure, and manage AI risk across a lifecycle. | Routing, memory, agent orchestration, and AI evaluation; `ENG-ROUTING-001/002`, `ENG-AIEVAL-001/002`, `ENG-AGENT-001/002`. | system/context map, risk register, evaluation dataset, measures, route/tool policy, residual-risk decision. |
| `NIST-AI-600-1` | Extend AI risk management for generative-AI-specific harms and controls. | Memory/governance, agent orchestration, AI evaluation; `ENG-MEMORY-001/002`, `ENG-AIEVAL-001/002`, `ENG-AGENT-001/002`. | prompt/tool threat model, adversarial cases, provenance, human escalation, monitoring/incident evidence. |

## SSDF evidence lifecycle

| Lifecycle point | Practical action | Do not accept | Example evidence |
| --- | --- | --- | --- |
| Plan | Identify assets, data, authority, suppliers, and security objectives before change. | A generic security sign-off with no changed boundary. | capability map, threat model, named owner. |
| Protect | Bound build, test, secrets, dependencies, and deployment authority. | A pipeline badge with unknown artifact provenance. | immutable build ID, dependency report, signed approval event. |
| Produce | Implement secure defaults and test boundary behavior. | Only happy-path unit tests. | authorization, idempotency, browser, or compatibility fixture results. |
| Respond | Receive, triage, remediate, learn, and verify vulnerabilities/incidents. | Closure based solely on ticket status. | finding record, fix test, deployment evidence, retest result. |

## Incident and recovery decision sequence

Apply this sequence to a security event, a migration integrity concern, or a
release regression:

1. **Stabilize evidence.** Preserve relevant trace IDs, versions, timestamps,
   decision logs, and a safe copy of the failing input. Avoid broad data
   collection that increases exposure.
2. **Classify impact.** State affected tenants, confidentiality/integrity/
   availability implications, uncertainty, and immediate business boundary.
3. **Contain with authority.** Disable a route, revoke a callback, pause a
   migration, roll back a release, or limit a tool only through a recorded
   accountable decision.
4. **Recover and reconcile.** Prove the intended state, not just process
   completion: reconcile tenant outcomes, verify authorization, or replay a
   controlled fixture.
5. **Learn and verify.** Turn the cause into a control, test, runbook change,
   or risk acceptance. Assign an owner and retest date.

## AI risk review matrix

| AI risk-management action | Required question | Evidence and decision |
| --- | --- | --- |
| Govern | Who owns the model, prompt, route, data, tool, and release decision? | named roles, policy version, exception authority. |
| Map | What task, users, data, authority, and failure harms are in scope? | capability/threat map and task-class inventory. |
| Measure | How are quality, safety, route correctness, and disagreement measured? | versioned dataset, rubric, raw results, human adjudications. |
| Manage | What blocks, limits, escalates, rolls back, or monitors the risk? | thresholds, approval workflow, alert/runbook, post-release review. |

## Practical limits of a mapping

An implementation may align to selected NIST outcomes without satisfying every
practice or profile action. Never label a product “NIST compliant” from this
appendix alone. State the specific source version, assessed scope, evidence
period, excluded systems, residual risks, and accountable decision maker.

## Review cadence

Review the mapping when a registered source changes, an incident exposes a
missing procedure, an AI system gains new authority, or a release mechanism
changes. At least annually, sample one completed control from each mapped
workflow and check that the evidence remains independently reproducible.
