---
id: CH-13
kind: chapter
title: Agent Orchestration Engineering Audit
purpose: Build and assess agent orchestration systems that keep authority, state, tools, delegation, and recovery observable and bounded.
audience: [AI platform engineers, application engineers, security engineers, SREs, QA, engineering leaders]
scope: Agent identity, task delegation, tool authority, execution isolation, state transitions, retries, recovery, evaluation, and audit evidence.
applicability: Single-agent workflows, multi-agent systems, coding harnesses, workflow engines, support automation, and human-in-the-loop operations.
owners: [Agent platform owner, workflow owner, security owner, SRE owner]
inputs: [agent inventory, tool registry, authority policy, workflow definitions, traces, evaluation results, incident records]
outputs: [orchestration risk assessment, control evidence, remediation plan, and release decision]
dependencies: [NIST-AI-RMF-1.0, NIST-AI-600-1, OWASP-LLM-TOP10-2025, NIST-SSDF-1.1]
standards: [NIST-AI-RMF-1.0, NIST-AI-600-1, OWASP-LLM-TOP10-2025, NIST-SSDF-1.1]
---

# Agent Orchestration Engineering Audit

## Purpose, audience, scope, and applicability

Agent orchestration is a production control plane, not a prompt chain. Audit whether every actor has a bounded identity, an explicit authority grant, observable state transitions, and a safe recovery path. Apply this chapter to systems that delegate work among models, tools, services, or humans.

## Concepts and engineering principles

Separate planning from execution, and capability discovery from authority to act. A delegated task must carry a correlation ID, declared inputs, permitted tools, stop conditions, and an accountable owner. Treat agent memory and tool output as untrusted until validated at the authorization boundary. Prefer narrow, revocable capabilities over ambient credentials.

## Roles and accountability

The agent platform owner owns the orchestration runtime and policy enforcement. The workflow owner defines business outcomes and acceptable escalation. Security approves sensitive capabilities and reviews authority changes. SRE owns runtime availability, kill switches, and degraded-mode recovery. A human approver owns high-impact actions that cannot be reversed safely.

## Prerequisites and required inputs

Collect an agent and tool inventory, authority matrix, task graph, input classification, model configuration, trace samples, retry policy, evaluation results, incident history, and emergency-disable procedure. Every external side effect must have an identified compensating or containment action.

## Standard operating procedure

1. Assign each orchestration run a durable correlation ID, owner, declared objective, and retention class.
2. Validate task inputs and classify the requested action before a planner can delegate it.
3. Issue the worker only the tools, tenant scope, time limit, and budget required for that task.
4. Record every delegation, tool proposal, approval, invocation, result, retry, and terminal state in the trace.
5. Require explicit approval for irreversible, cross-tenant, financial, destructive, or external-communication actions.
6. Stop retries when a policy, authority, budget, or safety condition fails; escalate rather than silently broadening permissions.
7. Reconcile final business outcomes against the original objective and retain sanitized evidence for review.

## Worked example

[Product Atlas delegated account-remediation example](../examples/agent-orchestration/README.md) shows a support triage agent delegating a tenant-scoped entitlement correction, blocking an attempted cross-tenant lookup, and escalating the final write for human approval.

## Automation examples

```bash
atlasctl agents run --workflow entitlement-remediation --tenant atlas-eu-42 --request req-913 --dry-run --format json
atlasctl agents approve --run run-913 --action entitlement-write --approver oncall-manager
atlasctl agents trace verify --run run-913 --require-complete-authority-chain
```

## Audit prompts

Use [Opus](../prompts/opus/ch13-orchestration-risk-synthesis.md), [Sonnet](../prompts/sonnet/ch13-delegation-evidence-review.md), and [Haiku](../prompts/haiku/ch13-agent-tool-inventory.md) for system-wide risk synthesis, one-run evidence review, and inventory normalization.

## Workflow checklist

Run [CL-AGENT-ORCH-01](../checklists/agent-orchestration.md) before enabling a new workflow, granting a tool capability, or changing delegation, approval, retry, or retention policy.

## Evidence requirements and retention guidance

Retain sanitized task definitions, correlation IDs, model and policy versions, authority grants, approvals, tool requests and results, state changes, evaluation evidence, and remediation ownership. Never retain raw credentials, unnecessary customer content, or unrestricted tool output when references and hashes are sufficient.

## Example findings with severity and remediation

**High — AGENT-ATLAS-01.** A remediation worker inherited a support-wide search tool and attempted to inspect a tenant not named in the task. Remediation: mint tenant-bound capability tokens, reject mismatched identifiers before tool invocation, and alert the workflow owner on any denied cross-scope request.

## KPIs and domain scorecard

The [agent orchestration KPI catalog](../scorecards/agent-orchestration-kpis.md) measures bounded-authority execution and reviewable recovery. High throughput does not compensate for an action whose authority chain cannot be reconstructed.

## Common failure patterns and diagnostic guidance

- A planner passes user-provided text directly into a tool call without policy or schema validation.
- A retry changes model, tool, tenant scope, or budget without recording a new decision.
- A worker reports success from model text while the authoritative system rejected or never completed the action.
- An emergency kill switch stops new work but leaves queued or in-flight side effects unaccounted for.

## Exit criteria

Exit when every tested workflow has a reproducible authority chain, bounded tools and data scope, observable terminal state, enforced escalation for sensitive actions, and reconciled outcome evidence.

## Related runbooks, controls, examples, and templates

Use the agent-orchestration checklist, threat-model, AI-evaluation-report, finding, incident-review, and verification-plan templates. Use the incident response runbook when an agent performs or attempts an unsafe external action.
