---
id: APP-CONTROL-CATALOG
kind: appendix
title: Control catalog and evidence traceability
standards: [NIST-SSDF-1.1, OWASP-ASVS-5.0.0]
---

# Control catalog and evidence traceability

This appendix is the decision index for the handbook's checklist controls. It
does not create controls or replace the source checklists. Use the checklist as
the authoritative procedure; use this catalog to determine which control is in
scope, what evidence should exist, and which decision is blocked when evidence
is absent.

## How to use this catalog

1. Start with the product capability or change type, not a preferred control.
2. Open the cited checklist and execute its procedure using the stated owner,
   cadence, and failure action.
3. Link immutable evidence to the release decision, audit report, or exception
   record. A chat assertion or a passing status without inputs is not evidence.
4. Record non-applicability with a boundary and an accountable approver. Do not
   mark a control `not applicable` merely because a system has not yet been
   observed failing.

## Control status vocabulary

| Status | Meaning | Permitted release decision |
| --- | --- | --- |
| Pass | Required procedure ran and evidence meets the expected result. | Proceed if all other gates pass. |
| Fail | Expected result was not met. | Block; remediate or use the exception process. |
| Not applicable | The stated applicability condition is demonstrably absent. | Proceed only with recorded rationale. |
| Exception | A known failure is time-bounded and approved under governance. | Proceed only inside the approved scope and expiry. |
| Not evaluated | Evidence was not collected or cannot be trusted. | Treat as fail for required controls. |

## Audit operations and product surfaces

| Control | Trigger and decision | Minimum durable evidence | Primary source |
| --- | --- | --- | --- |
| `ENG-AUDIT-001` | Audit intake and evidence-plan approval | scope, owner, system inventory, evidence plan | `checklists/audit-execution.md` |
| `ENG-AUDIT-002` | Finding severity and closure decision | reproduction, impact analysis, decision record | `checklists/audit-execution.md` |
| `ENG-DISCOVERY-001` | Capability map is complete enough to audit | capability map, owners, data/authority boundaries | `checklists/master-checklist.md` |
| `ENG-DISCOVERY-002` | Critical journey claims can be released | state matrix, negative-path evidence, acceptance owner | `checklists/master-checklist.md` |
| `ENG-CLI-001` | CLI command is safe for automation | JSON contract, exit-code matrix, stderr capture | `checklists/cli-engineering.md` |
| `ENG-CLI-002` | Production-impacting CLI action is authorized | confirmation/approval trace, dry-run result, audit event | `checklists/cli-engineering.md` |
| `ENG-DESKTOP-001` | Desktop upgrade is recoverable | upgrade/rollback test, version/state migration record | `checklists/desktop-engineering.md` |
| `ENG-DESKTOP-002` | IPC and local privileged actions are bounded | IPC allowlist, authorization test, local log | `checklists/desktop-engineering.md` |
| `ENG-DASHBOARD-001` | Critical UI journey handles real states | state matrix, accessible screenshots, browser test | `checklists/dashboard-ui.md` |
| `ENG-DASHBOARD-002` | UI does not disclose unauthorized data | role test results, API authorization trace, review | `checklists/dashboard-ui.md` |

## Service, integration, and AI controls

| Control | Trigger and decision | Minimum durable evidence | Primary source |
| --- | --- | --- | --- |
| `ENG-API-001` | API contract or authorization change | contract diff, tenant/role tests, decision log | `checklists/api-backend.md` |
| `ENG-API-002` | Retriable write or asynchronous workflow | idempotency test, queue/dead-letter evidence, trace | `checklists/api-backend.md` |
| `ENG-INTEGRATION-001` | Third-party callback or webhook enables side effects | signature verification test, replay evidence, secret owner | `checklists/agent-integrations.md` |
| `ENG-INTEGRATION-002` | Tool or agent integration gains authority | tool allowlist, approval boundary, tenant/environment test | `checklists/agent-integrations.md` |
| `ENG-ROUTING-001` | Route/fallback policy changes | policy version, route matrix, fallback test | `checklists/routing-orchestration.md` |
| `ENG-ROUTING-002` | Cost/latency tradeoff changes | route traces, budget evidence, stop threshold | `checklists/routing-orchestration.md` |
| `ENG-MEMORY-001` | Memory capture, retrieval, or retention changes | data classification, isolation test, retention configuration | `checklists/memory-governance-security.md` |
| `ENG-MEMORY-002` | Deletion, export, or replay request | request record, deletion/replay trace, residual-data check | `checklists/memory-governance-security.md` |
| `ENG-AIEVAL-001` | Model, prompt, retrieval, tool, or evaluator changes | versioned dataset, per-case results, baseline comparison | `checklists/ai-quality-routing-evaluation.md` |
| `ENG-AIEVAL-002` | Route authority or safety policy changes | route traces, policy decision records, exception approvals | `checklists/ai-quality-routing-evaluation.md` |
| `ENG-AGENT-001` | Delegated agent workflow is introduced or changed | task graph, authority map, approval/replay evidence | `checklists/agent-orchestration.md` |
| `ENG-AGENT-002` | Agent can invoke a consequential tool | tool authorization test, containment trace, human decision | `checklists/agent-orchestration.md` |

## Operations, change, and assurance controls

| Control | Trigger and decision | Minimum durable evidence | Primary source |
| --- | --- | --- | --- |
| `ENG-RELPERF-001` | SLO, capacity, or load-sensitive release | load result, SLO/error-budget view, capacity decision | `checklists/reliability-performance.md` |
| `ENG-RELPERF-002` | Recovery objective or dependency boundary changes | recovery rehearsal, dependency evidence, owner acceptance | `checklists/reliability-performance.md` |
| `ENG-COMM-001` | Customer-facing capability or claim | measured-claim source, limitation, approver | `checklists/commercial-readiness.md` |
| `ENG-COMM-002` | Entitlement, billing, or reconciliation change | lifecycle test, reconciliation report, exception record | `checklists/commercial-readiness.md` |
| `ENG-RELENG-001` | Production release | qualification record, immutable artifact, release decision | `checklists/release-engineering.md` |
| `ENG-RELENG-002` | Canary, rollback, or abort decision | threshold dashboard, rollback rehearsal, event timeline | `checklists/release-engineering.md` |
| `ENG-PLAYWRIGHT-001` | Browser-critical journey change | deterministic local/browser result, screenshots, trace | `checklists/playwright-testing.md` |
| `ENG-PLAYWRIGHT-002` | Visual or accessibility regression decision | baseline diff, keyboard/semantic check, reviewer outcome | `checklists/playwright-testing.md` |
| `ENG-CHAOS-001` | Resilience claim or failure-mode release | experiment hypothesis, abort threshold, recovery evidence | `checklists/chaos-engineering.md` |
| `ENG-CHAOS-002` | Fault exposes customer/security impact | containment record, telemetry, follow-up verification | `checklists/chaos-engineering.md` |
| `ENG-MIGRATION-001` | Persistent-state migration | compatibility matrix, checkpoint/resume result, tenant logs | `checklists/database-migrations.md` |
| `ENG-MIGRATION-002` | High-risk data contract or recovery path | restore rehearsal, reconciliation results, acceptance | `checklists/database-migrations.md` |
| `ENG-OBS-001` | Telemetry schema or alerting release | trace/log/metric samples, redaction check, dashboard link | `checklists/production-observability.md` |
| `ENG-OBS-002` | Alert policy change | alert test, action/runbook link, false-positive review | `checklists/production-observability.md` |
| `ENG-SDKCOMPAT-001` | Public API/SDK change | compatibility matrix, consumer fixture, version decision | `checklists/api-sdk-compatibility.md` |
| `ENG-SDKCOMPAT-002` | Deprecation or breaking change | migration guide, telemetry/adoption evidence, sunset approval | `checklists/api-sdk-compatibility.md` |
| `ENG-CVRA-001` | Release-pipeline gate changes | gate definition, failing-path result, artifact links | `checklists/continuous-verification-release-automation.md` |
| `ENG-CVRA-002` | Promotion automation changes | provenance, approval event, rollback/containment result | `checklists/continuous-verification-release-automation.md` |

## Evidence review questions

Before accepting any control, the reviewer should be able to answer: What exact
system version was tested? Which tenant, role, data class, and environment were
in scope? What would a failure have looked like? Where is the raw result? Who
can independently repeat the procedure? If any answer is unknown, record the
control as not evaluated rather than inferring a pass.
