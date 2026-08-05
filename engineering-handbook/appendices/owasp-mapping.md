---
id: APP-OWASP-MAPPING
kind: appendix
title: OWASP mapping and application guide
standards: [OWASP-ASVS-5.0.0, OWASP-TOP10-2025, OWASP-API-TOP10-2023, OWASP-WSTG-4.2, OWASP-SAMM-2.1, OWASP-LLM-TOP10-2025]
---

# OWASP mapping and application guide

This appendix maps handbook procedures to the OWASP sources pinned in the
standards registry. It is a practical applicability guide, not a restatement
of OWASP requirements. Teams must consult the cited official source for the
complete requirement or test method, retain the version in the evidence record,
and use the handbook's controls for operational ownership and release action.

## Source selection

| Source ID | Use it when | Handbook entry points | Evidence that makes the mapping credible |
| --- | --- | --- | --- |
| `OWASP-ASVS-5.0.0` | Verifying application security requirements for a product, API, local client, or deployment. | Chapters 4, 6, 9, 10, 14, 16, 18; related checklists. | versioned security tests, authorization traces, configuration review, remediation decision. |
| `OWASP-TOP10-2025` | Framing web-application risk during threat modeling, audit scoping, or executive reporting. | Chapters 1, 5, 6, 9, 14. | risk register tied to a concrete asset, trust boundary, and control. |
| `OWASP-API-TOP10-2023` | Auditing exposed APIs, resource authorization, inventory, rate limits, or third-party API paths. | Chapters 6, 7, 18. | contract inventory, cross-tenant/role results, quotas, webhook/replay tests. |
| `OWASP-WSTG-4.2` | Planning reproducible web-security testing. | Chapters 5, 14; audit execution workflow. | test case ID, environment, request/response capture with secrets removed, result and retest. |
| `OWASP-SAMM-2.1` | Assessing assurance program maturity rather than a single feature. | Chapters 1, 11, 12, 20; governance artifacts. | maturity baseline, prioritized improvement backlog, accountable owner and review cadence. |
| `OWASP-LLM-TOP10-2025` | Assessing LLM prompts, tools, retrieval, routing, memory, and agent authority. | Chapters 7–9, 13, 17. | threat model, adversarial/evaluation cases, tool approvals, isolation and trace evidence. |

## Operational mapping by risk area

| Risk area | Required handbook procedure | Primary controls | Review question |
| --- | --- | --- | --- |
| Broken object/property/function authorization | Test tenant, role, and object boundaries for every protected API and UI journey. | `ENG-API-001`, `ENG-DASHBOARD-002`, `ENG-SDKCOMPAT-001` | Can a valid low-privilege identity read or mutate another tenant’s object? |
| Callback forgery or replay | Verify signature before parsing/side effects; bind event, tenant, environment, timestamp, and replay window. | `ENG-INTEGRATION-001`, `ENG-API-002` | Can a captured valid callback produce a second side effect? |
| Unsafe agent/tool authority | Model the delegation graph and require approval before consequential actions. | `ENG-INTEGRATION-002`, `ENG-AGENT-001/002`, `ENG-AIEVAL-002` | Which tool call can change state, and what policy/human approval preceded it? |
| Memory leakage or retention failure | Classify memory, enforce retrieval isolation, and prove delete/export/replay outcomes. | `ENG-MEMORY-001/002` | Can one tenant retrieve, reconstruct, or retain another tenant’s context? |
| Input/output handling risk | Exercise negative cases at UI, API, integration, and model boundaries; keep safe evidence. | `ENG-API-001`, `ENG-PLAYWRIGHT-001/002`, `ENG-AIEVAL-001` | Does an untrusted value change control flow, reveal sensitive data, or bypass a gate? |
| Weak authentication/session handling | Test anonymous, expired, revoked, and privilege-changed sessions in critical journeys. | `ENG-DASHBOARD-002`, `ENG-API-001`, `ENG-DESKTOP-002` | Does authorization remain correct after session or role state changes? |
| Logging/monitoring gaps | Correlate authorized operational events without recording secrets; prove alerts are actionable. | `ENG-OBS-001/002`, `ENG-RELENG-002` | Can an operator connect a customer impact to a bounded trace and runbook? |
| Vulnerable change/release process | Make verification and provenance promotion gates non-bypassable; rehearse rollback. | `ENG-RELENG-001/002`, `ENG-CVRA-001/002` | Can an artifact be promoted without the exact gate evidence and accountable approval? |

## Assessment procedure

1. Identify the interface and trust boundary: browser, API, desktop IPC,
   callback, SDK, model/tool, memory, or deployment pipeline.
2. Choose the source whose scope best fits the boundary; do not use a generic
   Top 10 category as proof that a technical requirement was tested.
3. Select the corresponding handbook control and run its documented procedure.
4. Retain a safe reproduction artifact, raw test result or trace reference,
   observed result, severity rationale, and owner decision.
5. If the condition is accepted temporarily, use the exception-management
   process with expiry, compensating control, and follow-up verification.

## Common mapping failures

- **Citation without verification:** Listing an OWASP source in a slide is not
  evidence that a tenant boundary or agent tool was tested.
- **Category-only security review:** Top 10 categories help scope work, but the
  evidence needs a concrete request, state transition, and expected denial or
  safe outcome.
- **Green unit tests without deployed-boundary evidence:** A handler test may
  miss gateway, identity, configuration, queue, or callback behavior.
- **Security evidence that leaks secrets:** Store redacted request/response
  references and access-controlled raw artifacts; never paste credentials into
  the handbook, ticket, or screenshot.
